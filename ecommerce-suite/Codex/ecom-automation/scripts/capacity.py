"""Offline single-operator capacity estimate, not a performance benchmark."""
import argparse,json,math

def positive(x,zero=False):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<(0 if zero else 1e-12):raise ValueError('invalid nonnegative/positive capacity input')
 return x

def estimate(data):
 available=positive(data['operator_minutes_per_day']);machine=positive(data['worker_minutes_per_day']);rows=[];seen=set()
 for s in data['stores']:
  key=(s['tenant_id'],s['platform'],s['store_id'])
  if key in seen:raise ValueError('duplicate scoped store')
  seen.add(key)
  if s['model'] not in ['owned_stock','dropship','consignment','service','mixed']:raise ValueError('explicit business model required')
  orders=positive(s['orders_per_day'],True);rate=positive(s['exception_rate'],True)
  if rate>1:raise ValueError('exception rate > 1')
  manual=positive(s['routine_manual_minutes'],True)+orders*rate*positive(s['minutes_per_exception'],True)
  calls=positive(s['api_calls_per_day'],True);quota=positive(s['api_quota_per_day']);runtime=positive(s['worker_minutes'],True)
  rows.append(dict(tenant_id=key[0],platform=key[1],store_id=key[2],model=s['model'],manual_minutes=round(manual,2),quota_exceeded=calls>quota,worker_minutes=runtime))
 total=sum(x['manual_minutes'] for x in rows);work=sum(x['worker_minutes'] for x in rows)
 return dict(status='offline_estimate',stores=rows,operator_required_minutes=round(total,2),operator_available_minutes=available,operator_overloaded=total>available,worker_required_minutes=work,worker_overloaded=work>machine,quota_exceeded=any(x['quota_exceeded'] for x in rows),limitation='Input-based estimate, not observed capacity. Validate on real peak traffic, human exceptions and platform quotas. No unlimited-store claim.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 with open(a.input,encoding='utf-8') as f:r=estimate(json.load(f))
 with open(a.output,'x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
