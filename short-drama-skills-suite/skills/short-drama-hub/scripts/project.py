import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['init', 'doctor'])
    p.add_argument('--topic')
    p.add_argument('--episodes', type=int, default=6)
    p.add_argument('--minutes', type=float, default=1)
    p.add_argument('--genre', default='auto')
    p.add_argument('--text-model', default='')
    p.add_argument('--video-model', default='')
    p.add_argument('--out')
    p.add_argument('--config')
    a = p.parse_args()
    core = Path(__file__).resolve().parents[2] / 'global-short-drama'
    sys.path.insert(0, str(core / 'scripts'))
    from drama import validate
    if a.command == 'init':
        if not a.topic or not a.out:
            p.error('init requires --topic and --out')
        c = json.loads((core / 'assets/project.example.json').read_text(encoding='utf-8'))
        c.update(topic=a.topic, episodes=a.episodes, minutes_per_episode=a.minutes, genre=a.genre)
        c['ark'].update(text_model=a.text_model, video_model=a.video_model)
        validate(c)
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        target = out / 'project.json'
        if target.exists():
            raise ValueError('project already exists; do not overwrite')
        target.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf-8')
        result = {'status': 'project_initialized', 'config': str(target.resolve()), 'credentials_saved': False, 'director_brief_created': False}
    else:
        if not a.config:
            p.error('doctor requires --config')
        c = json.loads(Path(a.config).read_text(encoding='utf-8-sig'))
        validate(c)
        result = {'python': sys.version.split()[0], 'python_supported': sys.version_info >= (3,10), 'ffmpeg': bool(shutil.which('ffmpeg')), 'ffprobe': bool(shutil.which('ffprobe')), 'missing_models': [k for k in ['text_model', 'video_model'] if not c['ark'].get(k)], 'api_access_verified': False, 'browser_and_platform_access': 'host_runtime_verification_required', 'credentials_read_or_saved': False}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
