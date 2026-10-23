"""Draft-only browser worker. Core is stdlib; the UI driver is opt-in.

The port must return a reopened draft, never an editor's unsaved fields.
Fixtures finish as test_verified, never draft_saved. No publish capability.
"""
import hashlib
import json
import secrets
from pathlib import Path
from .dispatch import digest
from .media import validate_binding
from .store import Problem, digest as artifact_digest, identifier


def normalized(value):
    return ' '.join(value.split())


def checked_package(store, tenant, job_id, binding, assets_root):
    binding = validate_binding(binding)
    job = store.job(tenant, job_id)
    account = next((a for a in store.accounts(tenant, job['project_id'])
                    if a['id'] == job['account_id']), None)
    if (tenant != binding['tenant_id'] or not account or account['platform'] != 'wechat'
            or job['platform'] != 'wechat' or job['content_type'] != 'article'
            or job['state'] != 'checked' or binding['project_id'] != job['project_id']
            or binding['account_id'] != account['id']
            or binding['account_unique_id'] != account['external_id']
            or binding['channel_id'] != 'wechat-official-draft' or binding['route'] != 'browser'):
        raise Problem('须使用同项目已审核公众号文章及对应账号绑定', 409)
    current = artifact_digest(job['artifacts'])
    checks = job['checks']
    if (current != job['artifact_digest'] or checks.get('artifact_digest') != current
            or checks.get('items') != dict.fromkeys(['facts','rights','format','ai_label'], True)
            or not all(v is True for v in checks.get('items',{}).values())):
        raise Problem('审核与当前产物版本不符', 409)
    try:
        result = json.loads(job['artifacts']['result.json'])
        payload = result['payload']
        title, body = payload['title'], payload['body']
        if result['content_type'] != 'article' or result['deliverable_status'] != 'text_draft':
            raise ValueError()
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 64:
            raise ValueError()
        if not isinstance(body, str) or not 100 <= len(body.strip()) <= 20000:
            raise ValueError()
        # First version accepts plain text only. HTML is never executed.
        spec = payload.get('browser_assets', [])
        if not isinstance(spec, list) or len(spec) > 20:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise Problem('任务包须包含真实文章标题和正文；首版标题64字、正文100至20000字') from None
    root = Path(assets_root).resolve()
    assets = []
    for item in spec:
        if (not isinstance(item, dict) or set(item) != {'path','sha256','role'}
                or item['role'] not in {'cover','inline'} or not isinstance(item['path'], str)):
            raise Problem('素材需包含相对路径、SHA256和cover/inline用途')
        relative = Path(item['path'])
        target = root / relative
        if (relative.is_absolute() or '..' in relative.parts or target.is_symlink()
                or not target.resolve().is_relative_to(root) or not target.is_file()
                or target.suffix.lower() not in {'.png','.jpg','.jpeg'}
                or target.stat().st_size > 10*1024*1024):
            raise Problem('素材缺失、越界或不符合首版图片限制')
        if hashlib.sha256(target.read_bytes()).hexdigest() != item['sha256']:
            raise Problem('素材内容与审核哈希不一致',409)
        assets.append(dict(item))
    if sum(x['role'] == 'cover' for x in assets) != 1:
        raise Problem('任务包必须包含一张已审核封面；不得跳过素材')
    article = {'title': title.strip(), 'body': body.strip(), 'assets': assets}
    return job, account, article


