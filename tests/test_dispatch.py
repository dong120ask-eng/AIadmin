import hashlib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from workbench.dispatch import DispatchQueue
from workbench.store import Problem

class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.now=1000.;self.queue=DispatchQueue(self.root/'queue.sqlite3',clock=lambda:self.now)
    def tearDown(self):self.temp.cleanup()
    def binding(self,account='a1',device='emulator-5554',tenant='internal'):
        return {'tenant_id':tenant,'project_id':'p1','account_id':account,'account_unique_id':'qa-'+account,
                'channel_id':'taobao-guanghe','route':'android_emulator','device_udid':device,'app_package':'com.example.qa'}
    def request(self,account='a1',tenant='internal'):
        return {'tenant_id':tenant,'project_id':'p1','account_id':account,'channel_id':'taobao-guanghe','content_type':'short_video','publish_mode':'draft_only'}
    def enqueue(self,key='key1',account='a1',device='emulator-5554',tenant='internal',action='inspect_only'):
        return self.queue.enqueue(tenant,self.binding(account,device,tenant),self.request(account,tenant),key,action)
    def artifact(self,task):
        relative=f'device-inspections/{task}/source.xml';p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('<hierarchy>QA only</hierarchy>')
        return {'relative_path':relative,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    def test_idempotent_enqueue_and_conflicting_payload(self):
        first=self.enqueue();self.assertEqual(self.enqueue()['id'],first['id'])
        with self.assertRaises(Problem):self.enqueue(account='a2')
    def test_cross_tenant_binding_rejected(self):
        with self.assertRaises(Problem):self.queue.enqueue('other',self.binding(),self.request(),'key')
    def test_same_device_serialized_even_with_other_accounts(self):
        first=self.enqueue();self.enqueue('key2','a2')
        claimed=self.queue.claim('internal','w1');self.assertEqual(claimed['id'],first['id'])
        self.assertIsNone(self.queue.claim('internal','w2'))
        self.queue.finish_inspection('internal',first['id'],claimed['lease_token'],self.artifact(first['id']))
        self.assertIsNotNone(self.queue.claim('internal','w2'))
    def test_independent_devices_can_run(self):
        self.enqueue();self.enqueue('key2','a2','emulator-5556')
        self.assertIsNotNone(self.queue.claim('internal','w1'));self.assertIsNotNone(self.queue.claim('internal','w2'))
    def test_physical_resource_locked_across_tenants(self):
        self.enqueue();self.enqueue('key2','a2',tenant='other')
        self.queue.claim('internal','w1');self.assertIsNone(self.queue.claim('other','w2'))
    def test_concurrent_claims_only_one_owner(self):
        self.enqueue()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda w:self.queue.claim('internal',w),['w1','w2']))
        self.assertEqual(sum(r is not None for r in results),1)
    def test_interrupted_lease_quarantines_device_after_restart(self):
        self.enqueue();self.enqueue('key2','a2');claimed=self.queue.claim('internal','w1',5)
        self.now+=6;restarted=DispatchQueue(self.root/'queue.sqlite3',clock=lambda:self.now)
        self.assertEqual(restarted.recover()['marked_unknown'],1)
        self.assertIsNone(restarted.claim('internal','w2'))
        self.assertEqual(restarted.tasks('internal')[0]['state'],'unknown')
        with self.assertRaises(Problem):restarted.heartbeat('internal',claimed['id'],claimed['lease_token'])
    def test_resolution_requires_stopped_worker_and_does_not_requeue(self):
        self.enqueue();claimed=self.queue.claim('internal','w1');self.queue.mark_unknown('internal',claimed['id'],claimed['lease_token'])
        with self.assertRaises(Problem):self.queue.resolve_unknown('internal',claimed['id'],'检查完成')
        resolved=self.queue.resolve_unknown('internal',claimed['id'],'QA：旧进程已停止，未执行任何发布',True)
        self.assertEqual(resolved['state'],'cancelled');self.assertIsNone(self.queue.claim('internal','w2'))
    def test_old_or_wrong_worker_cannot_finish(self):
        self.enqueue();claimed=self.queue.claim('internal','w1')
        with self.assertRaises(Problem):self.queue.finish_inspection('internal',claimed['id'],'wrong',self.artifact(claimed['id']))
    def test_changed_artifact_rejected(self):
        self.enqueue();claimed=self.queue.claim('internal','w1');artifact=self.artifact(claimed['id'])
        (self.root/artifact['relative_path']).write_text('changed')
        with self.assertRaises(Problem):self.queue.finish_inspection('internal',claimed['id'],claimed['lease_token'],artifact)
    def test_wrong_artifact_path_rejected(self):
        self.enqueue();claimed=self.queue.claim('internal','w1')
        with self.assertRaises(Problem):self.queue.finish_inspection('internal',claimed['id'],claimed['lease_token'],{'relative_path':'../outside','sha256':'x'})
    def test_draft_and_publish_stay_blocked(self):
        for action in ['draft','publish']:
            row=self.enqueue(action,action=action)
            self.assertEqual(row['state'],'blocked');self.assertFalse(row['publishing_verified'])
        self.assertIsNone(self.queue.claim('internal','w1'))
    def test_credentials_and_unapproved_commands_rejected(self):
        request=self.request();request['command']='arbitrary'
        with self.assertRaises(Problem):self.queue.enqueue('internal',self.binding(),request,'key')
    def test_lists_are_tenant_scoped_and_hide_lease(self):
        first=self.enqueue();self.enqueue('key2',tenant='other');self.queue.claim('internal','w1')
        rows=self.queue.tasks('internal');self.assertEqual([r['id'] for r in rows],[first['id']]);self.assertNotIn('lease_token',rows[0])
    def test_heartbeat_extends_only_current_owner(self):
        self.enqueue();claimed=self.queue.claim('internal','w1',5);self.now+=4
        self.queue.heartbeat('internal',claimed['id'],claimed['lease_token'],5);self.now+=2
        self.assertEqual(self.queue.recover()['marked_unknown'],0)
        with self.assertRaises(Problem):self.queue.heartbeat('internal',claimed['id'],'wrong',5)
    def test_actual_protocol_worker_saves_local_source_without_publishing(self):
        from tests.test_android import AndroidTransportTests
        fixture=AndroidTransportTests('test_session_and_read_only_source');fixture.setUp()
        try:
            self.enqueue();result=self.queue.inspect_next('internal','w1',fixture.url)
            self.assertEqual(result['state'],'inspected');self.assertFalse(result['publishing_verified'])
            self.assertTrue((self.root/result['result']['relative_path']).is_file())
            self.assertEqual([r[0] for r in fixture.requests],['POST','GET','DELETE'])
        finally:fixture.tearDown()
    def test_worker_connection_failure_retains_quarantine(self):
        from unittest.mock import patch
        self.enqueue()
        with patch('workbench.dispatch.AndroidInspector.connect',side_effect=Problem('QA failure')):
            with self.assertRaises(Problem):self.queue.inspect_next('internal','w1')
        self.assertEqual(self.queue.tasks('internal')[0]['state'],'unknown')
        self.enqueue('key2','a2');self.assertIsNone(self.queue.claim('internal','w2'))
