"""v6 single-host automation gate. No merchant adapter is bundled."""
import argparse, hashlib, json, sqlite3, subprocess
from datetime import datetime, timezone
from pathlib import Path

WRITE_ACTIONS={'campaign_enroll','campaign_update','product_title_update','product_main_image_update','product_detail_update','product_selling_points_update','ad_plan_update','price_update','inventory_update'}
READ_ACTIONS={'campaign_detect','product_read','metrics_read','ad_report_read'}
SPECIAL={'campaign_enroll','campaign_update','ad_plan_update','price_update','inventory_update'}
UNRESOLVED={'running','submitted','unknown'}

class GateError(Exception):pass

def utc():return datetime.now(timezone.utc)
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
def timestamp(v):
    try:
        d=datetime.fromisoformat(v.replace('Z','+00:00'))
        if d.tzinfo is None:raise ValueError()
        return d
    except (ValueError,AttributeError,TypeError):raise GateError('timezone_aware_timestamp_required')
def identifier(v):
    if not isinstance(v,str) or not v or len(v)>200 or any(ord(c)<32 for c in v):raise GateError('invalid_identifier')
    return v

def initialize(c):
    c.execute('CREATE TABLE IF NOT EXISTS tasks_v6(task_key TEXT PRIMARY KEY, scope TEXT NOT NULL, target_id TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, updated TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS events_v6(id INTEGER PRIMARY KEY,task_key TEXT NOT NULL,status TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL)')
    c.commit()

def record(c,key,scope,target,status,detail):
    raw=json.dumps(detail,ensure_ascii=False,allow_nan=False)
    with c:
        c.execute('INSERT INTO tasks_v6 VALUES(?,?,?,?,?,?) ON CONFLICT(task_key) DO UPDATE SET status=excluded.status,detail=excluded.detail,updated=excluded.updated',(key,scope,target,status,raw,utc().isoformat()))
        c.execute('INSERT INTO events_v6(task_key,status,detail,created) VALUES(?,?,?,?)',(key,status,raw,utc().isoformat()))

def authorized(cfg,t,b):
    if cfg.get('stop') is True or b.get('paused') is True:raise GateError('stop_switch_enabled')
    a=cfg.get('authorization',{});store=t['store_id']
    if a.get('revoked') is True:raise GateError('authorization_revoked')
    if timestamp(a.get('valid_until'))<=utc():raise GateError('authorization_expired')
    if store not in a.get('stores',[]) or t['action'] not in a.get('actions',[]):raise GateError('store_or_action_not_authorized')
    if t['target_id'] not in a.get('targets_by_store',{}).get(store,[]):raise GateError('target_not_authorized_for_store')
    if a.get('bindings',{}).get(store)!={k:b[k] for k in ('tenant_id','platform')}:raise GateError('authorization_binding_mismatch')

def task_key(t,b):
    return digest({**{k:b[k] for k in ('tenant_id','platform')},**{k:t.get(k) for k in ('store_id','action','target_id','expected_before','desired_value','operation_version')}})

def call(adapter,request):
    if not isinstance(adapter,list) or not adapter or not all(isinstance(s,str) and s for s in adapter):raise GateError('trusted_adapter_argv_required')
    try:
        p=subprocess.run(adapter,input=json.dumps(request,ensure_ascii=False,allow_nan=False),text=True,capture_output=True,timeout=60,shell=False)
        if p.returncode:raise GateError('adapter_failed')
        if len(p.stdout)>1_000_000:raise GateError('adapter_response_too_large')
        return json.loads(p.stdout,parse_constant=lambda s:(_ for _ in ()).throw(ValueError()))
    except GateError:raise
    except Exception:raise GateError('adapter_transport_or_json_error')

def response_ok(r,req,max_age):
    if not isinstance(r,dict) or r.get('ok') is not True:raise GateError('adapter_not_confirmed')
    if any(r.get(k)!=req.get(k) for k in ('tenant_id','platform','store_id','target_id','action','idempotency_key')):raise GateError('response_scope_or_object_mismatch')
    age=(utc()-timestamp(r.get('observed_at'))).total_seconds()
    if age < -30 or age>max_age:raise GateError('stale_or_future_observation')

