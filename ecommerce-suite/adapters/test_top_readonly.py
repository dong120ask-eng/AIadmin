import importlib.util
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

top = load('top_readonly', HERE / 'top_readonly.py')
gate = load('gate', HERE.parent / 'Codex/ecom-automation/scripts/automation.py')

class Fake:
    def __init__(self, sid=123, total=1, duplicate=False):
        self.evidence = [{'source': 'synthetic_test_only'}]
        self.calls = []
        self.sid, self.total, self.duplicate = sid, total, duplicate
    def call(self, method, **params):
        self.calls.append(method)
        if method == 'taobao.shop.seller.get':
            return {'shop': {'sid': self.sid}}
        page = int(params['page_no'])
        start = 0 if self.duplicate else (page-1)*40
        return {'total_results': self.total, 'items': {'item': [{'num_iid': n+1, 'title': 'SYNTHETIC', 'unexpected': 'drop'} for n in range(start, min(start+40, self.total))]}}

class Tests(unittest.TestCase):
    def setUp(self):
        self.binding = dict(tenant_id='test', platform='taobao', store_id='test-store', shop_sid='123')
        self.req = dict(self.binding, op='read', action='product_read', target_id='onsale', idempotency_key='test')
    def test_official_signature_vector(self):
        params = dict(method='taobao.item.seller.get', app_key='12345678', session='test', timestamp='2016-01-01 12:00:00', format='json', v='2.0', sign_method='md5', fields='num_iid,title,nick,price,num', num_iid='11223344')
        self.assertEqual(top.sign(params, 'helloworld'), '66987CB115214E59E6EC978214934FB8')
    def test_remote_identity_blocks_data(self):
        client = Fake(sid=456)
        with self.assertRaisesRegex(top.Blocked, 'identity'):
            top.run(self.req, self.binding, client)
        self.assertEqual(len(client.calls), 1)
    def test_no_writes_or_unimplemented_reads(self):
        for change in ({'op':'write'}, {'action':'metrics_read'}, {'action':'campaign_detect'}, {'platform':'jd'}, {'tenant_id':'other'}):
            client = Fake()
            with self.assertRaises(top.Blocked):
                top.run(dict(self.req, **change), self.binding, client)
            self.assertFalse(client.calls)
    def test_pagination_and_minimization(self):
        result = top.run(self.req, self.binding, Fake(total=41))
        self.assertTrue(result['value']['complete'])
        self.assertEqual(len(result['value']['items']), 41)
        self.assertNotIn('unexpected', result['value']['items'][0])
    def test_cap_is_explicit_partial(self):
        result = top.run(self.req, self.binding, Fake(total=201))
        self.assertFalse(result['value']['complete'])
        self.assertEqual(len(result['value']['items']), 200)
    def test_duplicate_pages_fail(self):
        with self.assertRaisesRegex(top.Blocked, 'pagination'):
            top.run(self.req, self.binding, Fake(total=41, duplicate=True))
    def test_gate_state_and_revocation(self):
        cfg = {'stores': {'test-store':self.binding}, 'authorization': {'valid_until':'2099-01-01T00:00:00Z', 'stores':['test-store'], 'actions':['product_read'], 'targets_by_store':{'test-store':['onsale']}, 'bindings':{'test-store':{'tenant_id':'test','platform':'taobao'}}}, 'adapters':{'test-store':['trusted']}, 'tasks':[dict(self.req, task_id='test')]}
        with sqlite3.connect(':memory:') as db:
            with patch.object(gate, 'call', side_effect=lambda argv, request:top.run(request, self.binding, Fake())) as call:
                self.assertEqual(gate.process(cfg, db)[0]['status'], 'read_verified')
                self.assertEqual(db.execute('select status from tasks_v6').fetchone()[0], 'read_verified')
                cfg['authorization']['revoked'] = True
                self.assertEqual(gate.process(cfg, db)[0]['status'], 'blocked')
                self.assertEqual(call.call_count, 1)
    def test_allowlist_before_network(self):
        with self.assertRaisesRegex(top.Blocked, 'method_not_allowed'):
            top.Client('synthetic', 'synthetic', 'synthetic').call('taobao.item.update')

if __name__ == '__main__':
    unittest.main()
