import unittest
from capacity import estimate
class Tests(unittest.TestCase):
 def row(self):return dict(tenant_id='t',platform='jd',store_id='s',model='mixed',orders_per_day=100,exception_rate=.1,minutes_per_exception=10,routine_manual_minutes=20,api_calls_per_day=200,api_quota_per_day=100,worker_minutes=60)
 def test_overload(self):
  x=estimate(dict(operator_minutes_per_day=100,worker_minutes_per_day=50,stores=[self.row()]))
  self.assertEqual(x['operator_required_minutes'],120);self.assertTrue(x['operator_overloaded']);self.assertTrue(x['worker_overloaded']);self.assertTrue(x['quota_exceeded'])
 def test_store_scope(self):
  a=self.row();b=dict(a,platform='tmall')
  self.assertEqual(len(estimate(dict(operator_minutes_per_day=400,worker_minutes_per_day=400,stores=[a,b]))['stores']),2)
  with self.assertRaises(ValueError):estimate(dict(operator_minutes_per_day=400,worker_minutes_per_day=400,stores=[a,a]))
if __name__=='__main__':unittest.main()
