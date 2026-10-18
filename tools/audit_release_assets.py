"""Read-only archive inventory; never executes or extracts archived programs."""
import email
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

RULES = {
    'provider-token': re.compile(rb'\b(?:sk-[A-Za-z0-9_-]{20,}|(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,}|ak_[A-Za-z0-9]{20,})\b'),
    'private-key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'session-cookie': re.compile(rb'(?:sessionid|auth_token|SESSDATA|bili_jct|web_session|PHPSESSID)=[A-Za-z0-9%_+/-]{16,}'),
}
MAX_MEMBER = 256 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024


def scan_zip(data, report, prefix='', depth=0):
    if depth > 4:
        raise ValueError('archive nesting limit')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for item in archive.infolist():
            name = item.filename
            path = prefix + name
            if item.is_dir():
                continue
            if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or '\\' in name or re.match(r'^[A-Za-z]:', name):
                report['findings'].append({'rule': 'unsafe-archive-path', 'path': path})
            if item.flag_bits & 1:
                raise ValueError('encrypted member cannot be audited')
            if item.file_size > MAX_MEMBER:
                raise ValueError('member size limit')
            report['expanded_bytes'] += item.file_size
            if report['expanded_bytes'] > MAX_TOTAL:
                raise ValueError('expanded size limit')
            raw = archive.read(item)
            report['files_scanned'] += 1
            for label, rule in RULES.items():
                if rule.search(raw):
                    digest = hashlib.sha256(raw).hexdigest()
                    if label == 'provider-token' and digest in report.get('official_binary_sha256', []):
                        report['upstream_binary_pattern_hits'].append({'rule': label, 'path': path, 'sha256': digest})
                    else:
                        report['findings'].append({'rule': label, 'path': path, 'sha256': digest})
            base = PurePosixPath(name).name.lower()
            if base in {'.env', 'auth.json', 'cookies.txt', 'cookies.json', 'storage-state.json', 'id_rsa', 'id_ed25519'} or base.endswith(('.p12', '.pfx', '.key')):
                report['findings'].append({'rule': 'sensitive-filename', 'path': path})
            if any(word in base for word in ('license', 'licence', 'copyright', 'notice')):
                report['license_files'].append({'path': path, 'sha256': hashlib.sha256(raw).hexdigest()})
            if name.endswith('.dist-info/METADATA'):
                msg = email.message_from_bytes(raw)
                package = {k: msg.get(k) for k in ('Name', 'Version', 'License-Expression')}
                package['license_classifiers'] = [v for v in msg.get_all('Classifier', []) if v.startswith('License ::')]
                report['packages'].append(package)
            if base.endswith(('.zip', '.whl')):
                scan_zip(raw, report, prefix=path + '!/', depth=depth + 1)


def gh(*args):
    return subprocess.check_output(['gh', *args], timeout=600)


def verify_official_gh():
    """Trust exact bytes only after matching the pinned archive to the upstream release."""
    pins = json.loads(Path('yijian-jineng/config/runtime-build-pins.json').read_text(encoding='utf-8'))
    item = pins['github_cli']
    match = re.fullmatch(r'https://github.com/cli/cli/releases/download/([^/]+)/([^/]+)', item['url'])
    if not match:
        raise ValueError('Unexpected vendor source')
    tag, filename = match.groups()
    release = json.loads(gh('api', f'repos/cli/cli/releases/tags/{tag}'))
    assets = [a for a in release['assets'] if a['name'] == filename]
    if len(assets) != 1:
        raise ValueError('Official vendor asset missing or ambiguous')
    raw = gh('api', '-H', 'Accept: application/octet-stream', f'repos/cli/cli/releases/assets/{assets[0]["id"]}')
    digest = hashlib.sha256(raw).hexdigest()
    if digest != item['sha256']:
        raise ValueError('Official vendor archive does not match pinned SHA256')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        executables = [n for n in archive.namelist() if n.endswith('bin/gh.exe')]
        if len(executables) != 1:
            raise ValueError('Expected one official gh.exe')
        binary_digest = hashlib.sha256(archive.read(executables[0])).hexdigest()
    return {'source': 'https://github.com/cli/cli', 'tag': tag, 'asset': filename, 'archive_sha256': digest, 'binary_sha256': binary_digest}


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    official = verify_official_gh()
    pages = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100'))
    releases = [release for page in pages for release in page]
    output = Path('audit-output')
    output.mkdir(exist_ok=True)
    reports = []
    for release in releases:
        for asset in release['assets']:
            if not asset['name'].lower().endswith('.zip'):
                continue
            report = {'tag': release['tag_name'], 'asset_id': asset['id'], 'asset': asset['name'], 'files_scanned': 0, 'expanded_bytes': 0, 'findings': [], 'upstream_binary_pattern_hits': [], 'official_binary_sha256': [official['binary_sha256']], 'license_files': [], 'packages': [], 'status': 'incomplete'}
            try:
                with tempfile.TemporaryDirectory() as td:
                    destination = Path(td) / 'asset.zip'
                    # gh handles authenticated asset redirects; credentials never enter the report.
                    with destination.open('wb') as stream:
                        subprocess.run(['gh', 'api', '-H', 'Accept: application/octet-stream', f'repos/{repo}/releases/assets/{asset["id"]}'], stdout=stream, check=True, timeout=600)
                    data = destination.read_bytes()
                    if len(data) != asset['size']:
                        raise ValueError('asset size mismatch')
                    report['sha256'] = hashlib.sha256(data).hexdigest()
                    scan_zip(data, report)
                    report['status'] = 'scanned'
            except Exception as exc:
                # Do not include exception text: it may contain response data or URLs.
                report['error_type'] = type(exc).__name__
            reports.append(report)
            print(json.dumps({'tag': report['tag'], 'asset': report['asset'], 'status': report['status'], 'files_scanned': report['files_scanned'], 'findings': len(report['findings']), 'official_binary_pattern_hits': len(report['upstream_binary_pattern_hits']), 'license_files': len(report['license_files']), 'packages': len(report['packages'])}))
    result = {'scope': 'release ZIPs and nested ZIP/wheels; no archived program executed', 'official_gh_verification': official, 'limitations': 'Pattern scan and license inventory only; not privacy or licensing approval. Other archive formats and binary semantics require separate review.', 'reports': reports}
    (output / 'release-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if not reports or any(r['status'] != 'scanned' or r['findings'] for r in reports):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