def process(cfg,c):
    initialize(c)
    if cfg.get('stop') is True:return [{'status':'blocked','reason':'stop_switch_enabled'}]
    if cfg.get('mode','preview') not in ('preview','execute'):raise GateError('invalid_mode')
    tasks=cfg.get('tasks',[])
    if not isinstance(tasks,list) or len(tasks)>1000:raise GateError('task_batch_limit_1000')
    age=cfg.get('max_observation_age_seconds',300)
    if isinstance(age,bool) or not isinstance(age,int) or not 1<=age<=3600:raise GateError('invalid_freshness_window')
    # Legacy uncertain actions cannot be mapped safely: reconcile before any new writes.
    legacy=False
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tasks'").fetchone():
        legacy=bool(c.execute("SELECT 1 FROM tasks WHERE status IN ('running','submitted','unknown') LIMIT 1").fetchone())
    results=[]
    for raw in tasks:
        status='blocked';key=scope=target=None;detail={}
        try:
            if not isinstance(raw,dict):raise GateError('task_object_required')
            t=raw
            for k in ('task_id','store_id','action','target_id'):identifier(t.get(k))
            detail={'task_id':t['task_id']}
            b=cfg.get('stores',{}).get(t['store_id'],{})
            for k in ('tenant_id','platform'):identifier(b.get(k))
            action=t['action'];target=t['target_id'];scope=digest([b['tenant_id'],b['platform'],t['store_id']])
            detail.update(tenant_id=b['tenant_id'],platform=b['platform'],store_id=t['store_id'],target_id=target,action=action)
            if action not in READ_ACTIONS|WRITE_ACTIONS:raise GateError('unsupported_action')
            authorized(cfg,t,b) # Applies to reads, writes, and cached state disclosure.
            if action in WRITE_ACTIONS:identifier(t.get('operation_version'))
            key=task_key(t,b)
            if action in WRITE_ACTIONS:
                if legacy:raise GateError('legacy_uncertain_tasks_require_reconciliation')
                unresolved=c.execute("SELECT task_key,status FROM tasks_v6 WHERE scope=? AND target_id=? AND status IN ('running','submitted','unknown') LIMIT 1",(scope,target)).fetchone()
                if unresolved:raise GateError('object_has_unresolved_write')
                old=c.execute('SELECT status FROM tasks_v6 WHERE task_key=?',(key,)).fetchone()
                if old and old[0]=='verified':
                    results.append(dict(detail,status='already_verified',reason='no_replay'));continue
            adapter=cfg.get('adapters',{}).get(t['store_id'])
            if not adapter:raise GateError('merchant_adapter_not_connected')
            if action in SPECIAL:raise GateError('platform_specific_validator_unavailable')
            req=dict(tenant_id=b['tenant_id'],platform=b['platform'],store_id=t['store_id'],target_id=target,action=action,idempotency_key=key)
            before=call(adapter,dict(req,op='read'));response_ok(before,req,age)
            detail['observation_time']=before['observed_at']
            # Log only hashes and identity, never full adapter payload/buyer records.
            if action in READ_ACTIONS:
                status='read_verified';detail['data_sha256']=digest(before.get('value'))
                detail['reason']='read_verified_payload_not_logged'
            else:
                if 'expected_before' not in t or 'desired_value' not in t:raise GateError('before_and_desired_required')
                if before.get('value')!=t['expected_before']:raise GateError('precondition_changed')
                detail.update(before_sha256=digest(t['expected_before']),desired_sha256=digest(t['desired_value']))
                if cfg.get('mode','preview')=='preview':status='prepared'
                else:
                    if before.get('atomic_compare_and_set') is not True or not isinstance(before.get('revision'),str) or not before['revision']:raise GateError('atomic_remote_revision_required')
                    authorized(cfg,t,b) # May expire during preflight read.
                    record(c,key,scope,target,'running',detail)
                    status='unknown'
                    submitted=call(adapter,dict(req,op='write',expected_revision=before['revision'],expected_before=t['expected_before'],desired_value=t['desired_value']))
                    response_ok(submitted,req,age)
                    # Require an adapter receipt before classifying submission.
                    identifier(submitted.get('receipt_id'))
                    status='submitted';detail['receipt_sha256']=digest(submitted['receipt_id']);record(c,key,scope,target,status,detail)
                    after=call(adapter,dict(req,op='read'));response_ok(after,req,age)
                    if after.get('value')==t['desired_value']:
                        status='verified';detail['reason']='stored_value_verified_not_live_review_or_business_result'
                    else:status='unknown';detail['reason']='readback_differs_reconcile'
        except GateError as e:
            detail['reason']=str(e)
        except Exception:
            detail['reason']='invalid_input_or_internal_error'
        # Never overwrite an existing uncertain record with blocked from a replay.
        if key and scope and target:
            old=c.execute('SELECT status FROM tasks_v6 WHERE task_key=?',(key,)).fetchone()
            if not (status=='blocked' and old and old[0] in UNRESOLVED):record(c,key,scope,target,status,detail)
        results.append(dict(detail,status=status))
    return results

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--state',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    state=Path(a.state).resolve();output=Path(a.output).resolve();config=Path(a.config).resolve()
    if output in (state,config):p.exit(2,'output must differ from state and config\n')
    lock=Path(str(state)+'.lock');locked=False
    try:
        with lock.open('x') as f:f.write(utc().isoformat())
        locked=True
        # Reserve a writable new receipt before any adapter operation; no truncation.
        with output.open('x',encoding='utf-8') as out:
            with config.open(encoding='utf-8-sig') as f:cfg=json.load(f)
            with sqlite3.connect(str(state)) as c:result=process(cfg,c)
            json.dump(result,out,ensure_ascii=False,indent=2)
    except (OSError,ValueError,GateError):p.exit(2,'operation blocked; inspect configuration/state; existing files preserved\n')
    finally:
        if locked:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
