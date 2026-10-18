"""Validate source layouts, rebuild per-skill ZIPs, and produce a distribution."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    names = manifest['skills']
    if len(names) != 6 or len(set(names)) != 6:
        raise ValueError('Expected six unique skills')
    for flavor in ('codex', 'workbuddy'):
        for name in names:
            folder = ROOT / flavor / 'skills' / name
            content = (folder / 'SKILL.md').read_text(encoding='utf-8')
            front = content.split('---', 2)[1]
            required = ['name', 'description']
            if flavor == 'workbuddy':
                required += ['description_zh', 'description_en', 'version', 'author']
            for key in required:
                if not re.search(rf'^{key}:\s*\S', front, re.M):
                    raise ValueError(f'{flavor}/{name}: missing {key}')
            if not re.search(rf'^name:\s*{re.escape(name)}\s*$', front, re.M):
                raise ValueError(f'{name}: mismatched name')
            if 'TODO' in content:
                raise ValueError(f'{name}: unfinished template')
            for ref in set(re.findall(r'references/[a-z-]+\.md', content)):
                if not (folder / ref).is_file():
                    raise ValueError(f'{name}: unresolved reference {ref}')
            if flavor == 'workbuddy':
                output = ROOT / flavor / (name + '.zip')
                with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
                    for path in sorted(folder.rglob('*')):
                        if path.is_file():
                            z.write(path, path.relative_to(folder.parent))
                with zipfile.ZipFile(output) as z:
                    if z.testzip() is not None or f'{name}/SKILL.md' not in z.namelist():
                        raise ValueError(f'{name}: invalid ZIP')
    source_files = [p for p in sorted(ROOT.rglob('*')) if p.is_file()
                    and p.suffix != '.zip' and p.name != 'SHA256SUMS'
                    and '__pycache__' not in p.parts]
    (ROOT/'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n'
        for p in source_files), encoding='utf-8')
    output = ROOT.parent / '视频原创改编技能包_v1.0.0.zip'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(ROOT.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                z.write(path, path.relative_to(ROOT.parent))
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise ValueError('Distribution ZIP corrupt')
    print(json.dumps({'skills':len(names), 'source_files':len(source_files),
                      'package':str(output), 'status':'passed'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
