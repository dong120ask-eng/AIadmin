"""Local workflow bookkeeping only. This script never publishes or calls models."""
import argparse
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

GRAPH = {
 'planned': {'researched'}, 'researched': {'script_ready'},
 'script_ready': {'assets_ready','quality_checked','draft_saved'},
 'assets_ready': {'rendered','quality_checked','draft_saved'},
 'rendered': {'quality_checked','draft_saved'},
 'quality_checked': {'awaiting_approval','approved','draft_saved'},
 'awaiting_approval': {'approved','draft_saved'},
 'approved': {'submitting','draft_saved'},
 'submitting': {'submitted','scheduled','unknown'},
 'submitted': {'under_review','published','unknown'},
 'under_review': {'published','unknown'},
 'scheduled': {'submitted','under_review','published','unknown'},
 'draft_saved': set(), 'published': set(),
 'unknown': {'submitted','under_review','scheduled','published','draft_saved'},
 'blocked': set(), 'failed': set(),
}
REVIEW_KEYS = {'facts','originality','rights','media_quality','platform_rules','ai_and_commercial_labels','account_and_scope'}
SECRET_KEYS = {'password','api_key','access_token','refresh_token','cookies','cookie','authorization','secret'}
KINDS = {'article','image_text','short_video','long_video','audio','novel','music','short_drama'}


def stamp(): return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value):
        raise ValueError('Invalid identifier')
    return value


def no_secrets(value):
    if isinstance(value,dict):
        if any(str(k).lower() in SECRET_KEYS for k in value): raise ValueError('Store credential references, never secret fields')
        for v in value.values(): no_secrets(v)
    elif isinstance(value,list):
        for v in value:no_secrets(v)


def read_json(path):
    p=Path(path)
    if p.stat().st_size>4*1024*1024:raise ValueError('Input exceeds limit')
    value=json.loads(p.read_text(encoding='utf-8'))
    no_secrets(value)
    if not isinstance(value,dict):raise ValueError('Input must be an object')
    return value


