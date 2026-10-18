import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('release_metadata', Path(__file__).resolve().parents[1] / 'tools/release_metadata.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseMetadataTests(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(module.identity('2026-10-18-r12'), {'tag': 'v2026.10.18-r12', 'asset': 'yijian-jineng-20261018-r12.zip'})

    def test_invalid_versions(self):
        for value in ['2026-02-30-r1', '2026-10-18-r0', '../r1', 'v2026.10.14-r8', '2026-10-18-r1\n']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.identity(value)

    def test_integrity_and_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            metadata = module.identity('2026-10-18-r1')
            asset = root / metadata['asset']
            with zipfile.ZipFile(asset, 'w') as archive:
                archive.writestr('fixture.txt', 'synthetic test only')
            checksum = root / 'SHA256.txt'
            checksum.write_text(hashlib.sha256(asset.read_bytes()).hexdigest() + '  ' + asset.name + '\n', encoding='utf-8')
            module.verify(root, metadata)
            checksum.write_text('0' * 64 + '  ' + asset.name + '\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                module.verify(root, metadata)
            asset.rename(root / 'wrong.zip')
            with self.assertRaises(ValueError):
                module.verify(root, metadata)
