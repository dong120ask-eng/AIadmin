import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PipelineGuards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
        (self.root/'config').mkdir()
        self.campaign=json.loads((ROOT/'config/campaign.example.json').read_text(encoding='utf-8'))
        self.write('config/campaign.json',self.campaign)
        (self.root/'config/product-demo.md').write_text('product facts',encoding='utf-8')
        self.write('config/profiles.json',{'providers':{'fake':{'base_url':'http://127.0.0.1:1','model':None,'api_key_env':'UNSET_TEST_KEY'}}})
    def write(self,name,value):
        p=self.root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(value),encoding='utf-8')
    def run_script(self,path,*args):
        return subprocess.run([sys.executable,'-X','utf8',str(ROOT/path),'--root',str(self.root),*args],env=dict(os.environ,PYTHONUTF8='1'),capture_output=True,text=True,encoding='utf-8',timeout=30)
    def plan(self):
        r=self.run_script('tools/one_click.py','--campaign','config/campaign.json'); self.assertEqual(r.returncode,0,r.stderr)
        return self.root/'work'/(self.campaign['id']+'-plan.json')
    def test_changed_config_blocks_old_plan(self):
        self.plan(); self.campaign['topics'][0]['angle']='changed'; self.write('config/campaign.json',self.campaign)
        r=self.run_script('tools/one_click.py','--campaign','config/campaign.json'); self.assertNotEqual(r.returncode,0)
    def test_duplicate_topic_rejected(self):
        self.campaign['topics'].append(self.campaign['topics'][0]); self.write('config/campaign.json',self.campaign)
        r=self.run_script('tools/one_click.py','--campaign','config/campaign.json'); self.assertNotEqual(r.returncode,0)
    def test_partial_generation_stops_before_api(self):
        plan=self.plan(); job=json.loads(plan.read_text(encoding='utf-8'))['jobs'][0]
        (self.root/job['output_dir']).mkdir(parents=True)
        r=self.run_script('skills/account-content-factory/scripts/generate.py','--plan',str(plan),'--profiles','config/profiles.json','--provider','fake','--apply')
        self.assertNotEqual(r.returncode,0); self.assertIn('未完成生成目录',r.stderr)
if __name__=='__main__': unittest.main()
