"""Durable local dispatch. Only Android inspection has an executable worker."""
import hashlib
import json
import math
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from .android import AndroidInspector
from .media import execution_plan, validate_binding
from .store import Problem, identifier


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class DispatchQueue:
    def __init__(self,path,clock=time.time):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.clock=clock
        with self.transaction() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS dispatch_tasks(
              id TEXT PRIMARY KEY,tenant TEXT NOT NULL,project TEXT NOT NULL,request_key TEXT NOT NULL,
              payload TEXT NOT NULL,payload_digest TEXT NOT NULL,resource TEXT NOT NULL,action TEXT NOT NULL,
              state TEXT NOT NULL,lease_token TEXT,worker TEXT,lease_until REAL,result TEXT,
              created REAL NOT NULL,updated REAL NOT NULL,UNIQUE(tenant,request_key));
              CREATE TABLE IF NOT EXISTS dispatch_resources(resource TEXT PRIMARY KEY,task_id TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS dispatch_events(id INTEGER PRIMARY KEY,task_id TEXT NOT NULL,
              state TEXT NOT NULL,at REAL NOT NULL,note TEXT NOT NULL);''')

    @contextmanager
    def transaction(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        db.row_factory=sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE');yield db;db.commit()
        except Exception:db.rollback();raise
        finally:db.close()

    def _row(self,db,tenant,task):
        row=db.execute('SELECT * FROM dispatch_tasks WHERE tenant=? AND id=?',(tenant,task)).fetchone()
        if row is None:raise Problem('队列任务不存在',404)
        return row

    def _event(self,db,task,state,note):
        db.execute('INSERT INTO dispatch_events(task_id,state,at,note) VALUES(?,?,?,?)',
                   (task,state,self.clock(),note))

    def _view(self,row,include_lease=False):
        out=dict(row)
        for field in ['payload','result']:
            out[field]=json.loads(out[field]) if out[field] else None
        if not include_lease:out.pop('lease_token',None)
        out['publishing_verified']=False
        return out

    def enqueue(self,tenant,binding,request,key,action='inspect_only'):
        identifier(tenant);identifier(key)
        binding=validate_binding(binding)
        if tenant!=binding['tenant_id']:raise Problem('企业与执行配置不匹配',409)
        if action not in {'inspect_only','draft','publish'}:raise Problem('队列动作无效')
        allowed={'tenant_id','project_id','account_id','channel_id','content_type','publish_mode'}
        if not isinstance(request,dict) or set(request)-allowed:raise Problem('队列只接受任务引用和发布模式，不接受凭证或命令')
        plan=execution_plan(binding,request)
        payload={'binding':binding,'request':request,'action':action,'plan':plan}
        payload_hash=digest(payload)
        state='queued' if action=='inspect_only' and binding['route']!='browser' else 'blocked'
        stamp=self.clock();task='dispatch-'+uuid.uuid4().hex
        with self.transaction() as db:
            previous=db.execute('SELECT * FROM dispatch_tasks WHERE tenant=? AND request_key=?',(tenant,key)).fetchone()
            if previous:
                if previous['payload_digest']!=payload_hash:raise Problem('同一幂等键对应的内容已变化，不能重复入队',409)
                return self._view(previous)
            db.execute('INSERT INTO dispatch_tasks(id,tenant,project,request_key,payload,payload_digest,resource,action,state,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (task,tenant,binding['project_id'],key,json.dumps(payload,ensure_ascii=False),payload_hash,plan['exclusive_resource'],action,state,stamp,stamp))
            self._event(db,task,state,'只读安卓检查可执行；真实发布适配器尚未接入')
            return self._view(self._row(db,tenant,task))

    def _expire(self,db):
        rows=db.execute("SELECT id FROM dispatch_tasks WHERE state='running' AND lease_until<=?",(self.clock(),)).fetchall()
        for row in rows:
            db.execute("UPDATE dispatch_tasks SET state='unknown',lease_token=NULL,updated=? WHERE id=?",(self.clock(),row['id']))
            self._event(db,row['id'],'unknown','执行租约到期；资源保留隔离，先核查再恢复')
        return len(rows)

    def recover(self):
        with self.transaction() as db:return {'marked_unknown':self._expire(db),'auto_requeued':False}

    def claim(self,tenant,worker,lease_seconds=120,action="inspect_only",max_browser_sessions=2,profile_ref=None):
        identifier(tenant);identifier(worker)
        if action not in {"inspect_only", "draft", "browser_read"}:raise Problem("不允许执行发布")
        if isinstance(lease_seconds,bool) or not isinstance(lease_seconds,(int,float)) or not math.isfinite(lease_seconds) or not 5<=lease_seconds<=600:
            raise Problem('租约必须为5至600秒')
        if type(max_browser_sessions) is not int or not 1 <= max_browser_sessions <= 2:
            raise Problem('浏览器并发上限必须为1或2')
        with self.transaction() as db:
            self._expire(db)
            if action in {'draft','browser_read'} and db.execute(
                    "SELECT count(*) FROM dispatch_resources WHERE resource LIKE 'browser-profile:%'").fetchone()[0] >= max_browser_sessions:
                return None
            row=db.execute("SELECT t.* FROM dispatch_tasks t LEFT JOIN dispatch_resources r ON t.resource=r.resource WHERE t.tenant=? AND t.state='queued' AND t.action=? AND r.resource IS NULL ORDER BY t.created,t.rowid",(tenant,action)).fetchall()
            candidates=row;row=None;extra=None
            for candidate in candidates:
                payload=json.loads(candidate["payload"])
                if profile_ref is not None and payload["binding"].get("profile_ref") != profile_ref:continue
                unique=payload["binding"]["account_unique_id"]
                alias = None
                if action == 'draft' or (action == 'browser_read' and payload['binding']['channel_id'] == 'wechat-official-draft'):
                    alias = 'wechat-account:' + hashlib.sha256(unique.encode()).hexdigest()
                elif action == 'browser_read':
                    alias = 'browser-account:' + digest({'channel':payload['binding']['channel_id'],'unique':unique})
                if alias and db.execute("SELECT 1 FROM dispatch_resources WHERE resource=?",(alias,)).fetchone():continue
                row=candidate;extra=alias;break
            if row is None:return None
            token=secrets.token_hex(24)
            if extra:db.execute('INSERT INTO dispatch_resources(resource,task_id) VALUES(?,?)',(extra,row['id']))
            db.execute('INSERT INTO dispatch_resources(resource,task_id) VALUES(?,?)',(row['resource'],row['id']))
            db.execute("UPDATE dispatch_tasks SET state='running',worker=?,lease_token=?,lease_until=?,updated=? WHERE id=?",(worker,token,self.clock()+lease_seconds,self.clock(),row['id']))
            self._event(db,row['id'],'running','取得设备／会话排他锁')
            return self._view(self._row(db,tenant,row['id']),True)

    def _owned(self,db,tenant,task,token):
        row=self._row(db,tenant,task)
        if row['state']!='running' or not token or row['lease_token']!=token or row['lease_until']<=self.clock():
            raise Problem('执行租约无效；过期进程不能更新任务',409)
        return row

    def heartbeat(self,tenant,task,token,lease_seconds=120):
        if isinstance(lease_seconds,bool) or not isinstance(lease_seconds,(int,float)) or not math.isfinite(lease_seconds) or not 5<=lease_seconds<=600:raise Problem('租约无效')
        with self.transaction() as db:
            self._owned(db,tenant,task,token)
            db.execute('UPDATE dispatch_tasks SET lease_until=?,updated=? WHERE id=?',(self.clock()+lease_seconds,self.clock(),task))

    def finish_inspection(self,tenant,task,token,artifact):
        if not isinstance(artifact,dict) or set(artifact)!={'relative_path','sha256'} or not isinstance(artifact['relative_path'],str) or not isinstance(artifact['sha256'],str):raise Problem('检查结果必须为文件路径和哈希')
        expected=f'device-inspections/{task}/source.xml'
        if artifact['relative_path']!=expected:raise Problem('检查产物路径不匹配')
        target=self.path.parent/expected
        if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(self.path.parent.resolve()):raise Problem('检查产物缺失或路径无效')
        if target.stat().st_size>4*1024*1024:raise Problem('检查产物过大')
        if hashlib.sha256(target.read_bytes()).hexdigest()!=artifact['sha256']:raise Problem('检查产物哈希不匹配')
        with self.transaction() as db:
            row=self._owned(db,tenant,task,token)
            if row['action']!='inspect_only':raise Problem('检查执行器不能完成发布任务')
            db.execute("UPDATE dispatch_tasks SET state='inspected',lease_token=NULL,result=?,updated=? WHERE id=?",(json.dumps(artifact),self.clock(),task))
            db.execute('DELETE FROM dispatch_resources WHERE task_id=?',(task,))
            self._event(db,task,'inspected','已保存实际页面文件；不是账号核验或发布成功')
            return self._view(self._row(db,tenant,task))

    def mark_unknown(self,tenant,task,token):
        with self.transaction() as db:
            self._owned(db,tenant,task,token)
            db.execute("UPDATE dispatch_tasks SET state='unknown',lease_token=NULL,updated=? WHERE id=?",(self.clock(),task))
            self._event(db,task,'unknown','执行异常；不输出页面或凭证，不自动释放资源')

    def resolve_unknown(self,tenant,task,reason,worker_stopped=False):
        if worker_stopped is not True:raise Problem('须先确认旧进程已停止，否则不释放设备')
        if not isinstance(reason,str) or not 3<=len(reason.strip())<=500:raise Problem('填写核查结论，不提交账号秘密')
        with self.transaction() as db:
            row=self._row(db,tenant,task)
            if row['state']!='unknown':raise Problem('只能核查状态未知的任务',409)
            db.execute("UPDATE dispatch_tasks SET state='cancelled',updated=? WHERE id=?",(self.clock(),task))
            db.execute('DELETE FROM dispatch_resources WHERE task_id=?',(task,))
            self._event(db,task,'cancelled','人工核查完毕；结论保存在本机，不自动重发')
            # Free-text reconciliation notes may contain private account facts.
            db.execute('UPDATE dispatch_tasks SET result=? WHERE id=?',(json.dumps({'manual_resolution':reason,'worker_stopped':True},ensure_ascii=False),task))
            return self._view(self._row(db,tenant,task))

    def tasks(self,tenant):
        identifier(tenant)
        with self.transaction() as db:
            return [self._view(row) for row in db.execute('SELECT * FROM dispatch_tasks WHERE tenant=? ORDER BY created,rowid',(tenant,))]

    def inspect_next(self,tenant,worker,server='http://127.0.0.1:4723',backend='appium'):
        # Validate the local endpoint before obtaining a device lock.
        if backend=='appium':client=AndroidInspector(server)
        elif backend in {'uiautomator2','mobilerun'}:
            from .android_sdks import LocalSdkInspector
            client=LocalSdkInspector(backend)
        else:raise Problem('检查后端无效')
        task=self.claim(tenant,worker)
        if task is None:return {'status':'idle','publishing_verified':False}
        token=task['lease_token'];binding=task['payload']['binding']
        try:
            client.connect(binding);content=client.source();client.close()
            self.heartbeat(tenant,task['id'],token)
            relative=f"device-inspections/{task['id']}/source.xml"
            target=self.path.parent/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.parent.resolve().is_relative_to(self.path.parent.resolve()):raise Problem('检查目录越界')
            with target.open('x',encoding='utf-8') as file:file.write(content)
            return self.finish_inspection(tenant,task['id'],token,{'relative_path':relative,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        except Exception:
            try:client.close()
            except Exception:pass
            try:self.mark_unknown(tenant,task['id'],token)
            except Problem:self.recover()
            raise Problem('设备检查中断，任务与资源隔离；核查并停止旧进程后再恢复',409)

