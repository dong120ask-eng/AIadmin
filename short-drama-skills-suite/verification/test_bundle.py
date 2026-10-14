import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import io
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = ROOT / 'skills' if (ROOT / 'skills').is_dir() else ROOT
sys.path.insert(0, str(SKILL_ROOT / 'global-short-drama/scripts'))
from drama import Pipeline, read, save, main as drama_main
from runtime_support import reference_content


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, SKILL_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


media = load('bundle_media', 'drama-postproduction/scripts/media.py')
release = load('bundle_release', 'drama-release/scripts/release.py')
growth = load('bundle_growth', 'drama-growth/scripts/growth.py')
assets = load('bundle_assets', 'drama-assets/scripts/assets.py')
research = load('bundle_research', 'drama-market-research/scripts/research.py')


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.c = read(SKILL_ROOT / 'global-short-drama/assets/project.example.json')
        self.c.update(episodes=1, minutes_per_episode=2/60, genre='general')
        self.c['quality']['enabled'] = False
        self.c['ark']['video_options']['duration'] = 1
        self.c['ark']['video_model'] = 'fixture-video'
        self.c['render'] = {'width':160,'height':240,'fps':10}
        self.script = {'title':'test','synopsis':'fixture','shots':[{'id':i,'seconds':1,'characters':['c1'],'visual':'blue test scene','dialogue':'测试','scene_id':'test-scene','speaker':'c1'} for i in [1,2]]}

    def tearDown(self):
        self.temp.cleanup()

    def seed(self, p):
        save(p.out / 'ep001/zh-CN/script.json', self.script)

    def fixture_video(self):
        path = self.root/'fixture.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x240:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-c:a','aac','-shortest',str(path)],check=True)
        return path

    def test_bounded_scheduler_submits_second_before_polling_first(self):
        p = Pipeline(self.c,self.root/'run',api_key='fixture-key')
        self.seed(p)
        with patch.object(p,'api',side_effect=[{'id':'task-one'},{'id':'task-two'},{'status':'running'}]) as api:
            self.assertEqual(p.video([1])['shot'],'1/zh-CN/1')
            self.assertEqual(p.video([1])['shot'],'1/zh-CN/2')
            self.assertEqual(p.video([1])['status'],'running')
            self.assertEqual(api.call_args.args[0],'/contents/generations/tasks/task-one')
        self.assertEqual(p.state['video_seconds'],2)

    def test_reference_modes_and_rights(self):
        item = {'url':'https://example.com/original.png','role':'reference_image','rights_confirmed':True,'contains_real_face':False}
        manifest={'shots':{'1/zh-CN/1':[item]}}
        result=reference_content(manifest,'1/zh-CN/1',{'reference_images_supported':True})
        self.assertEqual(result[0]['role'],'reference_image')
        with self.assertRaises(ValueError):
            reference_content(manifest,'1/zh-CN/1',{})
        manifest['shots']['1/zh-CN/1'].append({**item,'role':'first_frame'})
        with self.assertRaisesRegex(ValueError,'mix'):
            reference_content(manifest,'1/zh-CN/1',{'reference_images_supported':True})

    def test_reference_payload_reaches_actual_request(self):
        mp=self.root/'assets.json'
        save(mp,{'shots':{'1/zh-CN/1':[{'url':'https://example.com/original.png','role':'reference_image','rights_confirmed':True}]}})
        self.c['assets'].update(manifest_path=str(mp),reference_images_supported=True)
        p=Pipeline(self.c,self.root/'run',api_key='fixture-key')
        self.seed(p)
        with patch.object(p,'api',return_value={'id':'fixture'}) as api:
            p.video([1])
            self.assertEqual(api.call_args.args[1]['content'][1]['image_url']['url'],'https://example.com/original.png')

    def test_credentials_in_config_rejected(self):
        self.c['ark']['api_key']='fixture-key'
        with self.assertRaisesRegex(ValueError,'credentials'):
            Pipeline(self.c,self.root/'run')

    def test_structure_retry_repairs_once_and_exhaustion_is_durable(self):
        p=Pipeline(self.c,self.root/'run')
        def check(v):
            if not v.get('valid'):
                raise ValueError('needs valid')
        with patch.object(p,'text',side_effect=[{}, {'valid':True}]) as text:
            self.assertTrue(p.checked_text('prompt',check,'repair')['valid'])
            self.assertEqual(text.call_count,2)
        with patch.object(p,'text',return_value={}) as text:
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'exhausted'):
                    p.checked_text('prompt',check,'failure')
            self.assertEqual(text.call_count,2)

    def test_asset_plan_tracks_real_cast_and_shots(self):
        p=Pipeline(self.c,self.root/'run')
        self.seed(p)
        plan=assets.build({'characters':[{'id':'c1','name':'测试','appearance':'短发','costume':'灰衣','voice':'普通话'}]},p.out)
        self.assertEqual(plan['shot_assignments']['1/zh-CN/1']['characters'],['c1'])
        self.assertFalse(plan['characters'][0]['image_generated'])

    def test_subtitle_timing_rejects_overlap_nan_and_overflow(self):
        out=self.root/'captions.srt'
        media.write_srt({'segments':[{'start':0,'end':1,'text':'你好'},{'start':1,'end':2,'text':'再见'}]},2,out)
        self.assertIn('你好',out.read_text(encoding='utf-8'))
        for segment in [{'start':float('nan'),'end':1,'text':'a'},{'start':0,'end':3,'text':'a'}]:
            with self.assertRaises(ValueError):
                media.write_srt({'segments':[segment]},2,out)
        with self.assertRaises(ValueError):
            media.write_srt({'segments':[{'start':0,'end':1.5,'text':'a'},{'start':1,'end':2,'text':'b'}]},2,out)

    def test_real_postproduction_burn_cover_mix_qc(self):
        video=self.fixture_video()
        srt=self.root/'captions.srt'
        media.write_srt({'segments':[{'start':0,'end':1,'text':'中文字幕测试'}]},2.02,srt)
        delivery=self.root/'burned.mp4'
        media.burn(video,srt,delivery)
        font=Path('C:/Windows/Fonts/msyh.ttc')
        cover=self.root/'cover.jpg'
        media.cover(video,.5,'短剧封面测试',font if font.exists() else None,cover) if font.exists() else media.cover(video,.5,'',None,cover)
        mixed=self.root/'mixed.mp4'
        media.mix(delivery,video,.1,mixed)
        report=media.qc(mixed)
        self.assertTrue(report['scan_completed'])
        self.assertTrue(report['human_review_required'])
        self.assertLess(abs(report['duration']-2),.2)
        self.assertTrue(cover.is_file())

    def test_media_changes_invalidate_publish_manifest(self):
        p=Pipeline(self.c,self.root/'run')
        self.seed(p)
        folder=p.out/'ep001/zh-CN'
        video=self.fixture_video()
        import shutil
        (folder/'shots').mkdir()
        for i in [1,2]:
            shutil.copyfile(video,folder/'shots'/f'{i:03d}.mp4')
        p.render([1])
        p.package()
        self.assertTrue(read(p.out/'publish-manifest.json')[0]['media_current'])
        (folder/'shots/001.wav').write_bytes(b'changed-voice-fixture')
        p.package()
        self.assertFalse(read(p.out/'publish-manifest.json')[0]['media_current'])

    def test_release_requires_materials_and_deduplicates_receipts(self):
        video=self.fixture_video()
        subtitle=self.root/'srt.srt'
        subtitle.write_text('test',encoding='utf-8')
        row={'platform':'hongguo','episode':1,'language':'zh-CN','video':str(video),'subtitle':str(subtitle),'qc':{},'rights':{},'filing':{}}
        queue=release.prepare([row],'hongguo','test-account')
        self.assertFalse(queue[0]['ready'])
        log=self.root/'log.jsonl'
        receipt={'release_id':queue[0]['release_id'],'status':'published','evidence':'test observed backend'}
        with self.assertRaises(ValueError):
            release.record(queue,receipt,log)
        receipt.update(remote_id='fixture-remote',access_token='do-not-store-fixture',account='wrong-account')
        release.record(queue,receipt,log)
        self.assertFalse(release.record(queue,receipt,log)['appended'])
        saved=json.loads(log.read_text(encoding='utf-8').strip())
        self.assertEqual(saved['account'],'test-account')
        self.assertNotIn('do-not-store-fixture',log.read_text(encoding='utf-8'))

    def test_metrics_weighted_denominators_unknown_and_duplicates(self):
        base={'platform':'test','account':'a','language':'zh-CN','genre':'suspense','cohort':'c','window_hours':'24','episode_seconds':'60','variant':'A','plays':'100','starts':'100','retained_starts':'50','completions':'40','next_episode_clicks':'20','likes':''}
        rows=[{**base,'content_id':'1'},{**base,'content_id':'2','plays':'300','starts':'300','retained_starts':'250','completions':'160','next_episode_clicks':'100','likes':'30'}]
        report=growth.analyze(rows)
        rates=report['groups'][0]['rates']
        self.assertEqual(rates['completion']['value'],.5)
        self.assertEqual(rates['like_rate']['value'],.1)
        self.assertFalse(report['causal_claims_supported'])
        with self.assertRaises(ValueError):
            growth.analyze([rows[0],rows[0]])

    def test_project_init_and_doctor(self):
        script=SKILL_ROOT/'short-drama-hub/scripts/project.py'
        project=self.root/'project'
        result=subprocess.run([sys.executable,str(script),'init','--topic','原创测试话题','--episodes','2','--minutes','1','--out',str(project)],capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        result=subprocess.run([sys.executable,str(script),'doctor','--config',str(project/'project.json')],capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(json.loads(result.stdout)['api_access_verified'])

    def test_deployment_preview_does_not_install(self):
        destination=self.root/'skills'
        result=subprocess.run([sys.executable,str(ROOT/'tools/deploy.py'),'--target','codex','--root',str(destination)],capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(destination.exists())
        self.assertEqual(len(json.loads(result.stdout)['skills']),8)

    def test_research_rejects_fabricated_evidence_levels_and_marks_limits(self):
        data = read(SKILL_ROOT/'drama-market-research/assets/research.example.json')
        self.assertFalse(research.build(data)['causal_claims_supported'])
        data['cases'][0]['evidence_level'] = 'A'
        with self.assertRaises(ValueError):
            research.build(data)

    def test_release_attestation_binds_final_video_and_subtitle(self):
        video = self.fixture_video()
        subtitle = self.root/'caption.srt'
        subtitle.write_text('reviewed subtitle', encoding='utf-8')
        row = {'platform':'youtube','episode':1,'language':'zh-CN','video':str(video),'subtitle':str(subtitle),'asset_sha256':release.sha(video),'media_current':True,'script_review':{'passed':True},'qc':{'mechanical_pass':True},'rights':{'original_or_licensed':True,'music_cleared':True,'voice_cleared':True}}
        self.assertFalse(release.prepare([row],'youtube','test')[0]['ready'])
        release.attest([row], 'test-reviewer')
        self.assertTrue(release.prepare([row],'youtube','test')[0]['ready'])
        subtitle.write_text('different subtitle',encoding='utf-8')
        self.assertIn('human_review_missing_or_stale', release.prepare([row],'youtube','test')[0]['missing'])
        row['script_review']['passed'] = False
        self.assertIn('script_review_not_passed', release.prepare([row],'youtube','test')[0]['missing'])

    def test_multimodal_voice_reference_requires_consent_and_model_support(self):
        item = {'url':'https://example.com/voice.wav','role':'reference_audio','rights_confirmed':True,'voice_consent_confirmed':True,'duration_seconds':3}
        data = {'shots':{'1/zh-CN/1':[item]}}
        cfg = {'multimodal_references_supported':True,'audio_only_reference_supported':True}
        self.assertEqual(reference_content(data,'1/zh-CN/1',cfg)[0]['type'],'audio_url')
        item['voice_consent_confirmed'] = False
        with self.assertRaises(ValueError):
            reference_content(data,'1/zh-CN/1',cfg)

    def test_scene_continuity_reaches_video_prompt(self):
        p = Pipeline(self.c,self.root/'run',api_key='fixture-key')
        self.seed(p)
        save(p.out/'bible.json',{'locations':[{'id':'test-scene','description':'走廊','lighting':'暖光','props':'灰色工具箱','axis':'门在画面左侧'}],'continuity':['衣服不变']})
        with patch.object(p,'api',return_value={'id':'fixture'}) as api:
            p.video([1])
            prompt=api.call_args.args[1]['content'][0]['text']
            self.assertIn('灰色工具箱',prompt)
            self.assertIn('adjacent_shots',prompt)

    def test_reviewer_model_routes_to_distinct_endpoint_model(self):
        self.c['ark'].update(text_model='writer',review_model='critic')
        p = Pipeline(self.c,self.root/'run',api_key='fixture-key')
        with patch.object(p,'api',return_value={'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]}) as api:
            p.checked_text('review',lambda x: None,'review-routing',model=self.c['ark']['review_model'])
            self.assertEqual(api.call_args.args[1]['model'],'critic')

    def test_stale_review_does_not_pass_publish_manifest(self):
        p = Pipeline(self.c,self.root/'run')
        self.seed(p)
        p.review_required = True
        save(p.out/'ep001/zh-CN/review.json',{'passed':True,'assessment':'old-review'})
        with patch.object(p,'require_review',side_effect=ValueError('stale review')):
            p.package()
        row = read(p.out/'publish-manifest.json')[0]
        self.assertFalse(row['script_review']['passed'])
        with patch.object(p,'require_review'):
            p.package()
        self.assertTrue(read(p.out/'publish-manifest.json')[0]['script_review']['passed'])

    def test_until_ready_stops_at_review_without_repeated_key_entry(self):
        cp=self.root/'project.json'
        save(cp,self.c)
        args=['drama.py','run','--config',str(cp),'--out',str(self.root/'run'),'--key-stdin','--until-ready','--max-steps','2','--poll-seconds','1']
        output=io.StringIO()
        with patch('sys.argv',args),patch('sys.stdin',io.StringIO('fixture-credential\n')),patch('sys.stdout',output),patch.object(Pipeline,'run',side_effect=[{'stage':'video','status':'running'},{'stage':'review','status':'package_created'}]) as runner,patch('drama.time.sleep') as sleep:
            drama_main()
            self.assertEqual(runner.call_count,2)
            sleep.assert_called_once_with(1)
        self.assertNotIn('fixture-credential',output.getvalue())
        self.assertNotIn('step_limit_reached',output.getvalue())


if __name__ == '__main__':
    unittest.main()
