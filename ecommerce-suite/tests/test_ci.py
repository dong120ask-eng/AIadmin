import copy
import importlib.util
import io
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / '示例与验收'))
import release
import test_automation
spec = importlib.util.spec_from_file_location('installer', ROOT / '安装Codex.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.source = Path(self.temp.name) / 'source'
        for name in ('a', 'b'):
            p = self.source / name
            p.mkdir(parents=True)
            (p / 'SKILL.md').write_text(name)
        self.target = self.project / '.agents/skills'

    def test_install_and_idempotence(self):
        installer.install(self.project, self.source)
        p = self.target / 'a/SKILL.md'
        stamp = p.stat().st_mtime_ns
        installer.install(self.project, self.source)
        self.assertEqual(p.stat().st_mtime_ns, stamp)
        self.assertEqual(installer.snapshot(self.target / 'a'), installer.snapshot(self.source / 'a'))

    def test_conflict_preserves_all_user_files(self):
        self.target.mkdir(parents=True)
        (self.target / 'a').mkdir()
        (self.target / 'a/SKILL.md').write_text('user edit')
        (self.target / 'unrelated.txt').write_text('keep')
        before = installer.snapshot(self.target)
        with self.assertRaises(ValueError): installer.install(self.project, self.source)
        self.assertEqual(installer.snapshot(self.target), before)

    def test_copy_failure_rolls_back_then_retry(self):
        self.target.mkdir(parents=True)
        (self.target / 'user.txt').write_text('keep')
        original = Path.open
        def fail(p, *args, **kwargs):
            if p == self.target / 'b/SKILL.md': raise OSError('injected full disk')
            return original(p, *args, **kwargs)
        with patch.object(Path, 'open', fail):
            with self.assertRaises(OSError): installer.install(self.project, self.source)
        self.assertEqual(list(self.target.iterdir()), [self.target / 'user.txt'])
        self.assertFalse((self.project / '.agents/ecommerce-install.lock').exists())
        installer.install(self.project, self.source)
        self.assertTrue((self.target / 'b/SKILL.md').is_file())

    def test_stage_failure_leaves_no_skills(self):
        with patch.object(installer.shutil, 'copytree', side_effect=OSError('injected')):
            with self.assertRaises(OSError): installer.install(self.project, self.source)
        self.assertFalse(self.target.exists())
        installer.install(self.project, self.source)

    def test_lock_fails_closed(self):
        agents = self.project / '.agents'
        agents.mkdir(parents=True)
        (agents / 'ecommerce-install.lock').write_text('other process')
        with self.assertRaises(FileExistsError): installer.install(self.project, self.source)
        self.assertEqual((agents / 'ecommerce-install.lock').read_text(), 'other process')
        self.assertFalse(self.target.exists())

    def test_symlink_refused(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        self.project.mkdir()
        try: (self.project / '.agents').symlink_to(outside, target_is_directory=True)
        except OSError as exc: self.skipTest(f'symlink privilege unavailable: {exc}')
        with self.assertRaises(ValueError): installer.install(self.project, self.source)
        self.assertEqual(list(outside.iterdir()), [])

    def test_cli_real_suite_in_isolated_project(self):
        import subprocess
        for _ in range(2):
            result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / '安装Codex.py'), str(self.project)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(self.target.iterdir())), release.metadata()['skill_count'])


class PackageTests(unittest.TestCase):
    def test_structure_and_historical_assets(self):
        release.structure(); release.historical()

    def test_rebuild_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / 'a', Path(d) / 'b'
            release.build(a); release.build(b)
            name = release.metadata()['archive']
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes())
            (a / name).write_bytes(b'corrupt')
            with self.assertRaises(AssertionError): release.verify(a)

    def test_archive_source_mismatch_even_with_valid_checksum(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); release.build(p)
            name = release.metadata()['archive']
            entries = release.expected(); entries['安装Codex.py'] = b'tampered'
            data = release.archive(entries.items())
            (p / name).write_bytes(data)
            (p / 'SHA256SUMS.txt').write_text(hashlib.sha256(data).hexdigest() + '  ' + name + '\n')
            with self.assertRaises(AssertionError): release.verify(p)

    def test_unsafe_and_duplicate_entries_refused(self):
        for name in ('../escape', '/absolute', 'C:/drive', 'a\\b'):
            with self.assertRaises(AssertionError): release.inspect(release.archive([(name, b'x')]))
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            data = release.archive([('same', b'a'), ('same', b'b')])
        with self.assertRaises(AssertionError): release.inspect(data)


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_automation.GateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_other_store_cannot_borrow_authorization(self):
        import automation as m
        f = self.fixture
        f.cfg['stores']['other'] = dict(f.cfg['stores']['s'])
        f.t['store_id'] = 'other'
        with patch('automation.call') as call:
            result = m.process(f.cfg, f.c)
        self.assertEqual(result[0]['reason'], 'store_or_action_not_authorized')
        call.assert_not_called()

    def test_rebound_tenant_and_platform_cannot_borrow_authorization(self):
        import automation as m
        f = self.fixture
        for key, value in [('tenant_id', 'different'), ('platform', 'tmall')]:
            cfg = copy.deepcopy(f.cfg)
            cfg['stores']['s'][key] = value
            with patch('automation.call') as call:
                result = m.process(cfg, f.c)
            self.assertEqual(result[0]['reason'], 'authorization_binding_mismatch')
            call.assert_not_called()

    def test_other_store_response_blocked_before_write(self):
        f = self.fixture
        result, call = f.run_with(lambda a, q: dict(f.reply(q), store_id='other'))
        self.assertEqual(result[0]['reason'], 'response_scope_or_object_mismatch')
        self.assertEqual(call.call_count, 1)


if __name__ == '__main__': unittest.main()
