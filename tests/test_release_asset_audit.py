"""Synthetic pattern fixtures are assembled in memory, never real credentials."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('audit', Path(__file__).resolve().parents[1] / 'tools/audit_release_assets.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        for name, data in entries:
            z.writestr(name, data)
    return stream.getvalue()


def report():
    return dict(files_scanned=0, expanded_bytes=0, findings=[],
                upstream_binary_pattern_hits=[], license_files=[], packages=[])


class ReleaseAuditTests(unittest.TestCase):
    def test_exact_hash_only(self):
        raw = b'sk' + b'-' + b'A' * 32
        r = report()
        r['official_binary_sha256'] = [hashlib.sha256(raw).hexdigest()]
        audit.scan_zip(archive([('bin/gh.exe', raw), ('other/gh.exe', raw + b'changed')]), r)
        self.assertEqual(len(r['upstream_binary_pattern_hits']), 1)
        self.assertEqual(len(r['findings']), 1)
        self.assertEqual(r['findings'][0]['path'], 'other/gh.exe')
        self.assertNotIn(raw.decode(), json.dumps(r))

    def test_filename_alone_never_trusted(self):
        r = report()
        audit.scan_zip(archive([('bin/gh.exe', b'ghp' + b'_' + b'A' * 32)]), r)
        self.assertEqual(r['findings'][0]['rule'], 'provider-token')

    def test_nested_duplicates_keep_paths_and_hash(self):
        raw = b'sk' + b'-' + b'B' * 32
        r = report()
        audit.scan_zip(archive([('vendor.zip', archive([('bin/gh.exe', raw)])), ('bin/gh.exe', raw)]), r)
        self.assertEqual([f['path'] for f in r['findings']], ['vendor.zip!/bin/gh.exe', 'bin/gh.exe'])
        self.assertEqual(len({f['sha256'] for f in r['findings']}), 1)

    def test_other_rules_not_suppressed(self):
        raw = b'-----BEGIN ' + b'PRIVATE KEY-----'
        r = report()
        r['official_binary_sha256'] = [hashlib.sha256(raw).hexdigest()]
        audit.scan_zip(archive([('gh.exe', raw)]), r)
        self.assertEqual(r['findings'][0]['rule'], 'private-key')

    def test_cookie_and_sensitive_file(self):
        r = report()
        audit.scan_zip(archive([('cookies.json', b'sessionid=' + b'C' * 24)]), r)
        self.assertEqual({f['rule'] for f in r['findings']}, {'session-cookie', 'sensitive-filename'})

    def test_unsafe_paths(self):
        for name in ('../bad', '/bad', 'C:/bad', 'a\\bad'):
            with self.subTest(name=name):
                r = report()
                audit.scan_zip(archive([(name, b'')]), r)
                self.assertEqual(r['findings'][0]['rule'], 'unsafe-archive-path')

    def test_limits_fail_closed(self):
        with patch.object(audit, 'MAX_MEMBER', 1):
            with self.assertRaises(ValueError):
                audit.scan_zip(archive([('large', b'xx')]), report())
        with self.assertRaises(ValueError):
            audit.scan_zip(archive([]), report(), depth=5)

    def test_local_gate_blocks_and_redacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            z = root / 'new.zip'
            raw = b'sk' + b'-' + b'D' * 32
            z.write_bytes(archive([('bad.txt', raw)]))
            # Redirect only the output directory; no network or credentials needed.
            original_path = audit.Path
            with patch.object(audit, 'verify_official_gh', return_value={'binary_sha256': 'none'}), patch.object(audit, 'Path', side_effect=lambda p: root / p if p == 'audit-output' else original_path(p)):
                with self.assertRaises(SystemExit):
                    audit.audit_local([z])
            output = (root / 'audit-output/local-release-audit.json').read_text()
            self.assertNotIn(raw.decode(), output)
            self.assertEqual(json.loads(output)['reports'][0]['status'], 'scanned')

    def test_local_gate_passes_clean_zip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            z = root / 'clean.zip'
            z.write_bytes(archive([('README', b'clean')]))
            original_path = audit.Path
            with patch.object(audit, 'verify_official_gh', return_value={'binary_sha256': 'none'}), patch.object(audit, 'Path', side_effect=lambda p: root / p if p == 'audit-output' else original_path(p)):
                audit.audit_local([z])
            self.assertEqual(json.loads((root / 'audit-output/local-release-audit.json').read_text())['reports'][0]['findings'], [])

    def test_corrupt_zip_blocks(self):
        with self.assertRaises(zipfile.BadZipFile):
            audit.scan_zip(b'broken', report())
