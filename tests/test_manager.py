import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.manager import ManagerQueue, TENANT, understand, check_file
from workbench.store import Problem


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name); self.clock = [1000]
        self.q = ManagerQueue(self.path/'manager.db', clock=lambda: self.clock[0])
        self.sentence = '创建文件 hello.txt，内容为你好，AIadmin'

    def test_closed_router(self):
        for text in ['发布文章', '支付100元', '创建文件 ../x.txt，内容为a', '运行 rm -rf', '创建文件 a.py，内容为print(1)']:
            self.assertFalse(understand(text)['executable'])

    def test_idempotency_and_restart(self):
        task = self.q.submit(self.sentence, 'same')
        self.assertEqual(task['id'], ManagerQueue(self.q.path).submit(self.sentence, 'same')['id'])
        with self.assertRaises(Problem): self.q.submit('创建文件 a.txt，内容为b', 'same')

    def test_authorization(self):
        self.q.submit(self.sentence)
        with patch('workbench.manager.invoke') as invoke:
            for args in [(False, False), (True, False), (False, True)]:
                with self.assertRaises(Problem): self.q.run_next(*args)
            invoke.assert_not_called()
        self.assertEqual(self.q.tasks(TENANT)[0]['state'], 'queued')

    def test_host_checked_success(self):
        self.q.submit(self.sentence)
        def fake(args, **kwargs):
            (kwargs['cwd']/'hello.txt').write_bytes('你好，AIadmin'.encode())
            return 0, 'model claims ignored'
        with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke', side_effect=fake):
            result = self.q.run_next(True, True, task_id=self.q.tasks(TENANT)[0]['id'])
        self.assertEqual(result['state'], 'checked')
        self.assertEqual(result['result']['checker'], 'host_exact_bytes')

    def test_missing_cli_does_not_claim(self):
        self.q.submit(self.sentence)
        with patch('workbench.manager.codex_binary', return_value=None):
            with self.assertRaises(Problem): self.q.run_next(True, True, task_id=self.q.tasks(TENANT)[0]['id'])
        self.assertEqual(self.q.tasks(TENANT)[0]['state'], 'queued')

    def test_bad_output_and_failure_isolate(self):
        for code in [0, 1]:
            q = ManagerQueue(self.path / ('case'+str(code)+'.db'))
            q.submit(self.sentence)
            with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke', return_value=(code, 'success')):
                with self.assertRaises(Problem): q.run_next(True, True, task_id=q.tasks(TENANT)[0]['id'])
            self.assertEqual(q.tasks(TENANT)[0]['state'], 'unknown')
            self.assertIsNone(q.claim(TENANT, 'other'))

    def test_recovery_fences_old_worker(self):
        task = self.q.submit(self.sentence)
        claimed = self.q.claim(TENANT, 'worker', 5, action='local_file', expected_task=task['id'])
        self.clock[0] += 6
        self.assertEqual(self.q.recover()['marked_unknown'], 1)
        with self.assertRaises(Problem): self.q.complete(task['id'], claimed['lease_token'], {})
        with self.assertRaises(Problem): self.q.resolve_unknown(TENANT, task['id'], '已核查')
        self.q.resolve_unknown(TENANT, task['id'], '已核查并停止旧进程', True)
        self.assertEqual(self.q.tasks(TENANT)[0]['state'], 'cancelled')

    def test_checker_rejects_extra_and_symlink(self):
        contract = understand(self.sentence)
        (self.path/'hello.txt').write_text(contract['content'], encoding='utf-8')
        (self.path/'extra.txt').write_text('extra')
        with self.assertRaises(Problem): check_file(self.path, contract)
        (self.path/'extra.txt').unlink(); (self.path/'hello.txt').unlink()
        try: (self.path/'hello.txt').symlink_to('missing')
        except OSError: self.skipTest('symlinks unavailable')
        with self.assertRaises(Problem): check_file(self.path, contract)

    def test_timeout_is_unknown(self):
        self.q.submit(self.sentence)
        with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke', side_effect=Problem('超时')):
            with self.assertRaises(Problem): self.q.run_next(True, True, task_id=self.q.tasks(TENANT)[0]['id'])
        self.assertEqual(self.q.tasks(TENANT)[0]['state'], 'unknown')

if __name__ == '__main__': unittest.main()
