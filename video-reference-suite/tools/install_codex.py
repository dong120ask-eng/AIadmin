"""Install six skill directories into an explicit project's .agents/skills.

Never overwrite existing skills. Uses only Python's standard library.
"""
from pathlib import Path
import argparse
import json
import shutil


def install(project):
    root = Path(__file__).resolve().parents[1]
    names = json.loads((root/'manifest.json').read_text(encoding='utf-8'))['skills']
    source = root/'codex/skills'
    destination = Path(project).expanduser().resolve()/'.agents/skills'
    # Check every destination and source before any writes.
    for name in names:
        if not (source/name/'SKILL.md').is_file():
            raise ValueError(f'Missing source skill: {name}')
        if (destination/name).exists():
            raise FileExistsError(f'Existing skill preserved: {destination/name}')
    created = []
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for name in names:
            target = destination/name
            created.append(target)
            shutil.copytree(source/name, target)
    except Exception:
        for target in reversed(created):
            if target.is_dir():
                shutil.rmtree(target)
        raise
    print(json.dumps({'installed_paths':[str(p) for p in created],
                      'next':'Start Codex in the chosen project and verify skill discovery.'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, help='Explicit project directory')
    args = parser.parse_args()
    install(args.project)
