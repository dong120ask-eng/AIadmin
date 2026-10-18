import unittest,copy
from datetime import datetime,timezone
from data_quality import inspect
class QualityTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,18,13,tzinfo=timezone.utc)
  self.d=dict(metadata=dict(tenant_id='demo',platform='jd',store_id='s',source='SYNTHETIC_DEMO',currency='CNY',metric_definition='paid revenue net of refunds',exported_at='2026-10-18T12:00:00Z',period_start='2026-10-17T00:00:00Z',period_end='2026-10-18T00:00:00Z'),max_age_seconds=7200,required_fields=['record_id','revenue'],numeric_fields=['revenue'],rows=[dict(record_id='1',revenue=10)])
 def test_valid(self):self.assertEqual(inspect(self.d,self.now)['status'],'passed_metadata_checks')
 def test_stale(self):self.d['max_age_seconds']=60;self.assertEqual(inspect(self.d,self.now)['status'],'blocked')
 def test_duplicate(self):self.d['rows']*=2;self.assertIn('row_1:duplicate_record_id',inspect(self.d,self.now)['errors'])
 def test_missing_not_zero(self):self.d['rows'][0]['revenue']=None;self.assertIn('row_0:missing:revenue',inspect(self.d,self.now)['errors'])
 def test_infinite(self):self.d['rows'][0]['revenue']=float('inf');self.assertEqual(inspect(self.d,self.now)['status'],'blocked')
 def test_bad_period(self):self.d['metadata']['period_end']='2030-01-01T00:00:00Z';self.assertIn('invalid_period',inspect(self.d,self.now)['errors'])
 def test_currency(self):self.d['metadata']['currency']='USD';self.assertIn('currency_requires_explicit_conversion',inspect(self.d,self.now)['errors'])
if __name__=='__main__':unittest.main()
