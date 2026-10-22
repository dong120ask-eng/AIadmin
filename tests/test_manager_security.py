"""Regression and real local-process fixtures; never calls a model."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from workbench.manager import ManagerQueue, TENANT, check_file, understand, manager_command, is_redirect
from workbench.runner import invoke, codex_binary
from workbench.store import Problem


class ManagerSecurityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.q = ManagerQueue(self.root / 'manager.db')
        self.text = '创建文件 hello.txt，内容为你好，AIadmin'
        self.contract = understand(self.text)

    def test_authorization_requires_identity(self):
        self.q.submit(self.text)
        with patch('workbench.manager.invoke') as call:
            with self.assertRaises(Problem): self.q.run_next(True, True)
            call.assert_not_called()
        self.assertEqual(self.q.tasks(TENANT)[0]['state'], 'queued')

    def test_consumed_authorization_never_runs_another_task(self):
        first = self.q.submit(self.text)
        second = self.q.submit('创建文件 next.txt，内容为另一个任务')
        def fake(args, **kw):
            (kw['cwd']/'hello.txt').write_bytes(self.contract['content'].encode())
            return 0, ''
        with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke', side_effect=fake) as call:
            self.q.run_next(True, True, task_id=first['id'])
            with self.assertRaises(Problem): self.q.run_next(True, True, task_id=first['id'])
            self.assertEqual(call.call_count, 1)
        self.assertEqual(self.q.tasks(TENANT)[1]['id'], second['id'])
        self.assertEqual(self.q.tasks(TENANT)[1]['state'], 'queued')

    def test_atomic_competing_claims(self):
        task = self.q.submit(self.text)
        def claim(_):
            return ManagerQueue(self.q.path).claim(TENANT, 'worker', expected_task=task['id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)

    def test_expired_token_cannot_complete_even_without_recover(self):
        clock = [1000]
        q = ManagerQueue(self.root/'lease.db', clock=lambda: clock[0])
        task = q.submit(self.text); claimed = q.claim(TENANT, 'worker', 5)
        clock[0] += 6
        with self.assertRaises(Problem): q.complete(task['id'], claimed['lease_token'], {})
        self.assertEqual(q.recover()['marked_unknown'], 1)
        self.assertIsNone(q.claim(TENANT, 'other'))

    def test_tampered_persisted_contract_not_invoked(self):
        task = self.q.submit(self.text)
        with self.q.transaction() as db:
            db.execute('UPDATE dispatch_tasks SET payload=? WHERE id=?',
                       (json.dumps({'contract': {'filename': '../outside.txt'}, 'sentence': self.text}), task['id']))
        with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke') as call:
            with self.assertRaises(Problem): self.q.run_next(True, True, task_id=task['id'])
            call.assert_not_called()
        self.assertEqual(self.q.tasks(TENANT)[0]['state'], 'unknown')

    def test_attempt_directory_survives_restart_after_failure(self):
        task = self.q.submit(self.text)
        with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke', side_effect=Problem('timeout')):
            with self.assertRaises(Problem): self.q.run_next(True, True, task_id=task['id'])
        result = ManagerQueue(self.q.path).tasks(TENANT)[0]
        self.assertEqual(result['state'], 'unknown')
        self.assertTrue(Path(result['result']['attempt_path']).is_dir())

    def test_fabricated_completion_cannot_mark_checked(self):
        task = self.q.submit(self.text)
        claimed = self.q.claim(TENANT, 'worker')
        with self.assertRaises(Problem): self.q.complete(task['id'], claimed['lease_token'], {'checker': 'host_exact_bytes'})
        self.assertEqual(self.q.tasks(TENANT)[0]['state'], 'running')

    def test_lease_expiring_during_final_readback_cannot_complete(self):
        clock = [1000]
        q = ManagerQueue(self.root/'slow.db', clock=lambda: clock[0])
        task = q.submit(self.text); claimed = q.claim(TENANT, 'worker', 5)
        with q.transaction() as db:
            db.execute('UPDATE dispatch_tasks SET result=? WHERE id=?',
                       (json.dumps({'attempt_path': str(self.root)}), task['id']))
        def slow_check(*args):
            clock[0] += 6
            return {'checker': 'host_exact_bytes'}
        with patch('workbench.manager.check_file', side_effect=slow_check), self.assertRaises(Problem):
            q.complete(task['id'], claimed['lease_token'], {'checker': 'host_exact_bytes'})
        self.assertEqual(q.recover()['marked_unknown'], 1)

    def test_replaced_task_directory_is_unknown(self):
        task = self.q.submit(self.text)
        def fake(args, **kw):
            folder = kw['cwd']
            folder.rename(folder.with_name(folder.name + '-old'))
            folder.mkdir()
            (folder/'hello.txt').write_bytes(self.contract['content'].encode())
            return 0, ''
        with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke', side_effect=fake):
            with self.assertRaises(Problem): self.q.run_next(True, True, task_id=task['id'])
        self.assertEqual(self.q.tasks(TENANT)[0]['state'], 'unknown')

    def test_invalid_filenames_and_contracts(self):
        for name in ('../outside.txt', 'C:\\outside.txt', 'x.txt:stream', 'NUL.txt', 'a.py', 'a.txt.'):
            with self.subTest(name=name), self.assertRaises(Problem):
                check_file(self.root, {**self.contract, 'filename': name})

    def test_hardlink_and_bounded_large_output(self):
        folder = self.root/'output'; folder.mkdir()
        source = self.root/'source'; source.write_bytes(self.contract['content'].encode())
        target = folder/'hello.txt'
        os.link(source, target)
        with self.assertRaises(Problem): check_file(folder, self.contract)
        target.unlink(); target.write_bytes(b'a' * 100000)
        with self.assertRaises(Problem): check_file(folder, self.contract)

    def test_reparse_attribute_rejected(self):
        self.assertTrue(is_redirect(SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)))

    @unittest.skipUnless(os.name == 'posix', 'POSIX filesystem fixture')
    def test_symlinked_runtime_root_and_fifo(self):
        outside = self.root/'outside'; outside.mkdir()
        (self.root/'manager-runtime').symlink_to(outside, target_is_directory=True)
        task = self.q.submit(self.text)
        with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke') as call:
            with self.assertRaises(Problem): self.q.run_next(True, True, task_id=task['id'])
            call.assert_not_called()
        (self.root/'manager-runtime').unlink()
        os.mkfifo(outside/'hello.txt')
        with self.assertRaises(Problem): check_file(outside, self.contract)

    @unittest.skipUnless(os.name == 'posix', 'POSIX symlink fixture')
    def test_symlinked_output_directory_rejected(self):
        folder = self.root/'output'; folder.mkdir()
        (folder/'hello.txt').write_bytes(self.contract['content'].encode())
        link = self.root/'link'; link.symlink_to(folder, target_is_directory=True)
        with self.assertRaises(Problem): check_file(link, self.contract)

    def test_native_windows_binary_only(self):
        with patch('workbench.runner.os.name', 'nt'):
            for name in ('codex.cmd', 'codex.bat', 'codex.ps1'):
                with patch.dict(os.environ, {'CODEX_BIN': name}): self.assertIsNone(codex_binary())

    def test_cli_policy_and_data_stdin(self):
        task = self.q.submit(self.text)
        def fake(args, **kw):
            self.assertEqual(args, manager_command('fake', kw['cwd']))
            self.assertNotIn(self.contract['content'], args)
            for value in ('sandbox_workspace_write.writable_roots=[]', 'sandbox_workspace_write.network_access=false',
                          'sandbox_workspace_write.exclude_tmpdir_env_var=true', 'sandbox_workspace_write.exclude_slash_tmp=true',
                          'web_search="disabled"', 'features.multi_agent=false'):
                self.assertIn(value, args)
            self.assertEqual(args[1:4], ['-a', 'never', 'exec'])
            (kw['cwd']/'hello.txt').write_bytes(self.contract['content'].encode())
            return 0, 'untrusted model message'
        with patch('workbench.manager.codex_binary', return_value='fake'), patch('workbench.manager.invoke', side_effect=fake):
            self.assertEqual(self.q.run_next(True, True, task_id=task['id'])['state'], 'checked')

    def test_real_subprocess_file_and_readback(self):
        task = self.q.submit(self.text)
        script = "import json,sys,pathlib; d=json.loads(sys.stdin.read().split('\\n',1)[1]); pathlib.Path(d['filename']).write_bytes(d['content'].encode('utf-8'))"
        with patch('workbench.manager.codex_binary', return_value=sys.executable), patch('workbench.manager.manager_command', return_value=[sys.executable, '-c', script]):
            result = self.q.run_next(True, True, task_id=task['id'])
        self.assertEqual(result['state'], 'checked')
        self.assertEqual(Path(result['result']['path']).read_bytes(), self.contract['content'].encode())

    def test_stdin_delivery_obeys_timeout(self):
        started = time.monotonic()
        with self.assertRaises(Problem):
            invoke([sys.executable, '-c', 'import time; time.sleep(20)'], prompt='x'*200000, timeout=0.2)
        self.assertLess(time.monotonic()-started, 5)

    def test_fast_exiting_excess_output_rejected(self):
        with patch('workbench.runner.MAX_BYTES', 100), self.assertRaises(Problem):
            invoke([sys.executable, '-c', "print('x'*1000)"], timeout=2)

    @unittest.skipUnless(os.name == 'posix', 'POSIX process group fixture')
    def test_exited_parent_descendant_stopped(self):
        marker = self.root/'escaped'
        script = "import subprocess,sys; subprocess.Popen([sys.executable,'-c'," + repr("import time,pathlib; time.sleep(0.5); pathlib.Path("+repr(str(marker))+").write_text('bad')") + "])"
        invoke([sys.executable, '-c', script], timeout=2)
        time.sleep(0.7)
        self.assertFalse(marker.exists())

if __name__ == '__main__': unittest.main()
