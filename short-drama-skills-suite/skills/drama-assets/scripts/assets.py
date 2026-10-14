import argparse
import json
from pathlib import Path
import sys


def build(bible, run):
    characters = []
    for person in bible['characters']:
        characters.append({'id': person['id'], 'name': person.get('name'), 'appearance': person.get('appearance'), 'costume': person.get('costume'), 'voice': person.get('voice'), 'image_prompt': '原创角色设定，同一人物正面/侧面/全身，清晰自然光，无文字。外形：' + str(person.get('appearance', '')) + '；服装：' + str(person.get('costume', '')), 'image_generated': False})
    shots, scenes = {}, {}
    for path in sorted(Path(run).glob('ep*/*/script.json')):
        episode = int(path.parent.parent.name.removeprefix('ep'))
        script = json.loads(path.read_text(encoding='utf-8-sig'))
        for shot in script['shots']:
            key = f"{episode}/{path.parent.name}/{shot['id']}"
            shots[key] = {'characters': shot['characters'], 'scene_id': shot.get('scene_id'), 'speaker': shot.get('speaker'), 'reference_images_needed': bool(shot['characters'])}
            scene = shot.get('scene_id', 'unassigned')
            scenes.setdefault(scene, []).append({'shot': key, 'visual': shot['visual']})
    return {'characters': characters, 'scenes': scenes, 'shot_assignments': shots, 'status': 'plan_not_generated_assets'}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser()
    p.add_argument('--bible', required=True)
    p.add_argument('--run', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bible = json.loads(Path(a.bible).read_text(encoding='utf-8-sig'))
    plan = build(bible, a.run)
    (out / 'asset-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    manifest = out / 'asset-manifest.json'
    if not manifest.exists():
        manifest.write_text(json.dumps({'schema_version': 1, 'shots': {key: [] for key in plan['shot_assignments']}}, indent=2), encoding='utf-8')
    print(json.dumps({'status': plan['status'], 'characters': len(plan['characters']), 'shots': len(plan['shot_assignments'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
