"""Shared real SQLite, isolated ports/local output fixtures; no model or platform calls."""
import hashlib
import itertools
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from workbench.browser_sessions import Sessions
from workbench.dispatch import DispatchQueue
from workbench.manager import ManagerQueue, TENANT
from workbench.store import Problem, Store
from workbench.wechat_browser import BrowserDraftWorker
from workbench.wechat_session import ProfileLease
from tests.test_browser_sessions import Fixture as ReadFixture
from tests.test_wechat_browser import FixtureUI as DraftFixture


class SharedQueue:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.now = 1000
        self.manager = ManagerQueue(root/'queue.db', clock=lambda: self.now)
        # Independent connections to exactly the same dispatch database.
        self.q = DispatchQueue(self.manager.path, clock=lambda: self.now)
        self.store = Store(root/'workbench.db')
        self.sessions = Sessions(self.q, self.store, root/'profiles')
        self.assets = root/'assets'; self.assets.mkdir()
        (self.assets/'cover.png').write_bytes(b'isolated fixture only')
        self.drafts = BrowserDraftWorker(
            DispatchQueue(self.q.path, clock=lambda: self.now), self.store, self.assets)
        self.project = self.store.create_project(TENANT, {'product_name': '跨模块隔离测试'})['id']
        self.bindings = []
        for i in range(3):
            account = self.store.create_account(TENANT, self.project, {
                'platform': 'wechat', 'external_id': 'synthetic-'+str(i), 'display_name': '隔离测试'})
            binding = {'tenant_id': TENANT, 'project_id': self.project,
                       'account_id': account['id'], 'account_unique_id': account['external_id'],
                       'channel_id': 'wechat-official-draft', 'route': 'browser',
                       'profile_ref': 'synthetic-profile-'+str(i)}
            self.sessions.register(TENANT, binding, True)
            self.bindings.append(binding)
        self.job = self.store.create_job(TENANT, self.project, {
            'content_type': 'article', 'topic': '隔离测试',
            'account_id': self.bindings[0]['account_id']})['id']
        article = {'title': '隔离测试不对外发布', 'body': '这是合成的跨模块队列测试正文。'*12,
                   'browser_assets': [{'path': 'cover.png', 'role': 'cover',
                    'sha256': hashlib.sha256((self.assets/'cover.png').read_bytes()).hexdigest()}]}
        self.store.prepare(TENANT, self.job); self.store.claim(TENANT, self.job)
        self.store.finish(TENANT, self.job, {'result.json': json.dumps({
            'content_type': 'article', 'deliverable_status': 'text_draft', 'payload': article})}, [])
        self.store.check(TENANT, self.job, dict.fromkeys(['facts','rights','format','ai_label'], True))

    def enqueue(self, kind, key=None, index=1, binding=None):
        key = key or kind
        if kind == 'local_file':
            return self.manager.submit('创建文件 hello.txt，内容为跨模块测试', key)
        if kind == 'draft':
            return self.drafts.enqueue(TENANT, self.job, binding or self.bindings[0], key, True)
        b = self.bindings[index]
        req = {k: b[k] for k in ('tenant_id','project_id','account_id','channel_id')}
        req.update(content_type='article', publish_mode='draft_only')
        return self.sessions.enqueue(TENANT, b['profile_ref'], req, key)

    def claim(self, task, worker='qa', **kwargs):
        return self.q.claim(TENANT, worker, action=task['action'], expected_task=task['id'], **kwargs)

    def state(self, task):
        return next(t['state'] for t in self.q.tasks(TENANT) if t['id']==task['id'])

    def locks(self):
        with self.q.transaction() as db:
            return dict(db.execute('SELECT resource,task_id FROM dispatch_resources').fetchall())

    def revoke(self, index=1):
        with self.q.transaction() as db:
            db.execute("UPDATE browser_sessions SET state='revoked' WHERE profile=?",
                       (self.bindings[index]['profile_ref'],))

    def port(self, index=1, **kwargs):
        port = ReadFixture(**kwargs)
        port.config = {'profile_ref': self.bindings[index]['profile_ref']}
        return port

    def run_manager(self, task, **kwargs):
        def output(args, **kw):
            (kw['cwd']/'hello.txt').write_bytes('跨模块测试'.encode())
            return 0, 'untrusted fixture text'
        with patch('workbench.manager.codex_binary', return_value='isolated-fixture'), \
                patch('workbench.manager.invoke', side_effect=output) as invoke:
            result = self.manager.run_next(True, True, task_id=task['id'], **kwargs)
            assert invoke.call_count == 1
            return result


class DispatchIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.h = SharedQueue(self.root/'shared')

    def test_three_task_types_all_six_enqueue_orders(self):
        for n, order in enumerate(itertools.permutations(['local_file','draft','browser_read'])):
            with self.subTest(order=order):
                h = SharedQueue(self.root/str(n))
                tasks = {kind: h.enqueue(kind) for kind in order}
                self.assertIsNone(h.q.claim(TENANT, 'android'))
                self.assertEqual(h.run_manager(tasks['local_file'])['state'], 'checked')
                draft = h.drafts.run(TENANT, 'draft-worker', DraftFixture('synthetic-0'))
                read = h.sessions.run(TENANT, 'read-worker', h.port())
                self.assertEqual(draft['state'], 'test_verified')
                self.assertFalse(draft['result']['draft_saved'])
                self.assertEqual(read['verification'], 'isolated_fixture')
                self.assertFalse(read['publishing_verified'])
                self.assertEqual(h.locks(), {})
                self.assertEqual(h.state(tasks['browser_read']), 'test_verified')

    def test_concurrent_workers_share_global_cap_and_local_work_is_independent(self):
        h = self.h
        tasks = [h.enqueue('draft'), h.enqueue('browser_read'), h.enqueue('local_file')]
        barrier = threading.Barrier(3)
        def claim(pair):
            i, task = pair
            barrier.wait(timeout=5)
            q = DispatchQueue(h.q.path, clock=lambda: h.now)
            return q.claim(TENANT, 'worker-'+str(i), action=task['action'], expected_task=task['id'])
        with ThreadPoolExecutor(max_workers=3) as pool:
            result = list(pool.map(claim, enumerate(tasks)))
        self.assertEqual([r['id'] for r in result], [t['id'] for t in tasks])
        third = h.enqueue('browser_read', 'third', index=2)
        self.assertIsNone(h.claim(third))
        self.assertEqual(len(h.locks()), 5)  # two Profiles, two account aliases, one local resource

    def test_local_requires_exact_task_and_filters_are_intersected(self):
        h = self.h
        browser = h.enqueue('browser_read'); first = h.enqueue('local_file')
        second = h.enqueue('local_file', 'second')
        with self.assertRaises(Problem): h.q.claim(TENANT, 'w', action='local_file')
        self.assertIsNone(h.q.claim(TENANT, 'w', expected_task=first['id']))
        self.assertIsNone(h.q.claim(TENANT, 'w', action='local_file', expected_task=browser['id']))
        self.assertIsNone(h.q.claim('other', 'w', action='local_file', expected_task=second['id']))
        claimed = h.claim(second)
        self.assertEqual(claimed['id'], second['id'])
        self.assertEqual(h.state(first), 'queued'); self.assertEqual(h.state(browser), 'queued')
        self.assertIsNone(h.claim(second)); self.assertIsNone(h.claim(first))

    def test_manager_rejects_browser_id_without_claim_or_model_call(self):
        h = self.h
        browser = h.enqueue('browser_read'); local = h.enqueue('local_file')
        with patch('workbench.manager.codex_binary', return_value='fixture'), \
                patch('workbench.manager.invoke') as invoke:
            with self.assertRaises(Problem): h.manager.run_next(True, True, task_id=browser['id'])
            invoke.assert_not_called()
        self.assertEqual(h.state(browser), 'queued'); self.assertEqual(h.state(local), 'queued')
        self.assertEqual(h.locks(), {})

    def test_consumed_or_cancelled_authorization_never_falls_back(self):
        h = self.h
        first = h.enqueue('local_file'); second = h.enqueue('local_file', 'next')
        claimed = h.claim(first)
        h.q.mark_unknown(TENANT, first['id'], claimed['lease_token'])
        h.q.resolve_unknown(TENANT, first['id'], '合成测试：已停止旧进程', True)
        with patch('workbench.manager.codex_binary', return_value='fixture'), \
                patch('workbench.manager.invoke') as invoke:
            with self.assertRaises(Problem): h.manager.run_next(True, True, task_id=first['id'])
            invoke.assert_not_called()
        self.assertEqual(h.state(second), 'queued')
        self.assertEqual(h.run_manager(second)['state'], 'checked')

    def test_manager_authorization_flags_still_required_with_shared_queue(self):
        h = self.h; task = h.enqueue('local_file'); h.enqueue('draft'); h.enqueue('browser_read')
        with patch('workbench.manager.invoke') as invoke:
            for flags in [(False,True),(True,False),(False,False)]:
                with self.assertRaises(Problem): h.manager.run_next(*flags, task_id=task['id'])
            invoke.assert_not_called()
        self.assertTrue(all(t['state']=='queued' for t in h.q.tasks(TENANT)))
        self.assertEqual(h.locks(), {})

    def test_profile_and_exact_id_never_fall_back(self):
        h = self.h
        first = h.enqueue('browser_read'); second = h.enqueue('browser_read', 'second', index=2)
        self.assertIsNone(h.claim(first, profile_ref=h.bindings[2]['profile_ref']))
        claimed = h.q.claim(TENANT, 'w', action='browser_read', profile_ref=h.bindings[2]['profile_ref'])
        self.assertEqual(claimed['id'], second['id']); self.assertEqual(h.state(first), 'queued')

    def test_draft_worker_selects_its_configured_profile(self):
        h = self.h
        first = h.enqueue('draft')
        second = h.enqueue('draft', 'second', binding={**h.bindings[0], 'profile_ref':'alternate'})
        port = DraftFixture('synthetic-0'); port.config = {'profile_ref':'alternate'}
        self.assertEqual(h.drafts.run(TENANT, 'w', port)['id'], second['id'])
        self.assertEqual(h.state(first), 'queued')

    def test_same_profile_across_draft_and_read_is_exclusive(self):
        h = self.h
        draft = h.enqueue('draft'); read = h.enqueue('browser_read', index=0)
        h.claim(draft)
        self.assertIsNone(h.claim(read))
        self.assertEqual(h.state(read), 'queued')

    def test_same_account_alias_across_distinct_profiles_is_exclusive(self):
        h = self.h
        draft = h.enqueue('draft', binding={**h.bindings[0], 'profile_ref':'alternate'})
        read = h.enqueue('browser_read', index=0)
        h.claim(read)
        self.assertIsNone(h.claim(draft))
        self.assertEqual(h.state(draft), 'queued')

    def test_cap_one_includes_draft_and_is_global_across_tenants(self):
        h = self.h
        draft = h.enqueue('draft'); read = h.enqueue('browser_read')
        h.claim(draft)
        self.assertIsNone(h.claim(read, max_browser_sessions=1))
        project = h.store.create_project('other', {'product_name':'其他企业隔离测试'})['id']
        account = h.store.create_account('other', project, {
            'platform':'wechat', 'external_id':'other-synthetic', 'display_name':'其他企业'})
        binding = {**h.bindings[2], 'tenant_id':'other', 'project_id':project,
                   'account_id':account['id'], 'account_unique_id':account['external_id'],
                   'profile_ref':'other-profile'}
        h.sessions.register('other', binding, True)
        request = {k:binding[k] for k in ('tenant_id','project_id','account_id','channel_id')}
        request.update(content_type='article', publish_mode='draft_only')
        other = h.sessions.enqueue('other', binding['profile_ref'], request, 'other-read')
        self.assertIsNone(h.q.claim('other', 'w', action='browser_read', max_browser_sessions=1))
        local = h.enqueue('local_file')
        self.assertIsNotNone(h.claim(local, max_browser_sessions=1))
        self.assertIsNotNone(h.q.claim('other', 'w2', action='browser_read',
                                     expected_task=other['id'], max_browser_sessions=2))

    def test_revoked_session_cannot_connect_but_other_modules_continue(self):
        h = self.h; read = h.enqueue('browser_read'); local = h.enqueue('local_file'); h.enqueue('draft')
        h.revoke()
        port = h.port()
        with patch.object(port, 'connect', wraps=port.connect) as connect:
            with self.assertRaises(Problem): h.sessions.run(TENANT, 'w', port)
            connect.assert_not_called()
        self.assertEqual(h.state(read), 'unknown')
        self.assertEqual(h.run_manager(local)['state'], 'checked')
        self.assertEqual(h.drafts.run(TENANT, 'draft', DraftFixture('synthetic-0'))['state'], 'test_verified')

    def test_revocation_during_read_cannot_commit(self):
        h = self.h; read = h.enqueue('browser_read'); port = h.port()
        original = port.read_digest
        def revoke(): h.revoke(); return original()
        port.read_digest = revoke
        with self.assertRaises(Problem): h.sessions.run(TENANT, 'w', port)
        self.assertEqual(h.state(read), 'unknown')
        self.assertEqual(len(h.locks()), 2)

    def test_revocation_after_close_is_checked_in_commit_transaction(self):
        h = self.h; read = h.enqueue('browser_read'); port = h.port()
        port.close = h.revoke
        with self.assertRaises(Problem): h.sessions.run(TENANT, 'w', port)
        self.assertEqual(h.state(read), 'unknown')
        self.assertEqual(len(h.locks()), 2)

    def test_expiry_restart_retains_all_resources_and_fences_all_old_workers(self):
        h = self.h
        tasks = [h.enqueue('local_file'), h.enqueue('draft'), h.enqueue('browser_read')]
        claims = [h.claim(t, lease_seconds=5) for t in tasks]
        h.now += 6
        restarted = DispatchQueue(h.q.path, clock=lambda: h.now)
        self.assertEqual(restarted.recover()['marked_unknown'], 3)
        self.assertEqual(len(h.locks()), 5)
        for task, claimed in zip(tasks, claims):
            with self.subTest(action=task['action']):
                with self.assertRaises(Problem): restarted.heartbeat(TENANT, task['id'], claimed['lease_token'])
                with self.assertRaises(Problem): restarted.mark_unknown(TENANT, task['id'], claimed['lease_token'])
                with self.assertRaises(Problem): restarted.resolve_unknown(TENANT, task['id'], '未停止旧进程')
        self.assertIsNone(h.claim(h.enqueue('browser_read', 'third', index=2)))
        for task in tasks:
            restarted.resolve_unknown(TENANT, task['id'], '合成测试：旧进程已停止并核查', True)
        self.assertEqual(h.locks(), {})
        with self.assertRaises(Problem): h.manager.complete(tasks[0]['id'], claims[0]['lease_token'], {})
        self.assertTrue(all(h.state(t)=='cancelled' for t in tasks))

    def test_timeout_during_read_keeps_profile_but_local_work_can_finish(self):
        h = self.h; read = h.enqueue('browser_read'); local = h.enqueue('local_file')
        port = h.port(); original = port.read_digest
        def slow(): h.now += 121; return original()
        port.read_digest = slow
        with self.assertRaises(Problem): h.sessions.run(TENANT, 'w', port)
        self.assertEqual(h.state(read), 'unknown'); self.assertEqual(len(h.locks()), 2)
        self.assertEqual(h.run_manager(local)['state'], 'checked')

    def test_timeout_during_draft_readback_cannot_release_locks(self):
        h = self.h; draft = h.enqueue('draft'); port = DraftFixture('synthetic-0')
        original = port.read_draft
        def slow(ref): h.now += 121; return original(ref)
        port.read_draft = slow
        with self.assertRaises(Problem): h.drafts.run(TENANT, 'w', port)
        self.assertEqual(h.state(draft), 'unknown'); self.assertEqual(len(h.locks()), 2)
        self.assertEqual(port.saves, 1)
        self.assertEqual(h.drafts.run(TENANT, 'w', port)['status'], 'idle')

    def test_wrong_browser_identity_isolated_and_other_account_can_run(self):
        h = self.h; bad = h.enqueue('browser_read'); good = h.enqueue('browser_read', 'good', index=2)
        with self.assertRaises(Problem): h.sessions.run(TENANT, 'w', h.port(wrong=True))
        self.assertEqual(h.state(bad), 'unknown')
        self.assertEqual(h.sessions.run(TENANT, 'w2', h.port(2))['verification'], 'isolated_fixture')
        self.assertEqual(h.state(good), 'test_verified')

    def test_os_profile_lease_blocks_worker_without_weakening_durable_lock(self):
        h = self.h; read = h.enqueue('browser_read')
        lease = ProfileLease(h.sessions.root/h.bindings[1]['profile_ref']).acquire()
        try:
            port = h.port()
            with patch.object(port, 'connect', wraps=port.connect) as connect:
                with self.assertRaises(Problem): h.sessions.run(TENANT, 'w', port)
                connect.assert_not_called()
        finally: lease.close()
        self.assertEqual(h.state(read), 'unknown'); self.assertEqual(len(h.locks()), 2)

    def test_invalid_action_parameters_or_browser_payload_do_not_take_locks(self):
        h = self.h; local = h.enqueue('local_file'); read = h.enqueue('browser_read')
        for args in ({'action':'publish'}, {'action':'wrong'}, {'max_browser_sessions':True},
                     {'max_browser_sessions':3}, {'lease_seconds':float('nan')},
                     {'profile_ref':'../outside'}, {'profile_ref':'valid-but-not-browser'}):
            with self.subTest(args=args), self.assertRaises(Problem): h.q.claim(TENANT, 'w', **args)
        with h.q.transaction() as db:
            db.execute('UPDATE dispatch_tasks SET payload=? WHERE id=?',
                       (json.dumps(local['payload']), read['id']))
        with self.assertRaises(Problem): h.claim(read)
        self.assertEqual(h.locks(), {})
        self.assertEqual(h.state(local), 'queued'); self.assertEqual(h.state(read), 'queued')


if __name__ == '__main__': unittest.main()