class BrowserDraftWorker:
    def __init__(self, queue, store, assets_root):
        self.queue, self.store = queue, store
        self.assets_root = Path(assets_root).resolve()
        if queue.path.resolve() == store.path.resolve():
            raise Problem('工作台与队列须使用独立数据库')
        with queue.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS browser_draft_attempts(
                fingerprint TEXT PRIMARY KEY,task TEXT UNIQUE NOT NULL,draft_ref TEXT,
                receipt TEXT,evidence TEXT,verified INTEGER NOT NULL DEFAULT 0)''')

    def enqueue(self, tenant, job_id, binding, key, draft_authorized=False):
        identifier(key)
        if draft_authorized is not True:
            raise Problem('须明确授权保存该账号草稿')
        job, account, article = checked_package(self.store,tenant,job_id,binding,self.assets_root)
        request = {k: binding[k] for k in ('tenant_id','project_id','account_id','channel_id')}
        request.update(content_type='article',publish_mode='draft_only')
        snapshot = {'job_id':job_id,'artifact_digest':job['artifact_digest'],'article':article}
        # Keep the general enqueue API blocked. Only this reviewed path enables a draft.
        row = self.queue.enqueue(tenant,binding,request,key,'draft')
        with self.queue.transaction() as db:
            current = self.queue._row(db,tenant,row['id'])
            payload = json.loads(current['payload'])
            if 'browser_draft' in payload:
                if payload['browser_draft'] != snapshot:
                    raise Problem('同一幂等键对应的文章版本已变化',409)
            elif current['state'] == 'blocked':
                payload['browser_draft'] = snapshot
                payload['plan'].update(status='configured_unverified',execution='wechat_browser_draft')
                db.execute("UPDATE dispatch_tasks SET payload=?,state='queued' WHERE id=?",
                           (json.dumps(payload,ensure_ascii=False),row['id']))
                self.queue._event(db,row['id'],'queued','已授权公众号草稿；真实浏览器能力待执行核验')
            return self.queue._view(self.queue._row(db,tenant,row['id']))

    def _validate(self, task):
        snap = task['payload']['browser_draft']
        job, account, article = checked_package(self.store,task['tenant'],snap['job_id'],
                                               task['payload']['binding'],self.assets_root)
        if job['artifact_digest'] != snap['artifact_digest'] or article != snap['article']:
            raise Problem('入队后文章或素材已变化',409)
        return job, account, article

    def _guard(self, task, token, port, account):
        self.queue.heartbeat(task['tenant'],task['id'],token,120)
        if port.identity() != account['external_id']:
            raise Problem('实际页面账号唯一ID与绑定不一致',409)

    def run(self, tenant, worker, port):
        # Serialize review changes during the irreversible draft save. The UI driver
        # has bounded calls; scan/login is completed BEFORE starting this worker.
        with self.store.connection() as lock:
            lock.execute('BEGIN IMMEDIATE')
            task = self.queue.claim(tenant,worker,120,action='draft',
                                    profile_ref=getattr(port,'config',{}).get('profile_ref'))
            if task is None:return {'status':'idle','publishing_verified':False}
            token = task['lease_token']
            try:
                job, account, article = self._validate(task)
                port.connect(task['payload']['binding'])
                self._guard(task,token,port,account)
                fingerprint = digest({'account':account['external_id'],'article':article})
                # Durable intent BEFORE opening an editor (which may autosave).
                with self.queue.transaction() as db:
                    self.queue._owned(db,tenant,task['id'],token)
                    if db.execute('SELECT 1 FROM browser_draft_attempts WHERE fingerprint=?',(fingerprint,)).fetchone():
                        raise Problem('相同账号内容已有执行意图；先核对旧草稿，不重复创建',409)
                    db.execute('INSERT INTO browser_draft_attempts(fingerprint,task) VALUES(?,?)',(fingerprint,task['id']))
                # The callback is called immediately before every UI mutation.
                guard = lambda: self._guard(task,token,port,account)
                port.fill(article,self.assets_root,guard)
                guard()
                reference = port.save_draft(guard)  # never retries this click
                if not isinstance(reference,str) or not 1 <= len(reference) <= 200:
                    raise Problem('保存后未取得稳定草稿ID',409)
                with self.queue.transaction() as db:
                    self.queue._owned(db,tenant,task['id'],token)
                    receipt = port.export_receipt() if hasattr(port,'export_receipt') else None
                    db.execute('UPDATE browser_draft_attempts SET draft_ref=?,receipt=? WHERE task=?',(reference,json.dumps(receipt),task['id']))
                return self._readback(task,token,port,account,article,job,reference)
            except Exception:
                try:self.queue.mark_unknown(tenant,task['id'],token)
                except Problem:self.queue.recover()
                raise Problem('公众号草稿执行中断；任务与会话隔离，先核对后台，不自动重发',409) from None
            finally:
                try:port.close()
                except Exception:pass

    def _readback(self, task, token, port, account, article, job, reference):
        self._guard(task,token,port,account)
        observed = port.read_draft(reference)
        self._guard(task,token,port,account)
        if (observed.get('draft_ref') != reference or observed.get('account_unique_id') != account['external_id']
                or observed.get('title') != article['title']
                or normalized(observed.get('body','')) != normalized(article['body'])
                or observed.get('assets') != article['assets']
                or observed.get('reopened_from_list') is not True):
            raise Problem('重新打开草稿后的标题、正文或素材不一致',409)
        live = getattr(port,'verification_mode',None) == 'official_browser'
        evidence = {'job_id':job['id'],'draft_ref':reference,'artifact_digest':job['artifact_digest'],
                    'article_digest':digest(article),'account_id':account['id'],
                    'verification':'official_browser_readback' if live else 'isolated_fixture',
                    'draft_saved':live,'backend_record_verified':live,'publishing_verified':False,
                    'readback_digest':digest(observed)}
        state = 'draft_saved' if live else 'test_verified'
        with self.queue.transaction() as db:
            self.queue._owned(db,task['tenant'],task['id'],token)
            db.execute('UPDATE browser_draft_attempts SET evidence=?,verified=? WHERE task=?',
                       (json.dumps(evidence),int(live),task['id']))
            db.execute('UPDATE dispatch_tasks SET state=?,result=?,lease_token=NULL,updated=? WHERE id=?',
                       (state,json.dumps(evidence),self.queue.clock(),task['id']))
            db.execute('DELETE FROM dispatch_resources WHERE task_id=?',(task['id'],))
            self.queue._event(db,task['id'],state,'草稿回读核对完成；未执行发布')
            return self.queue._view(self.queue._row(db,task['tenant'],task['id']))

    def reconcile(self, tenant, task_id, port, worker_stopped=False):
        if worker_stopped is not True:raise Problem('先确认旧进程已停止')
        with self.store.connection() as lock:
            lock.execute('BEGIN IMMEDIATE')
            with self.queue.transaction() as db:
                row = self.queue._row(db,tenant,task_id)
                attempt = db.execute('SELECT draft_ref,receipt FROM browser_draft_attempts WHERE task=?',(task_id,)).fetchone()
                if row['state'] != 'unknown' or not attempt or not attempt['draft_ref']:
                    raise Problem('无已记录草稿ID时须人工核对后台；禁止自动重建',409)
                task = self.queue._view(row)
                resource = db.execute('SELECT task_id FROM dispatch_resources WHERE resource=?',(row['resource'],)).fetchone()
                if not resource or resource['task_id'] != task_id:raise Problem('隔离锁缺失',409)
                token = secrets.token_hex(24)
                db.execute("UPDATE dispatch_tasks SET state='running',lease_token=?,lease_until=? WHERE id=?",
                           (token,self.queue.clock()+120,task_id))
            try:
                job, account, article = self._validate(task)
                port.connect(task['payload']['binding'])
                if hasattr(port,'restore_receipt'):
                    if not attempt['receipt']:raise Problem('素材回读凭据缺失；须人工核查',409)
                    port.restore_receipt(json.loads(attempt['receipt']))
                return self._readback(task,token,port,account,article,job,attempt['draft_ref'])
            except Exception:
                try:self.queue.mark_unknown(tenant,task_id,token)
                except Problem:self.queue.recover()
                raise Problem('只读核对未通过；继续隔离',409) from None
            finally:
                try:port.close()
                except Exception:pass
