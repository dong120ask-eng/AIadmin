"""Offline allowlist verification; never install or invoke runtime providers."""
import hashlib
import json
from pathlib import Path


def verify():
    root = Path(__file__).resolve().parent
    repo = root.parents[1]
    evidence = json.loads((root / 'PROVENANCE.json').read_text(encoding='utf-8'))
    expected = set()
    for entry in evidence['files']:
        path = repo / entry['path']
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('Unsafe path: ' + entry['path'])
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != entry['git_blob_sha']:
            raise ValueError('Source hash mismatch: ' + entry['path'])
        expected.add(path.relative_to(root / 'skills').as_posix()) if root / 'skills' in path.parents else None
    actual = set()
    for path in (root / 'skills').rglob('*'):
        if path.is_symlink():
            raise ValueError('Linked asset')
        if path.is_file():
            actual.add(path.relative_to(root / 'skills').as_posix())
    if actual != expected:
        raise ValueError('Skill allowlist mismatch')
    if len(evidence['excluded_skills']) != 18:
        raise ValueError('Exclusion inventory changed; review required')
    return {'verified_files': len(evidence['files']), 'excluded_skills': 18,
            'runtime_verified': False, 'installed': False}


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False))
