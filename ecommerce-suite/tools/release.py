"""Deterministic standard-library packaging and strict archive verification."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def metadata():
    m = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    assert re.fullmatch(r'\d+\.\d+\.\d+', m['version']), 'invalid version'
    assert m['archive'] == f"ecommerce-suite-{m['version']}.zip"
    return m


def files(root):
    for p in sorted(root.rglob('*')):
        assert not p.is_symlink(), f'symlink: {p}'
        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
            yield p.relative_to(root).as_posix(), p.read_bytes()


def structure():
    m = metadata()
    entries = json.loads((ROOT / '技能清单.json').read_text(encoding='utf-8'))
    names = [e['name'] for e in entries]
    assert len(names) == len(set(names)) == m['skill_count']
    assert set(names) == {p.name for p in (ROOT / 'Codex').iterdir()}
    for name in names:
        assert re.fullmatch(r'[a-z][a-z0-9-]+', name)
        p = ROOT / 'Codex' / name
        text = (p / 'SKILL.md').read_text(encoding='utf-8')
        assert text.startswith('---\n') and f'name: {name}\n' in text
        assert 'description:' in text and text.count('---') >= 2
        assert (p / 'agents/openai.yaml').is_file()
        assert (ROOT / '豆包' / (name + '.txt')).is_file()
        list(files(p))
    # Bundled execution code must match the code under regression tests.
    for p in (ROOT / 'Codex').glob('*/scripts/*.py'):
        assert p.read_bytes() == (ROOT / '示例与验收' / p.name).read_bytes(), str(p)
    return names


def archive(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, content in sorted(entries):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            z.writestr(info, content)
    return out.getvalue()


def expected():
    names = structure()
    entries = []
    for name, data in files(ROOT):
        if name.split('/')[0] not in ('dist',):
            entries.append((name, data))
    for name in names:
        entries.append((f'WorkBuddy/{name}.zip', archive(
            (f'{name}/{path}', data) for path, data in files(ROOT / 'Codex' / name))))
    return dict(entries)


def inspect(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        assert len(names) == len(set(names)), 'duplicate ZIP entry'
        assert z.testzip() is None, 'CRC failure'
        for info in z.infolist():
            n = info.orig_filename
            assert n == info.filename, 'ZIP reader normalized an unsafe name'
            assert '\\' not in n and not n.startswith('/') and ':' not in n
            assert '..' not in PurePosixPath(n).parts
            assert not stat.S_ISLNK(info.external_attr >> 16)
        return {n: z.read(n) for n in names}


def checksums(directory, filename):
    lines = (directory / filename).read_text(encoding='utf-8').splitlines()
    assert lines, 'empty checksum manifest'
    seen = set()
    for line in lines:
        digest, name = line.split(None, 1)
        name = name.strip()
        assert re.fullmatch(r'[0-9a-fA-F]{64}', digest)
        assert Path(name).name == name and name not in seen
        seen.add(name)
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest.lower(), name
    return seen


def historical():
    for manifest in sorted((ROOT / 'dist').glob('SHA256*.txt')):
        for name in checksums(ROOT / 'dist', manifest.name):
            outer = inspect((ROOT / 'dist' / name).read_bytes())
            skills = json.loads(outer['技能清单.json'])
            names = {e['name'] for e in skills}
            assert {n for n in outer if n.startswith('WorkBuddy/')} == {f'WorkBuddy/{n}.zip' for n in names}
            for n in names:
                inner = inspect(outer[f'WorkBuddy/{n}.zip'])
                source = {k[len('Codex/'):]: v for k, v in outer.items() if k.startswith(f'Codex/{n}/')}
                assert inner == source and f'{n}/SKILL.md' in inner


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    m = metadata()
    data = archive(expected().items())
    (output / m['archive']).write_bytes(data)
    (output / 'SHA256SUMS.txt').write_text(
        hashlib.sha256(data).hexdigest() + '  ' + m['archive'] + '\n', encoding='utf-8')
    verify(output)


def verify(output):
    m = metadata()
    assert checksums(output, 'SHA256SUMS.txt') == {m['archive']}
    data = (output / m['archive']).read_bytes()
    assert inspect(data) == expected(), 'archive differs from source'
    assert data == archive(expected().items()), 'non-reproducible archive'
    print(json.dumps(dict(version=m['version'], skills=m['skill_count'], sha256=hashlib.sha256(data).hexdigest(), acceptance='offline-only')))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['check', 'build', 'verify'])
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.command == 'check':
        structure(); historical(); print('Structure, historical SHA256, CRC and WorkBuddy layout passed')
    else:
        if a.output is None: p.error('--output required')
        (build if a.command == 'build' else verify)(a.output)


if __name__ == '__main__': main()
