"""Two isolated synthetic accounts, not real platform authorizations."""
import tempfile
import unittest
from pathlib import Path
from workbench.browser_sessions import Sessions
from workbench.dispatch import DispatchQueue, digest
from workbench.store import Store, Problem

class Fixture:
    def __init__(self,wrong=False,fail=False):self.wrong=wrong;self.fail=fail
    def connect(self,binding,directory):self.binding=binding
    def identity(self):return 'wrong' if self.wrong else self.binding['account_unique_id']
    def read_digest(self):
        if self.fail:raise OSError('fixture interruption')
        return digest('fixture readback')
    def close(self):pass

class BrowserSessionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.now=1000
        self.q=DispatchQueue(root/'dispatch.sqlite3',clock=lambda:self.now)
        self.store=Store(root/'workbench.sqlite3')
        self.s=Sessions(self.q,self.store,root/'profiles')
        self.project=self.store.create_project('internal',{'product_name':'隔离测试'})['id']
        self.bindings=[]
        for i in range(2):
            a=self.store.create_account('internal',self.project,{'platform':'wechat','external_id':'fixture-'+str(i),'display_name':'隔离测试'})
            b={'tenant_id':'internal','project_id':self.project,'account_id':a['id'],
               'account_unique_id':a['external_id'],'channel_id':'wechat-official-draft','route':'browser','profile_ref':'fixture-'+str(i)}
            self.s.register('internal',b,True);self.bindings.append(b)
    def tearDown(self):self.tmp.cleanup()
    def enqueue(self,i=0,key='one'):
        b=self.bindings[i];r={k:b[k] for k in ['tenant_id','project_id','account_id','channel_id']}
        r.update(content_type='article',publish_mode='draft_only')
        return self.s.enqueue('internal',b['profile_ref'],r,key)
    def test_two_accounts_run_with_fixture_evidence(self):
        self.enqueue();self.enqueue(1,'two')
        for _ in range(2):
            r=self.s.run('internal','worker',Fixture())
            self.assertEqual(r['verification'],'isolated_fixture');self.assertFalse(r['publishing_verified'])
        self.assertEqual([t['state'] for t in self.q.tasks('internal')],['test_verified']*2)
    def test_idempotency(self):
        self.assertEqual(self.enqueue()['id'],self.enqueue()['id'])
    def test_profile_and_identity_not_reassignable(self):
        b=dict(self.bindings[1],profile_ref='fixture-0')
        with self.assertRaises(Problem):self.s.register('internal',b,True)
        b=dict(self.bindings[0],profile_ref='new')
        with self.assertRaises(Problem):self.s.register('internal',b,True)
    def test_authorization_and_tenant(self):
        with self.assertRaises(Problem):self.s.register('internal',self.bindings[0])
        with self.assertRaises(Problem):self.s.binding('other','fixture-0')
    def test_wrong_identity_quarantined_other_account_runs(self):
        self.enqueue();self.enqueue(1,'two')
        with self.assertRaises(Problem):self.s.run('internal','worker',Fixture(wrong=True))
        self.assertEqual(self.s.run('internal','worker',Fixture())['verification'],'isolated_fixture')
        self.assertEqual(self.q.tasks('internal')[0]['state'],'unknown')
    def test_restart_expiry_and_explicit_resolution(self):
        task=self.enqueue();claimed=self.q.claim('internal','old',5,action='browser_read')
        self.now+=6
        q=DispatchQueue(self.q.path,clock=lambda:self.now);self.assertEqual(q.recover()['marked_unknown'],1)
        self.assertIsNone(q.claim('internal','new',action='browser_read'))
        with self.assertRaises(Problem):q.heartbeat('internal',task['id'],claimed['lease_token'])
        with self.assertRaises(Problem):q.resolve_unknown('internal',task['id'],'fixture checked')
        q.resolve_unknown('internal',task['id'],'fixture checked',True)
        self.assertEqual(q.tasks('internal')[0]['state'],'cancelled')
    def test_concurrency_limit_and_profile_exclusion(self):
        self.enqueue();self.enqueue(1,'two');self.enqueue(0,'three')
        a=self.q.claim('internal','w1',action='browser_read',max_browser_sessions=1)
        self.assertIsNotNone(a);self.assertIsNone(self.q.claim('internal','w2',action='browser_read',max_browser_sessions=1))
        self.assertIsNotNone(self.q.claim('internal','w2',action='browser_read'))
        self.assertIsNone(self.q.claim('internal','w3',action='browser_read'))
    def test_interruption_not_retried(self):
        self.enqueue()
        with self.assertRaises(Problem):self.s.run('internal','w',Fixture(fail=True))
        self.assertEqual(self.s.run('internal','w',Fixture())['status'],'idle')
    def test_worker_selects_only_its_profile(self):
        self.enqueue();self.enqueue(1,'two')
        port=Fixture();port.config={'profile_ref':'fixture-1'}
        self.s.run('internal','w',port)
        self.assertEqual(self.q.tasks('internal')[0]['state'],'queued')
    def test_revocation_blocks_execution(self):
        self.enqueue()
        with self.q.transaction() as db:
            db.execute("UPDATE browser_sessions SET state='revoked' WHERE profile='fixture-0'")
        with self.assertRaises(Problem):self.s.run('internal','w',Fixture())
        with self.assertRaises(Problem):self.s.binding('internal','fixture-0')

    def test_profile_symlink_refused(self):
        target=self.s.root/'elsewhere';target.mkdir()
        (self.s.root/'fixture-0').symlink_to(target,target_is_directory=True)
        self.enqueue()
        with self.assertRaises(Problem):self.s.run('internal','w',Fixture())

class ReadOnlyPortTests(unittest.TestCase):
    def port(self):
        from unittest.mock import Mock
        from workbench.browser_sessions import ReadOnlyBrowser
        p=ReadOnlyBrowser({'profile_ref':'qa','identity_selector':'#identity','read_selector':'#summary','verified_at':'fixture'})
        p.origin=('https','mp.weixin.qq.com',443);p.page=Mock();p.page.url='https://mp.weixin.qq.com/'
        p.page.locator.return_value.count.return_value=1
        p.page.locator.return_value.inner_text.return_value='fixture-account'
        return p
    def test_official_origin_only(self):
        p=self.port();p.page.url='https://mp.weixin.qq.com.evil.example/'
        with self.assertRaises(Problem):p.identity()
    def test_nonunique_or_login_wall_fails(self):
        p=self.port();p.page.locator.return_value.count.return_value=0
        with self.assertRaises(Problem):p.identity()
    def test_readback_only_returns_hash(self):
        p=self.port();self.assertEqual(p.read_digest(),digest('fixture-account'))
        p.page.locator.return_value.click.assert_not_called()
    def test_empty_identity_fails(self):
        p=self.port();p.page.locator.return_value.inner_text.return_value=' '
        with self.assertRaises(Problem):p.identity()
