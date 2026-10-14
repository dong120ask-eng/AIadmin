"""Maintain precise skill implementation categories and source entrypoints."""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
entries=[]
for f in sorted((ROOT/'skills').glob('*/SKILL.md')):
    meta=yaml.safe_load(f.read_text(encoding='utf-8').split('---',2)[1]); scripts=sorted((f.parent/'scripts').glob('*.py'))
    kind='shared-platform-executor' if f.parent.name.startswith('publish-') else 'script-and-instructions' if scripts else 'instruction-workflow'
    entries.append({'name':meta['name'],'description':meta['description'],'entry':f.relative_to(ROOT).as_posix(),'development':kind,'runtime_acceptance':'pending-real-environment','scripts':[s.relative_to(ROOT).as_posix() for s in scripts]})
platforms=json.loads((ROOT/'config/platforms.json').read_text(encoding='utf-8'))['platforms']
(ROOT/'config/skill-manifest.json').write_text(json.dumps({'version':'2026-10-14-r5','skill_count':len(entries),'platform_count':len(platforms),'skills':entries},ensure_ascii=False,indent=2),encoding='utf-8')
print('skills:',len(entries),'platforms:',len(platforms))