def hashed(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


class Ledger:
    def __init__(self,root):
        self.root=Path(root).expanduser().resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'workflow.sqlite3'
        with self.connect() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects(tenant TEXT, project TEXT, body TEXT, PRIMARY KEY(tenant,project));
            CREATE TABLE IF NOT EXISTS jobs(job TEXT PRIMARY KEY, tenant TEXT, project TEXT, idem TEXT, request_hash TEXT, body TEXT, UNIQUE(tenant,project,idem));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT, at TEXT, state TEXT, evidence TEXT);
            ''')

    def connect(self):
        c=sqlite3.connect(self.db,timeout=10);c.row_factory=sqlite3.Row
        return c

    def project(self,tenant,project):
        identifier(tenant);identifier(project)
        with self.connect() as c:r=c.execute('SELECT body FROM projects WHERE tenant=? AND project=?',(tenant,project)).fetchone()
        if not r:raise ValueError('Project unavailable in this tenant')
        return json.loads(r[0])

    def create_project(self,data):
        no_secrets(data)
        tenant=identifier(data.get('tenant_id'));project=identifier(data.get('project_id'))
        if not isinstance(data.get('product'),dict):raise ValueError('Product record required')
        for account in data.get('accounts',[]):
            if account.get('tenant_id')!=tenant or account.get('project_id')!=project:raise ValueError('Account belongs to another project')
            identifier(account.get('account_key'))
        body=json.dumps(data,ensure_ascii=False)
        with self.connect() as c:
            old=c.execute('SELECT body FROM projects WHERE tenant=? AND project=?',(tenant,project)).fetchone()
            if old:
                if json.loads(old[0])!=data:raise ValueError('Existing project differs; version or review it before replacement')
                return {'status':'existing','tenant_id':tenant,'project_id':project}
            c.execute('INSERT INTO projects VALUES(?,?,?)',(tenant,project,body))
        return {'status':'created','tenant_id':tenant,'project_id':project}

    def job(self,tenant,job):
        identifier(tenant);identifier(job)
        with self.connect() as c:r=c.execute('SELECT body FROM jobs WHERE tenant=? AND job=?',(tenant,job)).fetchone()
        if not r:raise ValueError('Job unavailable in this tenant')
        return json.loads(r[0])

    def plan(self,data):
        tenant=identifier(data.get('tenant_id'));project=identifier(data.get('project_id'))
        profile=self.project(tenant,project)
        if data.get('content_type') not in KINDS:raise ValueError('Unsupported content type')
        topic=data.get('topic')
        if not isinstance(topic,str) or not topic.strip() or len(topic)>2000:raise ValueError('Topic required')
        account=data.get('account_key')
        external_id=None
        if account:
            identifier(account)
            match=[a for a in profile.get('accounts',[]) if a['account_key']==account]
            if not match or match[0].get('platform_id')!=data.get('platform_id'):raise ValueError('Account/platform mismatch')
            external_id=match[0].get('external_id')
        version=data.get('version',1)
        if isinstance(version,bool) or not isinstance(version,int) or version<1:raise ValueError('Positive version required')
        request={k:data.get(k) for k in ['tenant_id','project_id','content_id','topic','content_type','platform_id','account_key']}
        request['version']=version
        content=identifier(data.get('content_id'))
        key=identifier(data.get('idempotency_key') or hashed(request))
        job_id=identifier(data.get('job_id') or hashed({'request':request,'key':key})[:32])
        result={**request,'account_external_id':external_id,'job_id':job_id,'idempotency_key':key,'state':'planned','publish_state':'not_connected','artifacts':[],
                'artifact_digest':None,'review':None,'approval':None,'publication_evidence':None,'cost':{'estimated_cny':None,'actual_cny':None},'created_at':stamp(),'updated_at':stamp()}
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT request_hash,body FROM jobs WHERE tenant=? AND project=? AND idem=?',(tenant,project,key)).fetchone()
            if r:
                if r[0]!=hashed(request):raise ValueError('Idempotency payload conflict')
                return json.loads(r[1])
            c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',(job_id,tenant,project,key,hashed(request),json.dumps(result,ensure_ascii=False)))
            c.execute('INSERT INTO events(job,at,state,evidence) VALUES(?,?,?,?)',(job_id,stamp(),'planned','{}'))
        (self.root/'jobs'/job_id).mkdir(parents=True,exist_ok=True)
        return result

    def artifact_records(self,job,items):
        if not isinstance(items,list) or not 1<=len(items)<=100:raise ValueError('Actual artifacts required')
        folder=self.root/'jobs'/job['job_id']
        if folder.is_symlink():raise ValueError('Unsafe job folder')
        records=[]
        for item in items:
            if not isinstance(item,dict) or item.get('kind') not in {'production_brief','text_draft','script','image','audio','video'}:raise ValueError('Invalid artifact kind')
            relative=Path(item.get('path',''))
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Artifact path must remain in job folder')
            path=folder/relative
            if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()) or not path.is_file():raise ValueError('Missing or unsafe artifact')
            size=path.stat().st_size
            if size==0 or size>500*1024*1024:raise ValueError('Empty or oversized artifact')
            media_suffixes={'image':{'.png','.jpg','.jpeg','.webp','.gif','.svg'},'audio':{'.mp3','.wav','.m4a','.ogg','.flac'},'video':{'.mp4','.mov','.webm','.mkv'}}
            if item['kind'] in media_suffixes and path.suffix.lower() not in media_suffixes[item['kind']]:raise ValueError('Media artifact must have a matching media format; verify playable/readable quality separately')
            h=hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            records.append({'path':str(relative),'kind':item['kind'],'size':size,'sha256':h.hexdigest()})
        if len({r['path'] for r in records})!=len(records):raise ValueError('Duplicate artifact path')
        return sorted(records,key=lambda r:r['path'])

    def intact(self,job):
        actual=self.artifact_records(job,job['artifacts'])
        if actual!=job['artifacts'] or hashed(actual)!=job['artifact_digest']:raise ValueError('Artifact changed; existing review and approval are invalid')

    def allowed(self,project,job):
        scope=project.get('publish_scope') or {}
        if scope.get('mode') not in {'auto_publish','review_then_publish'} or scope.get('allowed') is not True or not scope.get('confirmed_at'):raise ValueError('Public publishing is not authorized')
        account=[a for a in project.get('accounts',[]) if a['account_key']==job.get('account_key')]
        if not account or account[0].get('publish_authorized') is not True:raise ValueError('Account publishing not authorized')
        if account[0].get('external_id')!=job.get('account_external_id'):raise ValueError('Account identity changed after planning')
        if job.get('platform_id') not in scope.get('platforms',[]) or account[0].get('external_id') not in scope.get('account_external_ids',[]):raise ValueError('Target is outside publishing scope')
        if job['content_type'] not in scope.get('forms',[]) or job['topic'] not in scope.get('topics',[]):raise ValueError('Topic or form outside publishing scope')
        return scope,account[0]

    def submission_ready(self,project,job):
        scope,account=self.allowed(project,job)
        required={'image_text':'image','short_video':'video','long_video':'video','short_drama':'video','audio':'audio','music':'audio'}.get(job['content_type'],'text_draft')
        if not any(a['kind']==required for a in job['artifacts']):raise ValueError('Actual content/media required; a script cannot substitute for a finished work')
        window=scope.get('time_window')
        if window!='any':
            if not isinstance(window,dict):raise ValueError('Explicit publishing time window required')
            start=datetime.fromisoformat(window.get('start',''));end=datetime.fromisoformat(window.get('end',''))
            if start.tzinfo is None or end.tzinfo is None or not start<=datetime.now(timezone.utc)<=end:raise ValueError('Outside authorized publishing time window')
        limit=scope.get('daily_limit')
        if isinstance(limit,bool) or not isinstance(limit,int) or limit<1:raise ValueError('Authorized daily limit required')
        today=datetime.now(timezone.utc).date()
        with self.connect() as c:
            rows=c.execute('SELECT body FROM jobs WHERE tenant=?',(job['tenant_id'],)).fetchall()
        count=0
        for row in rows:
            other=json.loads(row[0])
            if other['job_id']==job['job_id'] or other.get('platform_id')!=job.get('platform_id') or other.get('account_external_id')!=job.get('account_external_id'):continue
            if other.get('state') in {'submitting','unknown'}:raise ValueError('Another task for this account is submitting or unresolved; reconcile it before another submission')
            if other.get('state') in {'submitting','submitted','under_review','scheduled','published','unknown'} and datetime.fromisoformat(other['updated_at']).date()==today:count+=1
        if count>=limit:raise ValueError('Daily publishing limit reached (UTC ledger day); reconcile scheduled/unknown records before expanding')

    def advance(self,tenant,job_id,state,evidence):
        identifier(tenant);identifier(job_id);no_secrets(evidence)
        if state not in GRAPH:raise ValueError('Unknown state')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT body FROM jobs WHERE tenant=? AND job=?',(tenant,job_id)).fetchone()
            if not r:raise ValueError('Job unavailable')
            job=json.loads(r[0]);old=job['state']
            stop=state in {'failed','blocked','unknown'} and old!='published'
            if not stop and state not in GRAPH[old]:raise ValueError('Illegal transition; submitting/unknown cannot be blindly retried')
            if state in {'script_ready','assets_ready','rendered'}:
                records=self.artifact_records(job,evidence.get('artifacts'))
                if state=='rendered' and not any(a['kind'] in {'image','audio','video'} for a in records):raise ValueError('Rendered state requires actual media')
                job.update(artifacts=records,artifact_digest=hashed(records),review=None,approval=None)
            if state=='quality_checked':
                self.intact(job)
                review=evidence.get('review') or {}
                checks=review.get('checks') or {}
                if review.get('artifact_digest')!=job['artifact_digest'] or review.get('method') not in {'manual','automated','mixed'}:raise ValueError('Review does not match actual artifact version')
                if not REVIEW_KEYS.issubset(checks):raise ValueError('Review checklist incomplete')
                for key in REVIEW_KEYS:
                    value=checks[key]
                    if value!='pass' and not (isinstance(value,dict) and value.get('status')=='not_applicable' and value.get('reason')):raise ValueError('Critical review not passed')
                job['review']=review
            if state in {'approved','submitting','submitted','scheduled','under_review','published'}:
                self.intact(job)
                project=self.project(tenant,job['project_id'])
                scope,account=self.allowed(project,job)
                if state=='submitting':self.submission_ready(project,job)
                if not job.get('review') or job['review'].get('artifact_digest')!=job['artifact_digest']:raise ValueError('Review required before publishing')
                if state=='approved':
                    approval=evidence.get('approval') or {}
                    if approval.get('approved') is not True or not approval.get('confirmed_at') or approval.get('artifact_digest')!=job['artifact_digest']:raise ValueError('Actual matching approval required')
                    job['approval']=approval
                elif not job.get('approval') or job['approval'].get('artifact_digest')!=job['artifact_digest']:raise ValueError('Matching publishing approval required')
                if state in {'submitted','scheduled','under_review','published'}:
                    publication=evidence.get('publication') or {}
                    for key,value in [('job_id',job_id),('platform_id',job['platform_id']),('artifact_digest',job['artifact_digest']),('account_external_id',account['external_id'])]:
                        if publication.get(key)!=value:raise ValueError('Publication evidence target mismatch')
                    if publication.get('identity_verified') is not True or publication.get('source_mode') not in {'browser','api','manual'} or not publication.get('observed_at'):raise ValueError('Real account and platform observation required')
                    if publication.get('platform_status')!=state or (state=='published' and not publication.get('post_id')):raise ValueError('Final platform state and post identifier required')
                    job['publication_evidence']=publication
                    job['publish_state']=state
            if stop:job['blocker']=evidence.get('reason') or 'Execution requires reconciliation or intervention'
            job.update(state=state,updated_at=stamp())
            c.execute('UPDATE jobs SET body=? WHERE tenant=? AND job=?',(json.dumps(job,ensure_ascii=False),tenant,job_id))
            # Store only evidence fields from validated records, never raw pages or logs.
            recorded={'artifact_digest':job['artifact_digest'],'review':job.get('review'),'approval':job.get('approval'),'publication':job.get('publication_evidence')}
            c.execute('INSERT INTO events(job,at,state,evidence) VALUES(?,?,?,?)',(job_id,stamp(),state,json.dumps(recorded,ensure_ascii=False)))
        return job

    def export(self,tenant,job_id,output):
        job=self.job(tenant,job_id);self.intact(job)
        out=Path(output)
        if out.exists():raise ValueError('Output already exists')
        out.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('job.json',json.dumps(job,ensure_ascii=False,indent=2))
            for item in job['artifacts']:
                z.write(self.root/'jobs'/job_id/item['path'],'artifacts/'+item['path'])
        return {'status':'exported','job_id':job_id,'platform_fact_independently_verified':False}


def main():
    p=argparse.ArgumentParser(description='Local ledger only; no model, browser or publishing integration')
    p.add_argument('--root',required=True)
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['create-project','plan']:
        s=sub.add_parser(name);s.add_argument('--file',required=True)
    for name in ['show','advance','export']:
        s=sub.add_parser(name);s.add_argument('--tenant',required=True);s.add_argument('--job',required=True)
        if name=='advance':s.add_argument('--state',required=True);s.add_argument('--evidence',required=True)
        if name=='export':s.add_argument('--output',required=True)
    a=p.parse_args()
    try:
        ledger=Ledger(a.root)
        if a.command=='create-project':result=ledger.create_project(read_json(a.file))
        elif a.command=='plan':result=ledger.plan(read_json(a.file))
        elif a.command=='show':result=ledger.job(a.tenant,a.job)
        elif a.command=='advance':result=ledger.advance(a.tenant,a.job,a.state,read_json(a.evidence))
        else:result=ledger.export(a.tenant,a.job,a.output)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,sqlite3.Error) as e:
        p.exit(1,'Ledger operation failed: '+str(e)+'\n')


if __name__=='__main__':main()
