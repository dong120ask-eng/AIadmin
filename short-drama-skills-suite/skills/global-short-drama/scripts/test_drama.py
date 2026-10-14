import copy
import json
import io
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import sys
import unittest
from unittest.mock import patch

from drama import Pipeline, read, save, read_session_key


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.c = read(Path(__file__).parent.parent / 'assets/project.example.json')
        self.c.update(episodes=1, minutes_per_episode=2/60, platforms=['hongguo', 'youtube'])
        self.c['genre'] = 'general'
        self.c['execution']['max_inflight_video_tasks'] = 1
        self.c['quality']['enabled'] = False
        self.c['ark'].update(text_model='fixture-text', video_model='fixture-video')
        self.c['ark']['video_options']['duration'] = 1
        self.c['render'] = {'width': 160, 'height': 240, 'fps': 10}
        self.script = {'title': '离线测试', 'synopsis': '合成测试，无真实供应商调用', 'shots': [{'id': i, 'seconds': 1, 'characters': ['c1'], 'visual': 'test', 'dialogue': '测试'} for i in [1, 2]]}

    def tearDown(self):
        self.temp.cleanup()

    def pipeline(self):
        return Pipeline(self.c, self.root / 'run')

    def seed_scripts(self, p):
        save(p.out / 'ep001/zh-CN/script.json', self.script)

    def test_plan_and_no_false_publication(self):
        p = self.pipeline()
        self.assertEqual(p.plan()['submitted_video_seconds'], 2)
        self.assertIsNone(p.plan()['estimated_cny'])
        p.package()
        rows = read(p.out / 'publish-manifest.json')
        self.assertTrue(all(x['status'] == 'missing_media' and not x['published'] for x in rows))

    def test_stdin_key_validation(self):
        self.assertEqual(read_session_key(io.StringIO('fixture-session-credential\n')), 'fixture-session-credential')
        for bad in ['', '\n', 'contains spaces\n', 'x' * 8193]:
            with self.assertRaises(ValueError):
                read_session_key(io.StringIO(bad))

    def test_session_key_authorization_without_environment_or_persistence(self):
        key = 'fixture-session-credential'
        p = Pipeline(self.c, self.root / 'run', api_key=key)
        response = io.BytesIO(b'{"ok":true}')
        with patch.dict(os.environ, {}, clear=True), patch('urllib.request.urlopen', return_value=response) as network:
            self.assertTrue(p.api('/chat/completions', {'model': 'fixture'})['ok'])
            self.assertEqual(network.call_args.args[0].get_header('Authorization'), 'Bearer ' + key)
        p.plan()
        p.package()
        for path in p.out.rglob('*.json'):
            self.assertNotIn(key, path.read_text(encoding='utf-8'))

    def test_cli_stdin_key_not_echoed_or_saved(self):
        key = 'fixture-cli-credential'
        cp = self.root / 'project.json'
        save(cp, self.c)
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('drama.py')), 'plan', '--config', str(cp), '--out', str(self.root / 'run'), '--key-stdin'], input=key + '\n', capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(key, result.stdout + result.stderr)
        for path in (self.root / 'run').rglob('*.json'):
            self.assertNotIn(key, path.read_text(encoding='utf-8'))

    def test_director_contract_and_change_detection(self):
        brief = {'schema_version': 1, 'topic': self.c['topic'], 'episodes': 1, 'minutes_per_episode': 2/60, 'language': 'zh-CN', 'episode_beats': [{'episode': 1, 'goal': 'a', 'obstacle': 'b', 'change': 'c', 'hook': 'd'}]}
        bp = self.root / 'brief.json'
        save(bp, brief)
        self.c['brief_path'] = str(bp)
        self.pipeline()
        brief['episode_beats'][0]['goal'] = 'changed'
        save(bp, brief)
        with self.assertRaisesRegex(ValueError, 'configuration changed'):
            self.pipeline()

    def test_invalid_director_rejected(self):
        bp = self.root / 'brief.json'
        save(bp, {'schema_version': 9})
        self.c['brief_path'] = str(bp)
        with self.assertRaisesRegex(ValueError, 'protocol mismatch'):
            self.pipeline()

    def test_changed_script_does_not_reuse_video(self):
        p = self.pipeline()
        self.seed_scripts(p)
        p.pin_script('1/zh-CN', self.script)
        self.script['shots'][0]['visual'] = 'changed scene'
        self.seed_scripts(p)
        with patch.object(p, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'script changed'):
                p.video([1])
            api.assert_not_called()

    def test_write_handoff_used_and_resume_skips_calls(self):
        p = self.pipeline()
        with patch.object(p, 'text', side_effect=[{'title': 'test', 'characters': [{'id': 'c1'}], 'episode_arcs': [{}]}, self.script]) as text:
            p.write([1])
            self.assertEqual(text.call_count, 2)
        with patch.object(p, 'text') as text:
            p.write([1])
            text.assert_not_called()

    def test_duration_validation(self):
        p = self.pipeline()
        self.script['shots'][1]['seconds'] = 8
        with self.assertRaises(ValueError):
            p.check_script(self.script)

    def test_unknown_submission_never_retried(self):
        p = self.pipeline()
        self.seed_scripts(p)
        with patch.dict(os.environ, {'ARK_API_KEY': 'test-only-not-secret'}), patch.object(p, 'api', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                p.video([1])
        p = self.pipeline()
        with patch.object(p, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'unknown submission'):
                p.video([1])
            api.assert_not_called()
        self.assertEqual(p.state['video_seconds'], 1)

    def test_submit_and_poll_resume_without_resubmit(self):
        p = self.pipeline()
        self.seed_scripts(p)
        with patch.dict(os.environ, {'ARK_API_KEY': 'test-only-not-secret'}), patch.object(p, 'api', return_value={'id': 'task-fixture'}) as api:
            self.assertEqual(p.video([1])['status'], 'submitted')
            self.assertEqual(api.call_count, 1)
        p = self.pipeline()
        with patch.object(p, 'api', return_value={'status': 'running'}) as api:
            self.assertEqual(p.video([1])['status'], 'running')
            self.assertEqual(api.call_args.args[0], '/contents/generations/tasks/task-fixture')
        self.assertEqual(p.state['video_seconds'], 1)

    def test_budget_blocks_submission(self):
        self.c['budget']['max_video_seconds'] = 0
        p = self.pipeline()
        self.seed_scripts(p)
        with patch.dict(os.environ, {'ARK_API_KEY': 'test-only-not-secret'}), patch.object(p, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'budget'):
                p.video([1])
            api.assert_not_called()

    def test_real_ffmpeg_render_and_voice_gate(self):
        p = self.pipeline()
        self.seed_scripts(p)
        folder = p.out / 'ep001/zh-CN/shots'
        folder.mkdir(parents=True)
        for i in [1, 2]:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=160x240:d=1', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-c:v', 'libx264', '-c:a', 'aac', '-shortest', str(folder / f'{i:03d}.mp4')], check=True)
        p.render([1])
        qc = read(p.out / 'ep001/zh-CN/qc.json')
        self.assertTrue(qc['mechanical_pass'])
        self.assertFalse(qc['voice_reviewed'])
        self.assertLess(abs(qc['duration'] - 2), .5)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=160x240:d=1', '-c:v', 'libx264', str(folder / '002.mp4')], check=True)
        with self.assertRaisesRegex(ValueError, 'voice track'):
            p.render([1])

    def test_three_minute_render_does_not_accumulate_aac_padding(self):
        self.c['minutes_per_episode'] = 3
        self.c['ark']['video_options']['duration'] = 5
        p = self.pipeline()
        self.script['shots'] = [{'id': i, 'seconds': 5, 'characters': ['c1'], 'visual': 'test', 'dialogue': '测试'} for i in range(1, 37)]
        self.seed_scripts(p)
        fixture = self.root / 'five-second.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=160x240:d=5', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=5', '-c:v', 'libx264', '-c:a', 'aac', '-shortest', str(fixture)], check=True)
        folder = p.out / 'ep001/zh-CN/shots'
        folder.mkdir(parents=True)
        for i in range(1, 37):
            shutil.copyfile(fixture, folder / f'{i:03d}.mp4')
        p.render([1])
        actual = read(p.out / 'ep001/zh-CN/qc.json')['duration']
        self.assertLess(abs(actual - 180), .5)


if __name__ == '__main__':
    unittest.main()
