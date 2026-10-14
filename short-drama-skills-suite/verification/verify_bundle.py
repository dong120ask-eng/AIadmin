"""Validate this bundle's simple frontmatter and resources without installing YAML."""
import json
from pathlib import Path
import re
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
skill_root = root / 'skills' if (root / 'skills').is_dir() else root
for name in ['short-drama-hub', 'cn-drama-director', 'global-short-drama', 'drama-assets', 'drama-postproduction', 'drama-release', 'drama-growth', 'drama-market-research']:
    folder = skill_root / name
    content = (folder / 'SKILL.md').read_text(encoding='utf-8')
    match = re.match(r'^---\n(.*?)\n---\n', content, re.S)
    assert match, f'{name}: missing frontmatter'
    fields = dict(line.split(':', 1) for line in match[1].splitlines())
    assert set(fields) == {'name', 'description'}
    assert fields['name'].strip() == name
    assert re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) and len(name) < 64
    assert 10 < len(fields['description'].strip()) < 1024
    for ref in re.findall(r'\]\(((?:references|assets)/[^)]+)\)', content):
        assert (folder / ref).is_file(), f'missing resource: {ref}'
    for path in folder.rglob('*.json'):
        json.loads(path.read_text(encoding='utf-8-sig'))
    print(name + ': frontmatter, references and JSON OK')

from importlib.util import module_from_spec, spec_from_file_location
spec = spec_from_file_location('drama', skill_root / 'global-short-drama/scripts/drama.py')
sys.path.insert(0, str(skill_root / 'global-short-drama/scripts'))
drama = module_from_spec(spec)
spec.loader.exec_module(drama)
c = drama.read(skill_root / 'global-short-drama/assets/project.example.json')
brief = {
    'schema_version': 2, 'topic': c['topic'], 'episodes': c['episodes'],
    'minutes_per_episode': c['minutes_per_episode'], 'language': 'zh-CN',
    'genre': {'primary': 'suspense', 'secondary': ['scifi'], 'tropes': []},
    'audience': '普通话悬疑漫剧观众', 'emotional_promise': '以能力与证据赢回主动权',
    'constraints': ['原创3D漫剧', '自然普通话', '主角主动行动', '线索先种后收'],
    'production_notes': {'visual_style': c['style'], 'voice': '标准普通话', 'pilot_first': True},
    'episode_beats': [
        {'episode': 1, 'goal': '核验倒计时装置', 'obstacle': '记忆缺失且访问受限', 'change': '发现熟悉的设计标记', 'hook': '标记为何出自她手'},
        {'episode': 2, 'goal': '追溯设计记录', 'obstacle': '记录与现场不符', 'change': '找到篡改痕迹', 'hook': '谁在她失忆后修改系统'},
        {'episode': 3, 'goal': '恢复关键权限', 'obstacle': '同事不信任她', 'change': '用现场修复证明能力', 'hook': '获得权限却发现第二重故障'},
        {'episode': 4, 'goal': '隔离故障节点', 'obstacle': '停机将损害另一片区', 'change': '决定承担风险先疏散', 'hook': '疏散路线本身出现疑点'},
        {'episode': 5, 'goal': '找出真实故障来源', 'obstacle': '倒计时接近终点', 'change': '回收第一集设计标记线索', 'hook': '必须作出不可两全的修复选择'},
        {'episode': 6, 'goal': '完成修复并公开证据', 'obstacle': '执行窗口极短', 'change': '依靠团队协作恢复安全，查清篡改', 'hook': '兑现真相与人物责任，故事收束'}
    ],
    'evidence': [{'source': '用户样本分享页与原创推断', 'level': 'C', 'observation': '能力被低估的主角通过行动改变状态', 'inference': '用于原创悬疑题材试验，不是验证过的爆款'}]
}
for beat in brief['episode_beats']:
    beat.update(strategy='依据已出现的线索进行现场核验', choice=beat['goal'], consequence=beat['change'], payoff=beat['change'])
demo = tempfile.TemporaryDirectory()
bp = Path(demo.name) / 'director-brief.json'
drama.save(bp, brief)
c['brief_path'] = str(bp.resolve())
drama.save(Path(demo.name) / 'project.json', c)
pipeline = drama.Pipeline(c, Path(demo.name) / 'run-suite')
print(json.dumps(pipeline.plan(), ensure_ascii=False))
demo.cleanup()
