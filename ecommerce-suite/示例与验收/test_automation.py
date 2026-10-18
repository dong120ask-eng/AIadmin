import unittest,sqlite3
from automation import process
class AutomationTests(unittest.TestCase):
 def conn(self):
  c=sqlite3.connect(':memory:');c.execute('create table tasks(task_key text primary key,status text,detail text,updated text)');return c
 def test_write_readback_and_timeout(self):
  from unittest.mock import patch
  t=dict(task_id='w',store_id='s',action='product_title_update',target_id='a',expected_before='old',desired_value='new')
  config=dict(mode='execute',authorization=dict(stores=['s'],actions=['product_title_update'],targets_by_store={'s':['a']},bindings={'s':{'tenant_id':'t','platform':'p'}},valid_until='2099-01-01T00:00:00+00:00'),adapters={'s':['trusted-adapter']},stores={'s':{'tenant_id':'t','platform':'p'}},tasks=[t])
  with patch('automation.call',side_effect=[{'ok':True,'value':'old'},{'ok':True,'receipt_id':'mock'}, {'ok':True,'value':'new'}]):
   c=self.conn();self.assertEqual(process(config,c)[0]['status'],'verified')
  with patch('automation.call',side_effect=[{'ok':True,'value':'old'},TimeoutError('uncertain')]):
   c=self.conn();self.assertEqual(process(config,c)[0]['status'],'unknown')
  t['action']='campaign_enroll';config['authorization']['actions']=['campaign_enroll']
  with patch('automation.call') as mock:
   self.assertEqual(process(config,self.conn())[0]['status'],'blocked');mock.assert_not_called()
 def test_display_id_does_not_replay(self):
  from automation import task_key
  a=dict(task_id='one',store_id='s',action='product_title_update',target_id='a',desired_value='new')
  b=dict(a,task_id='two');self.assertEqual(task_key(a),task_key(b))
 def test_identity_mismatch(self):
  from automation import call
  from unittest.mock import patch
  import subprocess,json
  request=dict(tenant_id='t',platform='jd',store_id='s')
  response=subprocess.CompletedProcess(['trusted'],0,json.dumps(dict(tenant_id='other',platform='jd',store_id='s',ok=True)),'')
  with patch('automation.subprocess.run',return_value=response):
   with self.assertRaises(ValueError):call(['trusted'],request)
 def test_missing_adapter(self):
  c=self.conn();x=process({'tasks':[dict(task_id='1',store_id='s',action='campaign_enroll',target_id='a')]},c)
  self.assertEqual(x[0]['status'],'blocked');self.assertIn('not connected',x[0]['reason'])
 def test_stop(self):self.assertEqual(process({'stop':True},self.conn())[0]['status'],'blocked')
 def test_unknown_not_replayed(self):
  import hashlib,json
  t=dict(task_id='1',store_id='s',action='product_title_update',target_id='a')
  from automation import task_key
  key=task_key(t);c=self.conn();c.execute('insert into tasks values (?,?,?,?)',(key,'unknown','{}','now'))
  self.assertEqual(process({'tasks':[t]},c)[0]['status'],'unknown')
if __name__=='__main__':unittest.main()
