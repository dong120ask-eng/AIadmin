"""Synthetic fixtures only. No merchant credentials or live platform requests."""
import base64
import csv
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workbench.ecommerce import Operations, FIELDS, PROFIT, analyze, metadata, table
from workbench.server import make_server
from workbench.store import Problem, Store


def meta():
    clock = datetime.now(timezone.utc)
    return {"store_id": "合成测试店/测试仓", "source": "unittest合成，非真实业务", "platform": "京东", "kind": "test", "exported_at": clock.isoformat(), "period_start": (clock-timedelta(days=11)).isoformat(), "period_end": (clock-timedelta(days=1)).isoformat(), "metric_definition": "合成同区间数据，单位件，CNY"}


def row(**kw):
    return {"record_id": "r1", "sku": "001", "on_hand": "25", "reserved": "3", "safety": "2", "sales_units": "100", "lead_days": "3", **kw}


def payload(rows=None, m=None):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows if rows is not None else [row()])
    return {"filename": "测试.csv", "content_base64": base64.b64encode(stream.getvalue().encode()).decode(), "metadata": m or meta()}


def xlsx_fixture(formula=False, shared=False):
    # Minimal synthetic OOXML fixture for importer validation, not a user workbook.
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    cells = []
    for i, key in enumerate(list(FIELDS)[:7]):
        cells.append(f'<c r="{chr(65+i)}1" t="inlineStr"><is><t>{FIELDS[key]}</t></is></c>')
    values = []
    for i, value in enumerate(row().values()):
        values.append(f'<c r="{chr(65+i)}2" t="inlineStr"><is><t>{value}</t></is>'+('<f>1+1</f>' if formula and i == 2 else '')+'</c>')
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as z:
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="data" sheetId="1" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="{ns}"><sheetData><row>{"".join(cells)}</row><row>{"".join(values)}</row></sheetData></worksheet>')
    return raw.getvalue()


class EcommerceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'workbench.db'
        self.ops = Operations(Store(self.path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_inventory_price_purchase_and_profit(self):
        r = row(unit_price='9', price_floor='10', purchase_price='5', contract_price='4', purchase_qty='5', **dict(zip(PROFIT,['100','0','70','5','30','10','0','0'])))
        a = analyze([r], metadata(meta()))
        self.assertEqual(a['quality']['errors'], [])
        v = a['results'][0]
        self.assertEqual((v['available'],v['coverage_days'],v['suggested_purchase']), (20,'2.00',10))
        self.assertEqual(v['profit'], '-15.00')
        self.assertEqual(a['summary']['covered_contribution_profit'],'-15.00')
        self.assertEqual({x['kind'] for x in a['alerts']}, {'库存','售价','采购价','采购量','经营'})

    def test_zero_sales_and_missing_cost_not_zero_profit(self):
        a = analyze([row(sales_units='0')], metadata(meta()))
        self.assertIsNone(a['results'][0]['coverage_days'])
        self.assertIsNone(a['results'][0]['profit'])
        self.assertIsNone(a['summary']['covered_contribution_profit'])
        self.assertEqual(a['summary']['profit_missing_rows'],1)

    def test_bad_rows_block_entire_batch_and_record_issue(self):
        for field, bad in [('on_hand','-1'),('sales_units','1.5'),('lead_days','NaN'),('unit_price','Infinity'),('unit_price','1e-999999')]:
            with self.subTest(field=field,bad=bad):
                a = analyze([row(**{field:bad})], metadata(meta()))
                self.assertTrue(a['quality']['errors'])
                self.assertEqual(a['results'],[])
        result = self.ops.ingest(payload([row(),row(record_id='r2')]))
        self.assertEqual(result['quality_status'],'blocked')
        self.assertEqual(result['issues'][0]['kind'],'数据质量')

    def test_stale_future_period_and_blank_record(self):
        for changes in [{'exported_at':(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()}, {'period_end':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}, {'exported_at':'2026-01-01T00:00:00'}]:
            a = analyze([row()], metadata({**meta(),**changes}))
            self.assertEqual(a['quality']['status'],'blocked')
        self.assertEqual(analyze([row(record_id='')], metadata(meta()))['quality']['status'],'blocked')
        m=meta();m['exported_at']=m['period_start']
        self.assertIn('统计结束时间晚于导出时间',analyze([row()],metadata(m))['quality']['errors'])

    def test_import_idempotency_persistence_and_source_identity(self):
        p=payload()
        a=self.ops.ingest(p);b=self.ops.ingest(p)
        self.assertEqual(a['id'],b['id'])
        self.assertEqual(len(self.ops.imports()),1)
        restarted=Operations(Store(self.path))
        self.assertEqual(restarted.get(a['id'])['source_sha256'],a['source_sha256'])
        p['metadata']['kind']='demo'
        other=self.ops.ingest(p)
        self.assertNotEqual(other['id'],a['id'])
        self.assertEqual(other['metadata']['kind'],'demo')
        self.assertEqual(restarted.get(a['id'])['metadata']['kind'],'test')

    def test_issue_closure_history_conflict_and_export_scope(self):
        a=self.ops.ingest(payload([row(sku='=HYPERLINK("bad")')]))
        issue=a['issues'][0]
        with self.assertRaises(Problem):
            self.ops.update_issue(issue['id'],{'state':'已关闭','version':0})
        updated=self.ops.update_issue(issue['id'],{'state':'已关闭','version':0,'owner':'测试人','note':'合成核查备注'})
        self.assertEqual(updated['version'],1)
        with self.assertRaises(Problem) as caught:
            self.ops.update_issue(issue['id'],{'state':'处理中','version':0})
        self.assertEqual(caught.exception.status,409)
        other=payload([row(sku='PRIVATE_OTHER')]);other['metadata']['kind']='demo';self.ops.ingest(other)
        z=zipfile.ZipFile(io.BytesIO(self.ops.export(a['id'])))
        self.assertEqual(set(z.namelist()),{'report.md','analysis.json','results.csv','issue-history.json'})
        self.assertNotIn('PRIVATE_OTHER',z.read('analysis.json').decode())
        self.assertIn("'=HYPERLINK",z.read('results.csv').decode('utf-8-sig'))
        self.assertEqual(len(json.loads(z.read('issue-history.json'))),1)
        self.assertIn('模拟测试',z.read('report.md').decode())
        with self.assertRaises(Problem):self.ops.get('../other')

    def test_csv_header_mapping_encoding_and_shape(self):
        raw=base64.b64decode(payload()['content_base64'])
        decoded=raw.decode()
        for k,v in FIELDS.items():decoded=decoded.replace(k,v)
        self.assertEqual(table('数据.csv',decoded.encode('gb18030'))[0]['sku'],'001')
        for raw in [b'sku,sku\na,b', b'sku\na', b'bad\na',b'']:
            with self.assertRaises(Problem):table('x.csv',raw)
        with self.assertRaises(Problem):table('x.xls',b'bad')
        with self.assertRaises(Problem):self.ops.ingest({**payload(),'content_base64':'!bad'})

    def test_xlsx_values_and_formula_rejection(self):
        rows=table('test.xlsx',xlsx_fixture())
        self.assertEqual(rows,[row()])
        self.assertEqual(analyze(rows,metadata(meta()))['results'][0]['available'],20)
        with self.assertRaises(Problem):table('test.xlsx',xlsx_fixture(formula=True))
        with self.assertRaises(Problem):table('test.xlsx',b'not a zip')

    def test_demo_is_explicit_and_never_real(self):
        self.assertEqual(self.ops.imports(), [])
        result = self.ops.demo()
        self.assertEqual(result['metadata']['kind'], 'demo')
        self.assertEqual(result['analysis']['summary'], {'sku_count': 3, 'alert_count': 6, 'profit_rows': 2, 'profit_missing_rows': 1, 'covered_net_revenue': '1100.00', 'covered_contribution_profit': '305.00'})
        self.assertIn('非真实店铺', result['metadata']['source'])

    def test_saved_analysis_is_blocked_when_snapshot_becomes_stale(self):
        result = self.ops.ingest(payload())
        with patch('workbench.ecommerce.datetime', wraps=datetime) as clock:
            clock.now.return_value = datetime.now(timezone.utc) + timedelta(days=8)
            later = self.ops.get(result['id'])
        self.assertEqual(later['quality_status'], 'blocked')
        self.assertEqual(later['analysis']['results'], [])
        self.assertEqual(len(later['issues']), len(result['issues']))

    def test_cross_store_records_not_aggregated(self):
        a=self.ops.ingest(payload())
        p=payload();p['metadata']['store_id']='另一家合成店'
        b=self.ops.ingest(p)
        self.assertNotEqual(a['id'],b['id'])
        self.assertEqual(a['analysis']['summary']['sku_count'],1)
        self.assertEqual(self.ops.get(a['id'])['rows'][0]['on_hand'],'25')


class EcommerceHTTPTests(unittest.TestCase):
    def test_http_import_export_guard_and_no_write_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            server=make_server(Store(Path(tmp)/'workbench.db'),0,capabilities={},homepage='ecommerce.html')
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            def request(path,body=None,token=None,origin=None):
                headers={}
                if token:headers['X-Workbench-Token']=token
                if origin:headers['Origin']=origin
                if body is not None:headers['Content-Type']='application/json'
                return urllib.request.urlopen(urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers))
            try:
                with request('/') as r:
                    self.assertIn('导入经营数据',r.read().decode())
                    self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
                with request('/api/ecommerce/config') as r:token=json.load(r)['token']
                for tok,origin in [(None,None),(token,'https://evil.invalid')]:
                    with self.assertRaises(urllib.error.HTTPError) as caught:request('/api/ecommerce/imports',payload(),tok,origin)
                    self.assertEqual(caught.exception.code,403)
                with request('/api/ecommerce/imports',payload(),token) as r:data=json.load(r)
                with request('/api/ecommerce/imports/'+data['id']+'/export') as r:
                    self.assertEqual(r.headers.get_content_type(),'application/zip')
                    self.assertIsNone(zipfile.ZipFile(io.BytesIO(r.read())).testzip())
                for path in ['/api/ecommerce/purchase','/api/ecommerce/publish','/api/ecommerce/price','/api/ecommerce/inventory']:
                    with self.assertRaises(urllib.error.HTTPError) as caught:request(path,{},token)
                    self.assertEqual(caught.exception.code,404)
            finally:
                server.shutdown();thread.join();server.server_close()


if __name__=='__main__':unittest.main()
