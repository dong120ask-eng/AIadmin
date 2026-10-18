import unittest
from ecom_tools import calculate
class Tests(unittest.TestCase):
 def test_profit(self):
  r=dict(record_id='1',sku='a',net_revenue=100,merchant_subsidy=0,goods_cost=40,platform_fees=5,ad_spend=30,fulfillment_cost=10,after_sales_net_loss=20,other_variable_cost=0)
  self.assertEqual(calculate('profit',{'rows':[r]})['total_contribution_profit'],'-5.00')
  with self.assertRaises(ValueError):calculate('profit',{'rows':[r,r]})
  del r['goods_cost']
  with self.assertRaises(ValueError):calculate('profit',{'rows':[r]})
 def test_promotion_order(self):
  r=dict(scenario_id='1',unit_price=100,quantity=1,merchant_subsidy=0,total_variable_cost=65,unit_price_floor=75,operations=[dict(type='multiply',factor=.8),dict(type='subtract',threshold=90,amount=10,threshold_basis='initial')])
  self.assertEqual(calculate('promotion',{'rows':[r]})['results'][0]['payable'],'70.00')
  r['operations'][1]['threshold_basis']='current'
  self.assertEqual(calculate('promotion',{'rows':[r]})['results'][0]['payable'],'80.00')
 def test_inventory(self):
  r=dict(sku='a',on_hand=10,reserved=2,safety=1,requests=[dict(store_id='A',requested=6),dict(store_id='B',requested=6)])
  x=calculate('inventory',{'rows':[r]})['results'][0]
  self.assertEqual([a['allocated'] for a in x['allocations']],[6,1])
 def test_zero_and_invalid(self):
  r=dict(channel='a',impressions=0,clicks=0,visitors=0,cart_users=0,buyers=0)
  self.assertIsNone(calculate('funnel',{'rows':[r]})['results'][0]['buyer_rate'])
  for v in [-1,'NaN',True,1.5]:
   r['buyers']=v
   with self.assertRaises(ValueError):calculate('funnel',{'rows':[r]})
 def test_cases(self):
  r=dict(case_id='1',sku='a',reason='破损',refund_amount=10)
  self.assertEqual(calculate('after_sales',{'rows':[r]})['results'][0]['refund_amount'],'10.00')
  with self.assertRaises(ValueError):calculate('after_sales',{'rows':[r,r]})
if __name__=='__main__':unittest.main()
