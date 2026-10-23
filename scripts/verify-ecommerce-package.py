"""Verify the distributable in isolation, using only synthetic temporary records."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def run(args, cwd):
    result = subprocess.run(
        [sys.executable, *args], cwd=cwd,
        env=dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1'),
        capture_output=True, text=True, encoding='utf-8', timeout=120,
    )
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed:\n{result.stdout}\n{result.stderr}')
    return result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='电商 打包验收 ') as temporary:
        temp = Path(temporary)
        package = temp / 'pilot.zip'
        run(['scripts/package-ecommerce.py', '--output', str(package)], root)
        extracted = temp / '解压 源码'
        with zipfile.ZipFile(package) as archive:
            assert archive.testzip() is None
            names = archive.namelist()
            assert len(names) == len(set(names))
            for name in names:
                assert not name.startswith(('/', '\\')) and ':' not in name
                assert '\\' not in name and '..' not in name.split('/')
            manifest = json.loads(archive.read('SOURCE-MANIFEST.json'))
            assert set(names) == set(manifest['sha256']) | {'SOURCE-MANIFEST.json'}
            for name, digest in manifest['sha256'].items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == digest
            assert not any(name.endswith(('.db', '.db-wal', '.db-shm', '.pyc')) for name in names)
            archive.extractall(extracted)
        tests = run(['-m', 'unittest', 'tests.test_ecommerce', '-v'], extracted)
        http_output = temp / 'http.json'
        run(['scripts/verify-ecommerce.py', '--output', str(http_output)], extracted)
        http = json.loads(http_output.read_text(encoding='utf-8'))
        assert http['merchant_connected'] is False and http['source_kind'] == 'demo'
        evidence = {
            'scope': 'isolated source package, synthetic offline records only',
            'python': sys.version.split()[0], 'os': sys.platform,
            'archive_sha256': hashlib.sha256(package.read_bytes()).hexdigest(),
            'manifest_and_crc': 'passed', 'file_count': len(names),
            'package_tests': tests, 'package_http': http,
            'windows_user_machine': 'not connected; not verified',
            'operator_acceptance': 'not performed',
        }
    result = json.dumps(evidence, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding='utf-8')
    print(result)


if __name__ == '__main__':
    main()
