"""Offline metadata and record-quality checks, not source authenticity verification."""
import argparse, json, math
from datetime import datetime,timezone

def parse(s):
 try:
  d=datetime.fromisoformat(s.replace('Z','+00:00'))
  if d.tzinfo is None:raise ValueError()
  return d
 except (TypeError,ValueError,AttributeError):raise ValueError('timezone-aware timestamp required')

def inspect(data,now=None):
 now=now or datetime.now(timezone.utc);errors=[]
 if not isinstance(data,dict):return dict(status='blocked',errors=['snapshot_object_required'])
 meta=data.get('metadata',{})
 if not isinstance(meta,dict):return dict(status='blocked',errors=['metadata_object_required'])
 for k in ('tenant_id','platform','store_id','source','currency','metric_definition'):
  if not isinstance(meta.get(k),str) or not meta[k].strip():errors.append('missing_metadata:'+k)
 if meta.get('currency')!='CNY':errors.append('currency_requires_explicit_conversion')
 try:
  age=(now-parse(meta.get('exported_at'))).total_seconds();limit=data['max_age_seconds']
  if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=604800:raise ValueError()
  if age< -30 or age>limit:errors.append('stale_or_future_snapshot')
 except (ValueError,KeyError):errors.append('invalid_export_time_or_freshness_limit')
 try:
  start=parse(meta.get('period_start'));end=parse(meta.get('period_end'))
  if start>=end or end>now:errors.append('invalid_period')
 except ValueError:errors.append('invalid_period')
 rows=data.get('rows');fields=data.get('required_fields');numeric=data.get('numeric_fields',[])
 if not isinstance(fields,list) or not fields or not all(isinstance(x,str) for x in fields):errors.append('required_fields_must_be_explicit');fields=[]
 if not isinstance(numeric,list) or not all(isinstance(x,str) for x in numeric):errors.append('invalid_numeric_fields');numeric=[]
 if not isinstance(rows,list) or not rows:errors.append('no_rows');rows=[]
 seen=set()
 for i,row in enumerate(rows):
  if not isinstance(row,dict):errors.append(f'row_{i}:not_object');continue
  key=row.get('record_id')
  if not isinstance(key,str) or not key:errors.append(f'row_{i}:missing_record_id')
  elif key in seen:errors.append(f'row_{i}:duplicate_record_id')
  else:seen.add(key)
  for field in fields:
   if field not in row or row[field] is None or row[field]=='':errors.append(f'row_{i}:missing:{field}')
  for field in numeric:
   value=row.get(field)
   if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):errors.append(f'row_{i}:invalid_numeric:{field}')
 return dict(status='passed_metadata_checks' if not errors else 'blocked',row_count=len(rows),errors=errors,limitation='Does not prove upstream authenticity, metric semantics, completeness or accounting reconciliation. Do not merge tenants or periods without explicit mapping.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 with open(a.input,encoding='utf-8-sig') as f:d=json.load(f)
 with open(a.output,'x',encoding='utf-8') as f:json.dump(inspect(d),f,ensure_ascii=False,indent=2)
