"""Build the Windows x64 release runtime from pinned, hash-verified vendor files."""
import argparse, hashlib, json, subprocess, sys, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def download(url, out, expected):
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'yijian-jineng-release'})
        with urllib.request.urlopen(request, timeout=120) as response, out.open('xb') as dest:
            import shutil
            shutil.copyfileobj(response, dest)
    try:
        if sha(out) != expected:
            raise ValueError('Vendor file hash mismatch: ' + out.name)
    except ValueError:
        # Delete corrupt/partial file so next run re-downloads instead of getting stuck.
        out.unlink(missing_ok=True)
        raise

def build(verify=False):
    pins = json.loads((ROOT / 'config/runtime-build-pins.json').read_text(encoding='utf-8'))
    offline = ROOT / 'offline'
    wheels = offline / 'wheels'
    if verify:
        for item in pins['wheels']:
            if sha(wheels / item['name']) != item['sha256']:
                raise ValueError('Wheel hash mismatch')
        for key in ('python', 'github_cli'):
            item = pins[key]
            if sha(offline / item['relative_path']) != item['sha256']:
                raise ValueError('Vendor hash mismatch')
        return
    offline.mkdir(exist_ok=True)
    lock = ROOT / 'config/requirements-release-hashed.txt'
    subprocess.run([sys.executable, '-m', 'pip', 'download',
                    '--index-url', 'https://pypi.org/simple',
                    '--only-binary=:all:', '--require-hashes',
                    '--dest', str(wheels), '-r', str(lock)],
                   check=True, timeout=600)
    for item in pins['wheels']:
        if sha(wheels / item['name']) != item['sha256']:
            raise ValueError('Unexpected wheel')
    item = pins['python']
    archive = offline / item['relative_path']
    download(item['url'], archive, item['sha256'])
    runtime = offline / 'runtime'
    if runtime.exists():
        raise ValueError('Runtime directory already exists')
    with zipfile.ZipFile(archive) as z:
        z.extractall(runtime)
    (runtime / 'python313._pth').write_text(
        'python313.zip\n.\nLib/site-packages\nimport site\n', encoding='ascii')
    with zipfile.ZipFile(next(wheels.glob('pip-*.whl'))) as z:
        z.extractall(runtime / 'Lib/site-packages')
    python = runtime / 'python.exe'
    subprocess.run([str(python), '-m', 'pip', 'install',
                    '--no-index', '--find-links', str(wheels),
                    '--require-hashes', '--target', str(runtime / 'Lib/site-packages'),
                    '-r', str(lock)], check=True, timeout=600)
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    item = pins['github_cli']
    archive = offline / item['relative_path']
    download(item['url'], archive, item['sha256'])
    with zipfile.ZipFile(archive) as z:
        z.extractall(archive.parent)
    (offline / 'requirements-lock.txt').write_text(
        '\n'.join(i['requirement'] for i in pins['wheels']) + '\n', encoding='utf-8')
    (archive.parent / 'source.json').write_text(json.dumps(item, indent=2), encoding='utf-8')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verify-only', action='store_true')
    a = p.parse_args()
    build(a.verify_only)
    print('Pinned offline runtime verified' if a.verify_only else 'Pinned offline runtime built')
