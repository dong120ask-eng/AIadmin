"""Local multi-account read-only browser prototype; never exports credentials."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from .dispatch import DispatchQueue, digest
from .media import validate_binding, media_index
from .store import Store, Problem
from .wechat_session import ProfileLease


def protected_root(path):
    raw = Path(path).absolute()
    if any(p.is_symlink() for p in [raw, *raw.parents]):
        raise Problem('私有目录不能包含符号链接')
    root = raw.resolve()
    checkout = Path(__file__).resolve().parent.parent
    if root == checkout or root.is_relative_to(checkout):
        raise Problem('会话资料必须位于仓库外')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != 'nt': os.chmod(root, 0o700)
    return root


class Sessions:
    def __init__(self, queue, store, root):
        self.queue, self.store = queue, store
        self.root = protected_root(root)
        with queue.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS browser_sessions(
                profile TEXT PRIMARY KEY,tenant TEXT NOT NULL,project TEXT NOT NULL,account TEXT NOT NULL,
                channel TEXT NOT NULL,identity_hash TEXT NOT NULL,binding TEXT NOT NULL,
                state TEXT NOT NULL,checked REAL,UNIQUE(tenant,project,account),
                UNIQUE(channel,identity_hash))''')

    def register(self, tenant, binding, authorized=False):
        binding = validate_binding(binding)
        if authorized is not True or binding['route'] != 'browser' or tenant != binding['tenant_id']:
            raise Problem('须明确授权本机会话只读检查，并匹配企业')
        accounts = self.store.accounts(tenant, binding['project_id'])
        if not any(a['id']==binding['account_id'] and a['external_id']==binding['account_unique_id'] for a in accounts):
            raise Problem('工作台账号与绑定不匹配',409)
        with self.queue.transaction() as db:
            old = db.execute('SELECT binding FROM browser_sessions WHERE profile=?',(binding['profile_ref'],)).fetchone()
            if old:
                if json.loads(old[0]) != binding: raise Problem('Profile已绑定其他账号或配置',409)
                return
            try:
                db.execute('INSERT INTO browser_sessions VALUES(?,?,?,?,?,?,?,?,NULL)',
                    (binding['profile_ref'],tenant,binding['project_id'],binding['account_id'],binding['channel_id'],
                     digest(binding['account_unique_id']),json.dumps(binding), 'unverified'))
            except Exception as exc:
                import sqlite3
                if isinstance(exc,sqlite3.IntegrityError): raise Problem('账号或平台身份已有独占Profile',409) from None
                raise

    def binding(self, tenant, profile):
        with self.queue.transaction() as db:
            row=db.execute('SELECT binding,state FROM browser_sessions WHERE tenant=? AND profile=?',(tenant,profile)).fetchone()
            if not row: raise Problem('会话不存在',404)
            if row['state']=='revoked':raise Problem('本机会话授权已撤销',409)
            return json.loads(row[0])

    def enqueue(self, tenant, profile, request, key):
        binding=self.binding(tenant,profile)
        task=self.queue.enqueue(tenant,binding,request,key,action='inspect_only')
        with self.queue.transaction() as db:
            row=self.queue._row(db,tenant,task['id'])
            # Only this explicitly registered adapter can promote a blocked plan.
            if row['state']=='blocked' and row['action']=='inspect_only':
                db.execute("UPDATE dispatch_tasks SET action='browser_read',state='queued' WHERE id=?",(task['id'],))
                self.queue._event(db,task['id'],'queued','已授权本机只读；不包含草稿或发布')
            return self.queue._view(self.queue._row(db,tenant,task['id']))

    def run(self, tenant, worker, port, limit=2):
        task=self.queue.claim(tenant,worker,120,action='browser_read',max_browser_sessions=limit,profile_ref=getattr(port,"config",{}).get("profile_ref"))
        if not task:return {'status':'idle','publishing_verified':False}
        token=task['lease_token']; binding=task['payload']['binding']; profile=binding['profile_ref']
        lease=None
        try:
            if self.binding(tenant,profile)!=binding:raise Problem('绑定已变化')
            self.register(tenant,binding,True)
            if (self.root/profile).is_symlink():raise Problem("Profile不得为链接")
            lease=ProfileLease(self.root/profile).acquire()
            port.connect(binding,self.root/profile)
            if port.identity()!=binding['account_unique_id']:raise Problem('身份不匹配或登录过期')
            before=port.read_digest()
            if not isinstance(before,str) or len(before)!=64 or any(c not in '0123456789abcdef' for c in before):
                raise Problem('只读回读摘要无效')
            if port.identity()!=binding['account_unique_id']:raise Problem('读取期间账号变化')
            if self.binding(tenant,profile)!=binding:raise Problem('会话授权已变化')
            self.queue.heartbeat(tenant,task['id'],token)
            live=isinstance(port,ReadOnlyBrowser)
            result={'verification':'real_browser_read' if live else 'isolated_fixture',
                    'readback_sha256':before,'identity_verified':True,'draft_saved':False,'publishing_verified':False}
            # Close the actual browser before releasing durable queue resources.
            port.close();lease.close();lease=None
            with self.queue.transaction() as db:
                self.queue._owned(db,tenant,task['id'],token)
                if db.execute('SELECT state FROM browser_sessions WHERE profile=?',(profile,)).fetchone()[0]=='revoked':
                    raise Problem('会话授权已撤销')
                state='read_verified' if live else 'test_verified'
                db.execute('UPDATE dispatch_tasks SET state=?,result=?,lease_token=NULL,updated=? WHERE id=?',
                           (state,json.dumps(result),self.queue.clock(),task['id']))
                db.execute('DELETE FROM dispatch_resources WHERE task_id=?',(task['id'],))
                db.execute('UPDATE browser_sessions SET state=?,checked=? WHERE profile=?',
                           ('verified' if live else 'fixture_verified',self.queue.clock(),profile))
                self.queue._event(db,task['id'],state,'身份前后核对及只读摘要完成；未保存或发布')
            return result
        except Exception:
            with self.queue.transaction() as db:
                db.execute("UPDATE browser_sessions SET state='needs_login_or_review' WHERE profile=? AND state!='revoked'",(profile,))
            try:self.queue.mark_unknown(tenant,task['id'],token)
            except Problem:self.queue.recover()
            raise Problem('只读检查失败：可能过期、错号、页面变更或运行时故障；隔离任务，停止旧进程后核查',409) from None
        finally:
            try:port.close()
            finally:
                if lease:lease.close()


class ReadOnlyBrowser:
    """Operator-verified selectors, fixed official entry; no clicks or writes."""
    def __init__(self, config, login=False):
        if (not isinstance(config,dict) or set(config)!={'profile_ref','identity_selector','read_selector','verified_at'}
                or not config['verified_at'] or not all(isinstance(config[k],str) and 0<len(config[k])<=500
                for k in ['identity_selector','read_selector'])):raise Problem('需要现场核验的只读选择器')
        self.config=config;self.login=login;self.context=self.engine=self.page=None

    def connect(self,binding,directory):
        if binding['profile_ref']!=self.config['profile_ref']:raise Problem('选择器会话不匹配')
        channel=next(c for c in media_index()['channels'] if c['id']==binding['channel_id'])
        self.entry=channel['entry_url'];self.origin=self._origin(self.entry)
        if self.origin[0]!='https':raise Problem('需要官方HTTPS入口')
        from playwright.sync_api import sync_playwright
        self.engine=sync_playwright().start()
        self.context=self.engine.chromium.launch_persistent_context(str(directory),headless=False)
        self.context.set_default_timeout(10000)
        self.page=self.context.new_page();self.page.goto(self.entry,timeout=20000)
        if self._origin(self.page.url)!=self.origin:raise Problem('页面离开官方域名')
        if self.login:input('仅在官方界面完成授权登录，完成后回车；不输入凭证到终端：')

    @staticmethod
    def _origin(url):
        p=urlsplit(url);return p.scheme,p.hostname,p.port or 443

    def _read(self,key):
        if self._origin(self.page.url)!=self.origin:raise Problem('页面离开授权官方域名')
        node=self.page.locator(self.config[key])
        if node.count()!=1:raise Problem('登录过期或元素不唯一')
        value=node.inner_text(timeout=10000).strip()
        if not value or len(value)>100000:raise Problem('回读为空或过大')
        return value

    def identity(self):return self._read('identity_selector')
    def read_digest(self):return digest(self._read('read_selector'))
    def close(self):
        try:
            if self.context:self.context.close()
        finally:
            self.context=None
            if self.engine:self.engine.stop();self.engine=None


def main():
    p=argparse.ArgumentParser(description='多账号本机只读会话；不保存草稿、不发布')
    p.add_argument('--data-dir',required=True);p.add_argument('--profiles-root',required=True)
    p.add_argument('--tenant',default='internal')
    sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('register');r.add_argument('--binding',required=True);r.add_argument('--authorize-read',action='store_true')
    e=sub.add_parser('enqueue');e.add_argument('--profile',required=True);e.add_argument('--request',required=True);e.add_argument('--key',required=True)
    w=sub.add_parser('run');w.add_argument('--config',required=True);w.add_argument('--worker',default='browser-worker');w.add_argument('--limit',type=int,default=2);w.add_argument('--login',action='store_true')
    l=sub.add_parser('login');l.add_argument('--profile',required=True);l.add_argument('--inspect',action='store_true')
    v=sub.add_parser('revoke');v.add_argument('--profile',required=True)
    sub.add_parser('status');sub.add_parser('recover')
    x=sub.add_parser('resolve');x.add_argument('--task',required=True);x.add_argument('--worker-stopped',action='store_true')
    args=p.parse_args()
    try:
        data=protected_root(args.data_dir)
        q=DispatchQueue(data/'dispatch.sqlite3');s=Sessions(q,Store(data/'workbench.sqlite3'),args.profiles_root)
        read=lambda f:json.loads(Path(f).read_text(encoding='utf-8-sig'))
        if args.command=='register':s.register(args.tenant,read(args.binding),args.authorize_read);result={'registered':True,'identity_verified':False}
        elif args.command=='enqueue':result=s.enqueue(args.tenant,args.profile,read(args.request),args.key)
        elif args.command=='run':result=s.run(args.tenant,args.worker,ReadOnlyBrowser(read(args.config),args.login),args.limit)
        elif args.command=='login':
            binding=s.binding(args.tenant,args.profile)
            with q.transaction() as db:
                if db.execute('SELECT 1 FROM dispatch_resources WHERE resource=?',('browser-profile:'+args.profile,)).fetchone():
                    raise Problem('会话正运行或隔离中')
            if (s.root/args.profile).is_symlink():raise Problem('Profile不得为链接')
            lease=ProfileLease(s.root/args.profile).acquire()
            port=None
            try:
                # Bootstrap opens the official entry only; no identity assertion.
                port=ReadOnlyBrowser({'profile_ref':args.profile,'identity_selector':'bootstrap-unused',
                                      'read_selector':'bootstrap-unused','verified_at':'bootstrap'},True)
                port.connect(binding,s.root/args.profile)
                if args.inspect:port.page.pause()
                result={'status':'manual_login_only','identity_verified':False,'publishing_verified':False}
            finally:
                try:
                    if port:port.close()
                finally:lease.close()
        elif args.command=='revoke':
            s.binding(args.tenant,args.profile)
            with q.transaction() as db:
                db.execute("UPDATE browser_sessions SET state='revoked' WHERE tenant=? AND profile=?",(args.tenant,args.profile))
            result={'authorization_revoked':True}
        elif args.command=='recover':result=q.recover()
        elif args.command=='resolve':result=q.resolve_unknown(args.tenant,args.task,'操作者已停止旧进程并核查本机只读任务',args.worker_stopped)
        else:
            result=[{'id':t['id'],'state':t['state'],'action':t['action'],'publishing_verified':False} for t in q.tasks(args.tenant)]
        # No raw account/binding/request/URL or exception text in CLI output.
        if args.command=='enqueue':result={'id':result['id'],'state':result['state']}
        print(json.dumps(result,ensure_ascii=False));return 0
    except (Exception,KeyboardInterrupt):
        print('会话操作未完成，请检查本机绑定、授权、运行时及任务隔离状态；不自动重试。');return 1

if __name__=='__main__':raise SystemExit(main())
