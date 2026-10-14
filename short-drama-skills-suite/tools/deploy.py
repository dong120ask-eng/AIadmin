"""Copy all skill bundles after review. Defaults to a read-only deployment plan."""
import argparse
import json
from pathlib import Path
import shutil
import sys

SKILLS = ['short-drama-hub', 'cn-drama-director', 'global-short-drama', 'drama-assets', 'drama-postproduction', 'drama-release', 'drama-growth', 'drama-market-research']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser()
    p.add_argument('--target', required=True, choices=['codex', 'deepseek', 'workbuddy'])
    p.add_argument('--root', help='explicit approved skill-root override')
    p.add_argument('--apply', action='store_true', help='copy only after explicit installation approval')
    a = p.parse_args()
    bundle = Path(__file__).resolve().parent.parent
    source = bundle / 'skills' if (bundle / 'skills').is_dir() else bundle
    user_home = Path.home()
    default = {'codex': user_home / '.codex/skills', 'deepseek': user_home / '.dsh/skills', 'workbuddy': user_home / '.workbuddy/skills'}
    destination = Path(a.root).resolve() if a.root else default[a.target].resolve()
    rows = [{'skill': name, 'source': str((source/name).resolve()), 'target': str(destination/name), 'exists': (destination/name).exists()} for name in SKILLS]
    if not all((source/name/'SKILL.md').is_file() for name in SKILLS):
        raise ValueError('incomplete source bundle')
    if a.apply:
        if any(row['exists'] for row in rows):
            raise ValueError('existing skill would be overwritten; choose a new root or review an update separately')
        destination.mkdir(parents=True, exist_ok=True)
        for name in SKILLS:
            shutil.copytree(source/name, destination/name, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    print(json.dumps({'mode': 'copied_needs_runtime_validation' if a.apply else 'dry_run_no_install', 'target': a.target, 'skills': rows, 'workbuddy_note': 'UI import is the verified route; direct directory copy requires checking actual skill discovery'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
