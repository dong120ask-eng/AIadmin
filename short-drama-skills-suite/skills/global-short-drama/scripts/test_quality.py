import copy
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import json
from unittest.mock import patch

from drama import Pipeline, read, save
from story_rules import catalog, genre_spec, rules_for, review_verdict


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.c = read(Path(__file__).parent.parent / 'assets/project.example.json')
        self.c.update(episodes=1, minutes_per_episode=.5, genre='suspense', languages=['zh-CN'])
        self.c['execution']['max_inflight_video_tasks'] = 1
        self.c['ark'].update(text_model='fixture-text', video_model='fixture-video')
        self.p = Pipeline(self.c, self.root / 'run', api_key='fixture-credential')
        self.bible = {'schema_version': 2, 'title': '离线悬疑测试', 'characters': [{'id': 'c1', 'name': '林舟', 'appearance': '短发青年，左眉有浅痕', 'costume': '灰色工作外套', 'voice': '普通话低声、克制', 'motivation': '找出断电原因'}], 'episode_arcs': [{'episode': 1, 'goal': '检查故障', 'obstacle': '记录与现场矛盾', 'choice': '亲自检验', 'consequence': '发现记录被改', 'payoff': '确认故障来源', 'hook': '恢复供电并承担责任'}], 'clues': []}
        self.script = {'schema_version': 2, 'title': '停电之夜', 'synopsis': '测试用原创短片', 'story': {'goal': '恢复供电', 'obstacle': '设备记录不符', 'strategy': '查现场物证', 'choice': '亲自测试开关', 'consequence': '找到篡改痕迹', 'payoff': '修复断路', 'hook': '面对责任'}, 'clues': [], 'shots': []}
        for i, (visual, dialogue) in enumerate([('林舟看见暗下来的走廊，握紧工具包。', '怎么停了？'), ('近景：记录显示正常，设备指示灯却熄灭。', '记录不对。'), ('他查看电箱旧封条，再看手里的维修单。', '谁拆过封条？'), ('镜头聚焦旧封条下的新划痕，林舟停下。', '是新的痕迹。'), ('林舟举起被改过的检修单，与同事核对。', '先恢复供电。'), ('走廊灯恢复，同事点头，林舟留下检修记录。', '责任也要查清。')], 1):
            self.script['shots'].append({'id': i, 'seconds': 5, 'characters': ['c1'], 'scene_id': 'corridor', 'purpose': '查证推动行动和状态变化', 'visual': visual, 'audio_kind': 'dialogue', 'speaker': 'c1', 'dialogue': dialogue})

    def tearDown(self):
        self.temp.cleanup()

    def seed(self):
        save(self.p.out / 'bible.json', self.bible)
        save(self.p.out / 'ep001/source.json', self.script)
        save(self.p.out / 'ep001/zh-CN/script.json', self.script)

    def report(self, passed=True):
        dimensions = catalog()['common']['dimensions']
        return {'scores': {x: 2 for x in dimensions}, 'dimension_evidence': {x: {'shot_ids': [1, 4, 6], 'reason': '测试证据，模拟编辑而非真实评分'} for x in dimensions}, 'genre_checks': [{'criterion': x, 'pass': passed, 'shot_ids': [2, 4, 6], 'reason': '模拟类型审稿'} for x in rules_for('suspense')['primary']['review_checks']], 'issues': [] if passed else [{'severity': 'major', 'shot_ids': [3], 'reason': '线索需要更明确呈现', 'repair': '展示封条旧痕与新痕的差异'}]}

    def test_eighteen_genres_have_distinct_engines(self):
        genres = catalog()['genres']
        self.assertEqual(len(genres) - 1, 18)
        self.assertEqual(len({g['episode_engine'] for g in genres.values()}), len(genres))
        for code in genres:
            self.assertEqual(rules_for(code)['primary']['label'], genres[code]['label'])
            self.assertTrue(genres[code]['review_checks'])

    def test_primary_and_secondary_not_visual_form(self):
        selected = genre_spec({'primary': 'romance', 'secondary': ['comedy'], 'tropes': ['先婚后爱']})
        self.assertEqual(rules_for(selected)['primary']['label'], '爱情与甜宠')
        for invalid in ['3d', {'primary': 'romance', 'secondary': ['romance']}, {'primary': 'comedy', 'secondary': ['family', 'scifi', 'action']}]:
            with self.assertRaises(ValueError):
                genre_spec(invalid)

    def test_cli_genre_names_are_utf8(self):
        cp = self.root / 'config.json'
        save(cp, self.c)
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('drama.py')), 'genres', '--config', str(cp), '--out', str(self.root / 'cli')], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['romance'], '爱情与甜宠')

    def test_missing_task_and_overlong_dialogue_block(self):
        self.seed()
        self.p.check_script(self.script)
        invalid = copy.deepcopy(self.script)
        del invalid['story']['choice']
        with self.assertRaisesRegex(ValueError, 'story requires'):
            self.p.check_script(invalid)
        invalid = copy.deepcopy(self.script)
        invalid['shots'][0]['dialogue'] = '这是远远超过五秒钟可以自然说完的一大段解释世界观的对白' * 3
        with self.assertRaisesRegex(ValueError, 'speech budget'):
            self.p.check_script(invalid)

    def test_ambience_shot_is_allowed(self):
        self.seed()
        script = copy.deepcopy(self.script)
        script['shots'][0].update(dialogue='', speaker='none', audio_kind='ambience')
        self.p.check_script(script)

    def test_character_ids_and_clue_payoff_checked(self):
        self.seed()
        invalid = copy.deepcopy(self.script)
        invalid['shots'][0]['speaker'] = 'invented-person'
        with self.assertRaisesRegex(ValueError, 'unknown character'):
            self.p.check_script(invalid)
        self.bible['clues'] = [{'id': 'seal', 'meaning': '封条被拆证明记录有问题', 'introduced_episode': 1, 'resolved_episode': 1}]
        save(self.p.out / 'bible.json', self.bible)
        with self.assertRaisesRegex(ValueError, 'setup missing'):
            self.p.check_episode_clues(1, self.script)
        self.script['clues'] = [{'id': 'seal', 'action': 'plant', 'shot_id': 3}, {'id': 'seal', 'action': 'payoff', 'shot_id': 5}]
        self.p.check_episode_clues(1, self.script)

    def test_failed_genre_check_beats_perfect_numeric_score(self):
        self.assertFalse(review_verdict(self.report(False), self.script, rules_for('suspense'))['passed'])

    def test_fictional_evidence_ids_rejected(self):
        report = self.report()
        report['dimension_evidence']['causality']['shot_ids'] = [999]
        with self.assertRaisesRegex(ValueError, 'actual shot'):
            review_verdict(report, self.script, rules_for('suspense'))

    def test_failed_review_blocks_video_and_exhaustion_does_not_repeat(self):
        self.seed()
        self.p.quality['max_revisions'] = 0
        with patch.object(self.p, 'text', return_value=self.report(False)) as text, patch.object(self.p, 'api') as api:
            self.assertEqual(self.p.run([1])['status'], 'review_failed')
            self.assertEqual(self.p.run([1])['status'], 'review_failed')
            self.assertEqual(text.call_count, 1)
            api.assert_not_called()

    def test_oneclick_rewrites_then_submits_with_fixed_character_prompt(self):
        self.seed()
        revised = copy.deepcopy(self.script)
        revised['shots'][2]['visual'] += '封条旧痕下压着一道新划痕。'
        with patch.object(self.p, 'text', side_effect=[self.report(False), revised, self.report()]), patch.object(self.p, 'api', return_value={'id': 'test-video-task'}) as api:
            self.assertEqual(self.p.run([1])['status'], 'submitted')
            prompt = api.call_args.args[1]['content'][0]['text']
            self.assertIn('左眉有浅痕', prompt)
            self.assertIn('普通话低声、克制', prompt)
        with patch.object(self.p, 'text') as text, patch.object(self.p, 'api', return_value={'status': 'running'}) as api:
            self.assertEqual(self.p.run([1])['status'], 'running')
            text.assert_not_called()
            self.assertEqual(api.call_args.args[0], '/contents/generations/tasks/test-video-task')

    def test_unreviewed_or_stale_script_cannot_generate_video(self):
        self.seed()
        with patch.object(self.p, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'review before'):
                self.p.video([1])
            api.assert_not_called()
        with patch.object(self.p, 'text', return_value=self.report()):
            self.p.review([1])
        modified = copy.deepcopy(self.script)
        modified['shots'][0]['visual'] = '一幕新的场景'
        save(self.p.out / 'ep001/zh-CN/script.json', modified)
        with patch.object(self.p, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'stale'):
                self.p.video([1])
            api.assert_not_called()

    def test_genre_rules_reach_bible_and_episode_generation(self):
        with patch.object(self.p, 'text', side_effect=[self.bible, self.script]) as text:
            self.p.write([1])
            for call in text.call_args_list:
                self.assertIn('公平线索', call.args[0])
                self.assertIn('观众此前能看到的线索', call.args[0])
        self.assertGreater(self.p.plan()['maximum_planned_text_calls'], self.p.plan()['estimated_text_calls'])

    def test_auto_selection_cached(self):
        self.c['genre'] = 'auto'
        p = Pipeline(self.c, self.root / 'auto')
        with patch.object(p, 'text', return_value={'primary': 'family', 'secondary': ['period'], 'tropes': []}) as text:
            self.assertEqual(p.genre_rules()['primary']['label'], '家庭伦理与亲情')
            p.genre_rules()
            self.assertEqual(text.call_count, 1)

    def test_v2_handoff_requires_complete_task_and_matching_genre(self):
        brief = {'schema_version': 2, 'topic': self.c['topic'], 'episodes': 1, 'minutes_per_episode': .5, 'language': 'zh-CN', 'genre': 'suspense', 'episode_beats': [{'episode': 1, **self.script['story'], 'change': '状态改变'}]}
        bp = self.root / 'director.json'
        save(bp, brief)
        self.c['brief_path'] = str(bp)
        Pipeline(self.c, self.root / 'valid-handoff')
        del brief['episode_beats'][0]['strategy']
        save(bp, brief)
        with self.assertRaisesRegex(ValueError, 'strategy'):
            Pipeline(self.c, self.root / 'invalid-handoff')
        brief['episode_beats'][0]['strategy'] = '查证'
        brief['genre'] = 'romance'
        save(bp, brief)
        with self.assertRaisesRegex(ValueError, 'genre mismatch'):
            Pipeline(self.c, self.root / 'mismatch')

    def test_bible_change_invalidates_previously_passed_review(self):
        self.seed()
        with patch.object(self.p, 'text', return_value=self.report()):
            self.p.review([1])
        self.bible['characters'][0]['motivation'] = '新的角色动机'
        save(self.p.out / 'bible.json', self.bible)
        with patch.object(self.p, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'stale'):
                self.p.video([1])
            api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
