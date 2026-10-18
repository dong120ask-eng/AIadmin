import unittest, sqlite3, json, copy, tempfile, subprocess, sys
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
import automation as m
class GateTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');m.initialize(self.c)
  self.t=dict(task_id='one',store_id='s',target_id='sku',action='product_title_update',expected_before='old',desired_value='new',operation_version='v1')
  self.cfg=dict(mode='execute',stores={'s':dict(tenant_id='tenant',platform='jd')},adapters={'s':['trusted-adapter']},authorization=dict(stores=['s'],actions=['product_title_update','metrics_read','campaign_enroll'],targets_by_store={'s':['sku']},bindings={'s':dict(tenant_id='tenant',platform='jd')},valid_until=(m.utc()+timedelta(hours=1)).isoformat()),tasks=[self.t])
 def tearDown(self):self.c.close()
 def reply(self,req,value='old',**kw):return dict(req,ok=True,value=value,observed_at=m.utc().isoformat(),revision='r1',atomic_compare_and_set=True,**kw)
 def success(self,adapter,req):return self.reply(req,'new' if req['op']=='write' or getattr(self,'written',False) else 'old',receipt_id='receipt')
 def run_with(self,fn):
  with patch('automation.call',side_effect=fn) as adapter:return m.process(self.cfg,self.c),adapter
 def test_write_verified(self):
  def fn(a,q):
   if q['op']=='write':self.written=True;self.assertEqual(q['expected_revision'],'r1')
   return self.success(a,q)
  x,_=self.run_with(fn);self.assertEqual(x[0]['status'],'verified')
 def test_read_requires_auth(self):
  self.t['action']='metrics_read';self.cfg['authorization']['revoked']=True
  x,a=self.run_with(self.success);self.assertEqual(x[0]['reason'],'authorization_revoked');a.assert_not_called()
 def test_cached_task_revocation(self):
  k=m.task_key(self.t,self.cfg['stores']['s']);scope=m.digest(['tenant','jd','s']);m.record(self.c,k,scope,'sku','verified',{})
  self.cfg['authorization']['revoked']=True
  x,_=self.run_with(self.success);self.assertEqual(x[0]['status'],'blocked')
 def test_display_id_stable(self):self.assertEqual(m.task_key(self.t,self.cfg['stores']['s']),m.task_key(dict(self.t,task_id='another'),self.cfg['stores']['s']))
 def test_tenant_key_separate(self):self.assertNotEqual(m.task_key(self.t,dict(tenant_id='a',platform='jd')),m.task_key(self.t,dict(tenant_id='b',platform='jd')))
 def test_uncertain_different_version_blocked(self):
  k=m.task_key(self.t,self.cfg['stores']['s']);m.record(self.c,k,m.digest(['tenant','jd','s']),'sku','unknown',{})
  self.t['operation_version']='v2';x,a=self.run_with(self.success);self.assertEqual(x[0]['reason'],'object_has_unresolved_write');a.assert_not_called()
 def test_uncertain_same_key_preserved(self):
  k=m.task_key(self.t,self.cfg['stores']['s']);m.record(self.c,k,m.digest(['tenant','jd','s']),'sku','unknown',{})
  self.run_with(self.success);self.assertEqual(self.c.execute('select status from tasks_v6 where task_key=?',(k,)).fetchone()[0],'unknown')
 def test_stale(self):
  x,_=self.run_with(lambda a,q:dict(self.reply(q),observed_at=(m.utc()-timedelta(hours=2)).isoformat()));self.assertEqual(x[0]['reason'],'stale_or_future_observation')
 def test_future(self):
  x,_=self.run_with(lambda a,q:dict(self.reply(q),observed_at=(m.utc()+timedelta(hours=2)).isoformat()));self.assertEqual(x[0]['status'],'blocked')
 def test_wrong_object(self):
  x,_=self.run_with(lambda a,q:dict(self.reply(q),target_id='different'));self.assertEqual(x[0]['reason'],'response_scope_or_object_mismatch')
 def test_no_atomic_revision(self):
  x,a=self.run_with(lambda a,q:dict(self.reply(q),atomic_compare_and_set=False));self.assertEqual(x[0]['reason'],'atomic_remote_revision_required');self.assertEqual(a.call_count,1)
 def test_expired_during_preflight(self):
  def fn(a,q):self.cfg['authorization']['valid_until']=(m.utc()-timedelta(seconds=1)).isoformat();return self.reply(q)
  x,a=self.run_with(fn);self.assertEqual(x[0]['reason'],'authorization_expired');self.assertEqual(a.call_count,1)
 def test_write_timeout_no_replay(self):
  def fn(a,q):
   if q['op']=='write':raise TimeoutError('SECRET_DO_NOT_LOG')
   return self.reply(q)
  x,_=self.run_with(fn);self.assertEqual(x[0]['status'],'unknown');self.assertNotIn('SECRET',json.dumps(x))
  x,a=self.run_with(self.success);a.assert_not_called()
 def test_no_sensitive_payload_logging(self):
  self.t['action']='metrics_read'
  x,_=self.run_with(lambda a,q:self.reply(q,{'buyer_phone':'SECRET'}));self.assertEqual(x[0]['status'],'read_verified');self.assertNotIn('SECRET',str(list(self.c.execute('select detail from events_v6'))))
 def test_preview_no_write(self):
  self.cfg['mode']='preview';x,a=self.run_with(lambda a,q:self.reply(q));self.assertEqual(x[0]['status'],'prepared');self.assertEqual(a.call_count,1)
 def test_special_write_blocked(self):
  self.t['action']='campaign_enroll';x,a=self.run_with(self.success);self.assertEqual(x[0]['reason'],'platform_specific_validator_unavailable');a.assert_not_called()
 def test_legacy_uncertain(self):
  self.c.execute('create table tasks(status text)');self.c.execute("insert into tasks values('unknown')")
  x,a=self.run_with(self.success);self.assertEqual(x[0]['reason'],'legacy_uncertain_tasks_require_reconciliation');a.assert_not_called()
 def test_one_bad_task_does_not_stop_others(self):
  self.cfg['tasks']=[None,dict(self.t,action='metrics_read')];x,_=self.run_with(lambda a,q:self.reply(q));self.assertEqual([i['status'] for i in x],['blocked','read_verified'])
 def test_store_pause(self):
  self.cfg['stores']['s']['paused']=True;x,a=self.run_with(self.success);self.assertEqual(x[0]['reason'],'stop_switch_enabled');a.assert_not_called()
 def test_already_verified_no_write(self):
  k=m.task_key(self.t,self.cfg['stores']['s']);m.record(self.c,k,m.digest(['tenant','jd','s']),'sku','verified',{})
  x,a=self.run_with(self.success);self.assertEqual(x[0]['status'],'already_verified');a.assert_not_called()
 def test_existing_receipt_not_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'out.json').write_text('keep');(p/'cfg.json').write_text(json.dumps(self.cfg))
   r=subprocess.run([sys.executable,str(Path(m.__file__)), '--config',str(p/'cfg.json'),'--state',str(p/'state.db'),'--output',str(p/'out.json')],capture_output=True)
   self.assertNotEqual(r.returncode,0);self.assertFalse((p/'state.db').exists());self.assertEqual((p/'out.json').read_text(),'keep')
 def test_response_scope_validation(self):
  req=dict(tenant_id='a',platform='jd',store_id='s',target_id='sku',action='metrics_read',idempotency_key='k')
  with self.assertRaises(m.GateError):m.response_ok(dict(self.reply(req),platform='tmall'),req,300)
if __name__=='__main__':unittest.main()
