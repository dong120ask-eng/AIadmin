import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
adapter=load('tested_platform_adapter','skills/platform-content-adapter/scripts/adapter.py')
ops=load('tested_platform_ops','skills/dsh-selfmedia-hub/scripts/ops.py')
engine=load('tested_platform_engine','skills/publishing-workflow-runner/scripts/engine.py')

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'body.md').write_text('Own verified content',encoding='utf-8')
        (self.root/'observed.txt').write_text('Actual account settings review',encoding='utf-8')
    def task(self,pid='x',media=None):
        l=ops.Ledger(self.root)
        try:
            l.register({'id':'one','device_id':'browser-one','platform':pid,'package_name':'browser.creator','account_id':'my-account','account_alias':'Mine','launch_mode':'primary'})
            return l.create('one','Own title','body.md',media or [],'private')
        finally:l.db.close()
    def profile(self,t,fmt='text'):
        policy=adapter.capabilities()[t['instance']['platform']]
        return {'schema':'publishing-profile/v1','backend':'browser','platform':t['instance']['platform'],'account_id':'my-account','device_id':'browser-one',
                'location':'https://x.com/compose/post','cdp':'http://127.0.0.1:9222','identity_selector':'#observed-account','visibility_value':'private','visibility_selector':'#observed-visibility','visibility_text':'Observed private',
                'content_format':fmt,'draft_steps':[{'action':'fill','selector':'#observed-body','value':'body'}],
                'platform_review':{'task_id':t['id'],'fingerprint':t['fingerprint'],'reviewer':'human','confirmed':dict.fromkeys(policy['review_fields'],True),'evidence':[{'path':'observed.txt','sha256':hashlib.sha256((self.root/'observed.txt').read_bytes()).hexdigest()}]}}
    def test_six_platforms_and_official_sources(self):
        policies=adapter.capabilities();self.assertEqual(len(policies),6)
        self.assertTrue(all(x['source'].startswith('https://') for x in policies.values()))
    def test_handoff_keeps_original_content_and_state(self):
        t=self.task();p=self.profile(t);r=adapter.handoff(self.root,t['id'],p,'handoff.json')
        self.assertEqual(r['fingerprint'],t['fingerprint']);self.assertEqual(r['state'],'prepared')
        self.assertEqual((self.root/'body.md').read_text(),'Own verified content')
    def test_missing_setting_blocks_shared_executor(self):
        t=self.task();p=self.profile(t);p['platform_review']['confirmed']['rights']=False
        with self.assertRaises(ValueError):engine.validate(p,t)
    def test_review_for_other_task_is_rejected(self):
        t=self.task();p=self.profile(t);p['platform_review']['task_id']='other'
        with self.assertRaises(ValueError):adapter.handoff(self.root,t['id'],p,'handoff.json')
        self.assertFalse((self.root/'handoff.json').exists())
    def test_modified_evidence_is_rejected(self):
        t=self.task();p=self.profile(t);(self.root/'observed.txt').write_text('changed')
        with self.assertRaises(ValueError):adapter.handoff(self.root,t['id'],p,'handoff.json')
    def test_wrong_account_is_rejected(self):
        t=self.task();p=self.profile(t);p['account_id']='someone-else'
        with self.assertRaises(ValueError):adapter.handoff(self.root,t['id'],p,'handoff.json')
    def test_youtube_requires_real_video_and_title_step(self):
        t=self.task('youtube');p=self.profile(t,'video')
        with self.assertRaises(ValueError):engine.validate(p,t)
    def test_browser_media_requires_upload_step(self):
        (self.root/'image.png').write_bytes(b'fixture')
        t=self.task('x',['image.png']);p=self.profile(t,'image')
        with self.assertRaises(ValueError):engine.validate(p,t)
    def test_unsupported_format_rejected(self):
        t=self.task('douban');p=self.profile(t,'video')
        with self.assertRaises(ValueError):engine.validate(p,t)
    def test_observation_can_precede_settings_review(self):
        t=self.task();p=self.profile(t);p.pop('platform_review')
        engine.validate(p,t,platform_settings=False)
        with self.assertRaises(ValueError):engine.validate(p,t)

if __name__=='__main__':unittest.main()
