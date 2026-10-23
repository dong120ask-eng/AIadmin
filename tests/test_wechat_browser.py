"""Isolated fixtures only. No WeChat, credentials, or real draft saves."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from workbench.dispatch import DispatchQueue
from workbench.store import Store, Problem
from workbench.wechat_browser import BrowserDraftWorker
from workbench.wechat_ui import WechatBrowserUI


class FixtureUI:
    verification_mode = 'isolated_fixture'
    def __init__(self, identity='gh_fixture'):
        self.account = identity;self.saves = 0;self.fills = 0;self.closed = False
        self.corrupt = False;self.fail_save = False;self.fail_read = False
    def connect(self,binding):pass
    def identity(self):return self.account
    def fill(self,article,root,guard):
        guard();self.article = article;self.fills += 1
    def save_draft(self,guard):
        guard();self.saves += 1
        if self.fail_save:raise TimeoutError()
        return 'fixture-draft-1'
    def read_draft(self,ref):
        if self.fail_read:raise TimeoutError()
        return {'draft_ref':ref,'account_unique_id':self.account,
                'title':self.article['title'],'body':self.article['body']+('坏' if self.corrupt else ''),
                'assets':self.article['assets'],'reopened_from_list':True}
    def close(self):self.closed = True


class WechatBrowserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.root = Path(self.tmp.name)
        self.store = Store(self.root/'workbench.sqlite3');self.queue = DispatchQueue(self.root/'dispatch.sqlite3')
        self.assets = self.root/'assets';self.assets.mkdir()
        (self.assets/'cover.png').write_bytes(b'isolated image fixture, not production')
        self.project = self.store.create_project('internal',{'product_name':'隔离测试'})
        self.account = self.store.create_account('internal',self.project['id'],
            {'platform':'wechat','external_id':'gh_fixture','display_name':'隔离测试账号'})
        job = self.store.create_job('internal',self.project['id'],{'content_type':'article','topic':'隔离测试','account_id':self.account['id']})
        self.job_id = job['id']
        self.article = {'title':'隔离测试，不对外发布','body':'只用于隔离测试的完整正文，不代表真实业务。'*10,
                        'browser_assets':[{'path':'cover.png','sha256':hashlib.sha256((self.assets/'cover.png').read_bytes()).hexdigest(),'role':'cover'}]}
        self.store.prepare('internal',self.job_id);self.store.claim('internal',self.job_id)
        self.store.finish('internal',self.job_id,{'result.json':json.dumps({'content_type':'article','deliverable_status':'text_draft','payload':self.article})},[])
        self.store.check('internal',self.job_id,dict.fromkeys(['facts','rights','format','ai_label'],True))
        self.binding = {'tenant_id':'internal','project_id':self.project['id'],'account_id':self.account['id'],
                        'account_unique_id':'gh_fixture','channel_id':'wechat-official-draft','route':'browser','profile_ref':'qa-profile'}
        self.worker = BrowserDraftWorker(self.queue,self.store,self.assets)
    def tearDown(self):self.tmp.cleanup()
    def enqueue(self,key='fixture-key',binding=None):
        return self.worker.enqueue('internal',self.job_id,binding or self.binding,key,True)
    def test_fixture_never_counts_as_real_draft(self):
        self.enqueue();ui = FixtureUI();out = self.worker.run('internal','fixture-worker',ui)
        self.assertEqual(out['state'],'test_verified')
        self.assertFalse(out['result']['draft_saved']);self.assertFalse(out['result']['backend_record_verified'])
        self.assertFalse(out['publishing_verified']);self.assertTrue(ui.closed);self.assertEqual(ui.saves,1)
        self.assertEqual(self.store.job('internal',self.job_id)['publish_status'],'not_connected')
    def test_no_authorization(self):
        with self.assertRaises(Problem):self.worker.enqueue('internal',self.job_id,self.binding,'k')
    def test_same_key_is_idempotent(self):
        self.assertEqual(self.enqueue()['id'],self.enqueue()['id'])
    def test_cross_tenant(self):
        binding = {**self.binding,'tenant_id':'other'}
        with self.assertRaises(Problem):self.enqueue(binding=binding)
    def test_cross_account(self):
        with self.assertRaises(Problem):self.enqueue(binding={**self.binding,'account_unique_id':'other'})
    def test_mismatched_profile_account_is_stopped_before_fill(self):
        self.enqueue();ui = FixtureUI('wrong')
        with self.assertRaises(Problem):self.worker.run('internal','w',ui)
        self.assertEqual(ui.fills,0);self.assertEqual(ui.saves,0)
    def test_changed_assets_before_enqueue(self):
        (self.assets/'cover.png').write_bytes(b'changed')
        with self.assertRaises(Problem):self.enqueue()
    def test_changed_assets_after_enqueue(self):
        self.enqueue();(self.assets/'cover.png').write_bytes(b'changed');ui = FixtureUI()
        with self.assertRaises(Problem):self.worker.run('internal','w',ui)
        self.assertEqual(ui.fills,0)
    def test_changed_review_after_enqueue(self):
        self.enqueue()
        self.store.mutate('internal',self.job_id,['checked'],lambda j:j.update(checks={}), 'fixture_changed')
        ui = FixtureUI()
        with self.assertRaises(Problem):self.worker.run('internal','w',ui)
        self.assertEqual(ui.saves,0)
    def test_unknown_save_is_not_retried(self):
        self.enqueue();ui = FixtureUI();ui.fail_save = True
        with self.assertRaises(Problem):self.worker.run('internal','w',ui)
        self.assertEqual(self.queue.tasks('internal')[0]['state'],'unknown')
        self.assertEqual(self.worker.run('internal','w',ui)['status'],'idle');self.assertEqual(ui.saves,1)
    def test_corrupt_readback_quarantined(self):
        self.enqueue();ui = FixtureUI();ui.corrupt = True
        with self.assertRaises(Problem):self.worker.run('internal','w',ui)
        self.assertEqual(self.queue.tasks('internal')[0]['state'],'unknown')
    def test_reconcile_reads_only_known_reference(self):
        task = self.enqueue();ui = FixtureUI();ui.fail_read = True
        with self.assertRaises(Problem):self.worker.run('internal','w',ui)
        ui.fail_read = False
        out = self.worker.reconcile('internal',task['id'],ui,True)
        self.assertEqual(out['state'],'test_verified');self.assertEqual(ui.saves,1)
    def test_reconcile_requires_stopped_process(self):
        task = self.enqueue()
        with self.assertRaises(Problem):self.worker.reconcile('internal',task['id'],FixtureUI())
    def test_no_reference_requires_manual_review(self):
        task = self.enqueue();ui = FixtureUI();ui.fail_save = True
        with self.assertRaises(Problem):self.worker.run('internal','w',ui)
        with self.assertRaises(Problem):self.worker.reconcile('internal',task['id'],ui,True)
        self.assertEqual(ui.saves,1)
    def test_duplicate_content_different_key_is_not_saved_twice(self):
        self.enqueue();ui = FixtureUI();self.worker.run('internal','w',ui)
        self.enqueue('second-key')
        with self.assertRaises(Problem):self.worker.run('internal','w',ui)
        self.assertEqual(ui.saves,1)
    def test_same_profile_serialized(self):
        self.enqueue();self.enqueue('second')
        self.assertIsNotNone(self.queue.claim('internal','w',action='draft'))
        self.assertIsNone(self.queue.claim('internal','w2',action='draft'))
    def test_same_account_across_profiles_serialized(self):
        self.enqueue();self.enqueue('second',binding={**self.binding,'profile_ref':'other-profile'})
        self.assertIsNotNone(self.queue.claim('internal','w',action='draft'))
        self.assertIsNone(self.queue.claim('internal','w2',action='draft'))
    def test_android_worker_cannot_claim_browser_draft(self):
        self.enqueue();self.assertIsNone(self.queue.claim('internal','android-worker'))
    def test_publish_still_blocked(self):
        req = {k:self.binding[k] for k in ['tenant_id','project_id','account_id','channel_id']}
        req.update(content_type='article',publish_mode='auto_publish')
        out = self.queue.enqueue('internal',self.binding,req,'publish-key','publish')
        self.assertEqual(out['state'],'blocked')
        with self.assertRaises(Problem):self.queue.claim('internal','w',action='publish')
    def test_missing_ui_config_fails_closed(self):
        with self.assertRaises(Problem):WechatBrowserUI({},self.root/'profiles')
    def test_no_path_traversal(self):
        self.article['browser_assets'][0]['path'] = '../outside.png'
        def mutate(job):
            from workbench.store import digest
            job['artifacts']['result.json'] = json.dumps({'content_type':'article','deliverable_status':'text_draft','payload':self.article})
            job['artifact_digest'] = digest(job['artifacts'])
            job['checks']['artifact_digest'] = job['artifact_digest']
        self.store.mutate('internal',self.job_id,['checked'],mutate,'fixture')
        with self.assertRaises(Problem):self.enqueue()
    def test_lease_expiry_keeps_both_locks(self):
        self.enqueue();task = self.queue.claim('internal','w',action='draft')
        self.queue.clock = lambda:task['lease_until']+1
        self.assertEqual(self.queue.recover()['marked_unknown'],1)
        with self.queue.transaction() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM dispatch_resources').fetchone()[0],2)
        self.queue.resolve_unknown('internal',task['id'],'隔离测试：旧进程已停止',True)
        with self.queue.transaction() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM dispatch_resources').fetchone()[0],0)

if __name__ == '__main__':unittest.main()
