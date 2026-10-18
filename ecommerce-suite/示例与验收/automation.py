"""Persistent host automation gate. No built-in merchant adapters. Standard library only."""
import argparse, json, sqlite3, hashlib, subprocess
from datetime import datetime, timezone
from pathlib import Path
WRITE_ACTIONS={'campaign_enroll','campaign_update','product_title_update','product_main_image_update','product_detail_update','product_selling_points_update','ad_plan_update','price_update','inventory_update'}
READ_ACTIONS={'campaign_detect','product_read','metrics_read','ad_report_read'}

def call(adapter,request):
    if not isinstance(adapter,list) or not adapter or not all(isinstance(x,str) for x in adapter):raise ValueError('explicit adapter argv required')
    p=subprocess.run(adapter,input=json.dumps(request,ensure_ascii=False),text=True,capture_output=True,timeout=60,shell=False)
    if p.returncode:raise RuntimeError('adapter failed; inspect local redacted logs')
    result=json.loads(p.stdout)
    if not isinstance(result,dict):raise ValueError('adapter response must be object')
    if any(result.get(k)!=request.get(k) for k in ('tenant_id','platform','store_id')):raise ValueError('adapter tenant/platform/store identity mismatch')
    return result

def now():return datetime.now(timezone.utc).isoformat()
def record(conn,key,status,detail):
    conn.execute('INSERT INTO tasks VALUES (?,?,?,?) ON CONFLICT(task_key) DO UPDATE SET status=excluded.status, detail=excluded.detail, updated=excluded.updated',(key,status,json.dumps(detail,ensure_ascii=False),now()));conn.commit()

def task_key(t):
    # Display task ID is not a business idempotency key.
    identity={k:t.get(k) for k in ('store_id','action','target_id','expected_before','desired_value','operation_version')}
    return hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def process(config,conn):
    if config.get('stop',False):return [{'status':'blocked','reason':'stop switch enabled'}]
    results=[]
    for t in config.get('tasks',[]):
        key=task_key(t)
        previous=conn.execute('select status from tasks where task_key=?',(key,)).fetchone()
        if previous and previous[0] in ('verified','unknown','running','submitted'):
            results.append({'task_id':t.get('task_id'),'status':previous[0],'reason':'no automatic replay; reconcile uncertain tasks with platform first'});continue
        status='blocked';detail={'task_id':t.get('task_id')}
        try:
            store=t['store_id'];action=t['action'];adapter=config.get('adapters',{}).get(store)
            binding=config.get('stores',{}).get(store,{})
            if adapter and (not binding.get('tenant_id') or not binding.get('platform')):raise ValueError('explicit tenant/platform/store binding required')
            if action not in READ_ACTIONS|WRITE_ACTIONS:raise ValueError('unsupported action')
            if not adapter:
                detail['reason']='merchant adapter not connected'
            elif action in READ_ACTIONS:
                response=call(adapter,dict(op='read',tenant_id=binding['tenant_id'],platform=binding['platform'],store_id=store,action=action,target_id=t['target_id'],idempotency_key=key))
                if response.get('ok') is not True:raise ValueError('read not confirmed')
                status='read_verified';detail['evidence']=response
            else:
                auth=config.get('authorization',{})
                expiry=datetime.fromisoformat(auth.get('valid_until','').replace('Z','+00:00'))
                if expiry.tzinfo is None or expiry<=datetime.now(timezone.utc):raise ValueError('missing/expired timezone-aware authorization')
                if store not in auth.get('stores',[]) or action not in auth.get('actions',[]):raise ValueError('not authorized for store/action')
                if t['target_id'] not in auth.get('targets_by_store',{}).get(store,[]):raise ValueError('target not authorized for this store')
                if auth.get('bindings',{}).get(store)!=binding:raise ValueError('authorization tenant/platform binding mismatch')
                # Paid actions require per-task financial reservation in a real budget service; do not fake it here.
                if action in ('ad_plan_update','campaign_enroll','campaign_update','price_update','inventory_update'):
                    detail['reason']='requires platform-specific promotion/budget/inventory validator; unavailable in generic runner'
                else:
                    req=dict(tenant_id=binding['tenant_id'],platform=binding['platform'],store_id=store,action=action,target_id=t['target_id'],idempotency_key=key)
                    before=call(adapter,dict(req,op='read'))
                    if before.get('ok') is not True or before.get('value')!=t['expected_before']:raise ValueError('precondition changed or unreadable')
                    if config.get('mode','preview')!='execute':
                        status='prepared';detail.update(before=t['expected_before'],after=t['desired_value'],reason='preview mode; no write')
                    else:
                        record(conn,key,'running',detail)
                        status='unknown' # preserve uncertainty if submit or verification fails
                        submitted=call(adapter,dict(req,op='write',expected_before=t['expected_before'],desired_value=t['desired_value']))
                        if submitted.get('ok') is not True:raise RuntimeError('write outcome uncertain; reconcile before retry')
                        status='submitted';record(conn,key,status,detail)
                        after=call(adapter,dict(req,op='read'))
                        if after.get('ok') is True and after.get('value')==t['desired_value']:
                            status='verified';detail['receipt_id']=submitted.get('receipt_id');detail['evidence']=after
                        else:status='unknown';detail['reason']='readback differs; reconcile before retry'
        except Exception as e:
            detail['reason']=str(e)[:300]
            if status not in ('unknown','submitted'):status='blocked'
        record(conn,key,status,detail);results.append(dict(detail,status=status))
    return results

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--state',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if Path(a.output).exists():p.exit(2,'output already exists; no tasks executed\n')
    # Exclusive local file lock: applies to one shared state path on one host only.
    lock=Path(a.state+'.lock')
    try:
        with lock.open('x') as f:f.write(str(datetime.now(timezone.utc)))
    except FileExistsError:p.exit(2,'state locked; inspect running process before removing stale lock\n')
    try:
        with open(a.config,encoding='utf-8') as f:config=json.load(f)
        with sqlite3.connect(a.state) as c:
            c.execute('create table if not exists tasks(task_key text primary key,status text,detail text,updated text)')
            result=process(config,c)
        with open(a.output,'x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
