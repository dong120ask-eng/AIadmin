import importlib.util
import pathlib
import shutil
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1]


class AllowlistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name) / 'reuse' / 'aladmin'
        shutil.copytree(SOURCE, self.root, ignore=shutil.ignore_patterns('__pycache__'))
        spec = importlib.util.spec_from_file_location('fixture_verify', self.root / 'verify.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_pristine(self):
        self.assertEqual(self.module.verify()['verified_files'], 12)

    def test_tampered_license(self):
        (self.root / 'skills/marketing-material-generator/LICENSE').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.module.verify()

    def test_extra_unreviewed_skill(self):
        extra = self.root / 'skills/unreviewed'
        extra.mkdir()
        (extra / 'SKILL.md').write_text('unreviewed')
        with self.assertRaisesRegex(ValueError, 'allowlist mismatch'):
            self.module.verify()

    def test_missing_source(self):
        (self.root / 'install/install-shared.ps1').unlink()
        with self.assertRaises(FileNotFoundError):
            self.module.verify()


if __name__ == '__main__':
    unittest.main()
