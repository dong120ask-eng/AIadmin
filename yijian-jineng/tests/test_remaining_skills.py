import hashlib,importlib.util,io,json,os,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
ops=load('extended_ops','skills/dsh-selfmedia-hub/scripts/ops.py')
quality=load('extended_quality','skills/content-quality-gate/scripts/quality.py')
engine=load('extended_engine','skills/publishing-workflow-runner/scripts/engine.py')
recovery=load('extended_recovery','skills/publishing-recovery/scripts/recovery.py')
calendar=load('extended_calendar','skills/account-content-calendar/scripts/calendar.py')
assets=load('extended_assets','skills/asset-library/scripts/assets.py')
sources=load('extended_sources','skills/content-source-library/scripts/sources.py')
analytics=load('extended_analytics','skills/selfmedia-analytics/scripts/analytics.py')
experiment=load('extended_experiment','skills/content-experiment-lab/scripts/experiment.py')
client=load('extended_client','skills/model-provider-runtime/scripts/client.py')
exports=load('extended_export','skills/content-package-export/scripts/export.py')
calibration=load('extended_calibration','skills/publishing-calibration/scripts/calibrate.py')
batch=load('extended_batch','tools/batch_prepare.py')
router=load('extended_router','skills/platform-publish-router/scripts/queue.py')
video=load('extended_video','skills/video-format-adaptation/scripts/adapt.py')
formatting=load('extended_formatting','skills/dsh-content-studio/scripts/formatting.py')
accept=load('extended_accept','skills/account-content-factory/scripts/accept.py')
class Base(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
    def write(self,name,value):
        p=self.root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(value,ensure_ascii=False) if not isinstance(value,str) else value,encoding='utf-8'); return p
    def proof(self,name):
        p=self.root/name; return {'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    def task(self,reviewed=False):
        self.write('body.md','自己的产品事实与内容'); l=ops.Ledger(self.root)
        l.register({'id':'instance-one','device_id':'browser-one','platform':'xiaohongshu','package_name':'browser.creator','account_id':'account-one','account_alias':'自己的账号','launch_mode':'primary'})
        t=l.create('instance-one','产品标题','body.md',[],'private')
        if reviewed:
            self.write('qa.json',{'schema':'content-qa/v1','task_id':t['id'],'fingerprint':t['fingerprint'],'passed':True,'issues':[],'reviewer':'human-reviewer'})
            l.change(t['id'],'qa',evidence='qa.json'); l.change(t['id'],'claim'); t=l.load(t['id'])
        l.db.close(); return t
class QualityTests(Base):
    def review(self,t):
        self.write('facts.md','用户提供的真实资料')
        return {'task_id':t['id'],'fingerprint':t['fingerprint'],'facts_reviewed':True,'rights_reviewed':True,'reviewer':'human','platform_rules':{'platform':'xiaohongshu','title_max_chars':20,'body_max_chars':1000,'blocked_phrases':[]},'evidence':[self.proof('facts.md')]}
    def test_passed_qa_binds_actual_task(self):
        t=self.task(); r=quality.inspect(self.root,t['id'],self.review(t)); self.assertTrue(r['passed']); self.assertEqual(r['fingerprint'],t['fingerprint'])
    def test_unreviewed_facts_do_not_pass(self):
        t=self.task(); review=self.review(t); review['facts_reviewed']=False; self.assertFalse(quality.inspect(self.root,t['id'],review)['passed'])
    def test_changed_fact_evidence_rejected(self):
        t=self.task(); review=self.review(t); self.write('facts.md','changed')
        with self.assertRaises(ValueError): quality.inspect(self.root,t['id'],review)
    def test_plain_qa_evidence_no_longer_bypasses_gate(self):
        t=self.task(); self.write('qa.json',{'passed':True}); l=ops.Ledger(self.root)
        try:
            with self.assertRaises(ValueError): l.change(t['id'],'qa',evidence='qa.json')
            self.assertEqual(l.load(t['id'])['state'],'prepared')
        finally: l.db.close()
    def test_unsafe_health_content_stays_pending(self):
        t=self.task(); review=self.review(t); review['regulated_health']=True; self.assertFalse(quality.inspect(self.root,t['id'],review)['passed'])
    def test_actual_image_is_decoded_and_measured(self):
        original=self.task(); from PIL import Image
        Image.new('RGB',(64,64),'white').save(self.root/'image.png'); l=ops.Ledger(self.root)
        try: t=l.create('instance-one','产品标题','body.md',['image.png'],'private')
        finally: l.db.close()
        report=quality.inspect(self.root,t['id'],self.review(t)); self.assertTrue(report['passed']); self.assertEqual(report['media'][0]['size'],[64,64])
class FakeBackend:
    def __init__(self,account='account-one',fail_submit=False): self.account=account; self.operations=[]; self.fail_submit=fail_submit; self.labels={'visibility':'仅自己可见','publish':'发布'}
    def identity(self): return self.account
    def count(self,s): return 1
    def label(self,s): return self.labels.get(s,'')
    def fill(self,s,value): self.operations.append(('fill',s,value))
    def files(self,s,value): self.operations.append(('files',s,value))
    def click(self,s):
        self.operations.append(('click',s))
        if s=='publish' and self.fail_submit: raise OSError('connection dropped')
    def snapshot(self,base): Path(str(base)+'.html').write_text('<div>current UI</div>',encoding='utf-8')
    def close(self): pass
class WorkflowTests(Base):
    def profile(self):
        self.write('calibration.html','real observed test fixture')
        return {'schema':'publishing-profile/v1','backend':'browser','platform':'xiaohongshu','account_id':'account-one','device_id':'browser-one','location':'https://creator.xiaohongshu.com/editor','cdp':'http://127.0.0.1:9222','identity_selector':'#account','visibility_value':'private','visibility_selector':'visibility','visibility_text':'仅自己可见','calibrated':True,'verified_by':'reviewer','verified_at':'2026-10-14T12:00:00+08:00','calibration_evidence':[self.proof('calibration.html')],'draft_steps':[{'action':'fill','selector':'title','value':'title'},{'action':'fill','selector':'body','value':'body'}],'submit_selector':'publish'}
    def stage(self,t,p,b):
        engine.execute(self.root,t['id'],p,'prepare',b); l=ops.Ledger(self.root); task=l.load(t['id'])
        self.write('approval.json',{'task_id':t['id'],'fingerprint':task['fingerprint'],'draft_sha256':task['draft']['sha256'],'consent':True,'approved_by':'actual-user'})
        l.change(t['id'],'approve',approval='approval.json'); self.write('pre.json',{'account':'account-one'}); l.change(t['id'],'begin',observed='account-one',evidence='pre.json'); l.db.close()
    def test_draft_uses_actual_task_text(self):
        t=self.task(True); b=FakeBackend(); r=engine.execute(self.root,t['id'],self.profile(),'prepare',b)
        self.assertEqual(r['state'],'draft'); self.assertEqual(b.operations[1][2],(self.root/'body.md').read_text(encoding='utf-8'))
    def test_wrong_account_never_changes_ui(self):
        t=self.task(True); b=FakeBackend('wrong')
        with self.assertRaises(ValueError): engine.execute(self.root,t['id'],self.profile(),'prepare',b)
        self.assertEqual(b.operations,[])
    def test_publish_button_not_allowed_in_draft(self):
        t=self.task(True); p=self.profile(); p['draft_steps']=[{'action':'click','selector':'publish','purpose':'editor'}]; b=FakeBackend()
        with self.assertRaises(ValueError): engine.execute(self.root,t['id'],p,'prepare',b)
        self.assertEqual(b.operations,[])
    def test_uncalibrated_profile_cannot_execute(self):
        t=self.task(True); p=self.profile(); p['calibrated']=False; b=FakeBackend()
        with self.assertRaises(ValueError): engine.execute(self.root,t['id'],p,'prepare',b)
        self.assertEqual(b.operations,[])
    def test_submission_requires_existing_approval(self):
        t=self.task(True); b=FakeBackend()
        with self.assertRaises(ValueError): engine.execute(self.root,t['id'],self.profile(),'submit',b)
        self.assertEqual(b.operations,[])
    def test_submit_failure_keeps_unknown_and_blocks_second_click(self):
        t=self.task(True); p=self.profile(); b=FakeBackend(fail_submit=True); self.stage(t,p,b)
        with self.assertRaises(OSError): engine.execute(self.root,t['id'],p,'submit',b)
        l=ops.Ledger(self.root)
        try: self.assertEqual(l.load(t['id'])['state'],'uncertain')
        finally: l.db.close()
        with self.assertRaises(ValueError): engine.execute(self.root,t['id'],p,'submit',b)
        self.assertEqual(sum(x==('click','publish') for x in b.operations),1)
    def test_visibility_mismatch_blocks_submission(self):
        t=self.task(True); p=self.profile(); b=FakeBackend(); self.stage(t,p,b); b.labels['visibility']='公开'
        with self.assertRaises(ValueError): engine.execute(self.root,t['id'],p,'submit',b)
        self.assertNotIn(('click','publish'),b.operations)
    def test_calibration_binds_observed_identity(self):
        t=self.task(True); p=self.profile(); obs=engine.capture(FakeBackend(),p,self.root,self.root/'evidence/sample','observe'); r=calibration.calibrate(self.root,t['id'],p,str(obs.relative_to(self.root.resolve())),'reviewer'); self.assertTrue(r['calibrated'])
        self.write(str(obs.relative_to(self.root.resolve())),{'schema':'ui-observation/v1','account_id':'wrong'})
        with self.assertRaises(ValueError): calibration.calibrate(self.root,t['id'],p,str(obs.relative_to(self.root.resolve())),'reviewer')
    def test_recovery_requires_exact_verified_work(self):
        t=self.task(True); p=self.profile(); b=FakeBackend(); self.stage(t,p,b); engine.execute(self.root,t['id'],p,'submit',b)
        self.write('result.md','实际作品与账号截图测试证据')
        record={'task_id':t['id'],'fingerprint':t['fingerprint'],'account_id':'account-one','verified':True,'reviewer':'human','outcome':'published','result_id':'real-work-id','title':t['title'],'evidence':self.proof('result.md')}
        r=recovery.recover(self.root,t['id'],record); self.assertEqual(r['state'],'published')
    def test_batch_plan_does_not_connect_backend(self):
        t=self.task(True); self.write('profile.json',self.profile()); called=[]
        r=batch.prepare(self.root,{'tasks':[{'task_id':t['id'],'profile':'profile.json'}]},False,lambda p:called.append(1))
        self.assertEqual(r['mode'],'plan'); self.assertEqual(called,[])
    def test_batch_prepares_draft_and_releases_device(self):
        t=self.task(True); self.write('profile.json',self.profile()); r=batch.prepare(self.root,{'tasks':[{'task_id':t['id'],'profile':'profile.json'}]},True,lambda p:FakeBackend()); self.assertEqual(r['tasks'][0]['state'],'draft')
        l=ops.Ledger(self.root)
        try: self.assertIsNone(l.db.execute('SELECT task FROM locks').fetchone())
        finally: l.db.close()
    def test_export_reviewed_task_without_approval_or_credentials(self):
        t=self.task(True); r=exports.export(self.root,t['id'],'handoff.zip')
        import zipfile
        with zipfile.ZipFile(r['file']) as z: self.assertEqual(set(z.namelist()),{'body.md','handoff.json'}); self.assertNotIn('approval',z.read('handoff.json').decode())
class LibraryTests(Base):
    def test_native_content_commit_is_atomic_and_repeatable(self):
        self.write('brief.md','facts'); job={'id':'one','brief':'brief.md','brief_sha256':self.proof('brief.md')['sha256'],'output_dir':'outputs/job','account_id':'one','format':'article','regulated_health':False}; value={'title':'标题','body':'独立正文'}
        a=accept.commit(self.root,job,value); b=accept.commit(self.root,job,value); self.assertEqual(a['output'],b['output']); self.assertEqual(b['state'],'existing-output-needs-review')
        with self.assertRaises(ValueError): accept.commit(self.root,job,{'title':'changed','body':'changed'})
    def test_native_bad_video_never_creates_output(self):
        self.write('brief.md','facts'); job={'id':'one','brief':'brief.md','brief_sha256':self.proof('brief.md')['sha256'],'output_dir':'outputs/job','account_id':'one','format':'video','regulated_health':False}
        with self.assertRaises(ValueError): accept.commit(self.root,job,{'title':'title','body':'body'})
        self.assertFalse((self.root/'outputs/job').exists())
    def test_article_formatting_escapes_html_and_rejects_active_links(self):
        text=formatting.render('标题','## 小标题\n<script>alert(1)</script>\n\n[危险](javascript:alert)')
        self.assertNotIn('<script>',text); self.assertNotIn('href="javascript:',text); self.assertIn('<h3',text)
    def test_html_import_removes_scripts_and_deduplicates(self):
        self.write('source.html','<p>正文事实</p><script>bad()</script>'); self.write('metadata.json',{'source_url':'https://example.com/article','access':'public','collected_at':'2026-10-14T10:00:00+08:00'})
        a=sources.ingest(self.root,'source.html','metadata.json'); b=sources.ingest(self.root,'source.html','metadata.json'); self.assertEqual(a['id'],b['id']); self.assertNotIn('bad()',(self.root/a['path']/'body.md').read_text(encoding='utf-8'))
    def test_multiline_source_dedup_matches_saved_fingerprint(self):
        self.write('source.html','<p>第一段</p><p>第二段</p>'); self.write('metadata.json',{'source_url':'https://example.com/article','access':'public','collected_at':'2026-10-14T10:00:00+08:00'})
        a=sources.ingest(self.root,'source.html','metadata.json'); b=sources.ingest(self.root,'source.html','metadata.json'); self.assertEqual(a['id'],b['id']); self.assertEqual(self.proof(a['path']+'/body.md')['sha256'],a['id'])
    def test_rss_rejects_entities(self):
        self.write('source.xml','<!DOCTYPE x [<!ENTITY e SYSTEM "file:///secret">]><rss/>'); self.write('metadata.json',{'source_url':'https://example.com/rss','access':'public','collected_at':'2026-10-14T10:00:00+08:00'})
        with self.assertRaises(ValueError): sources.ingest(self.root,'source.xml','metadata.json')
    def test_asset_cross_account_use_requires_explicit_reuse(self):
        self.write('media.txt','media fixture'); a=assets.Assets(self.root)
        try:
            r=a.ingest('media.txt',{'rights':'owned','source':'my camera'}); a.use(r['sha'],'one','task-one')
            with self.assertRaises(ValueError): a.use(r['sha'],'two','task-two')
            a.use(r['sha'],'two','task-two',True)
        finally: a.db.close()
    def test_export_only_reviewed_task(self):
        t=self.task()
        with self.assertRaises(ValueError): exports.export(self.root,t['id'],'out.zip')
    def test_queue_resume_does_not_duplicate_tasks(self):
        self.task(); self.write('outputs/job/body.md','real output'); self.write('outputs/job/content.json',{'title':'new title','body':'real output'})
        self.write('plan.json',{'jobs':[{'id':'job-one','output_dir':'outputs/job','instance_id':'instance-one','platform':'xiaohongshu','format':'article','visibility':'private'}]})
        a=router.enrollment(self.root,'plan.json',True,'state/map.json'); b=router.enrollment(self.root,'plan.json',True,'state/map.json')
        self.assertEqual(a['tasks'][0]['task'],b['tasks'][0]['task']); self.assertEqual(b['mode'],'resumed')
        self.write('plan.json',{'jobs':[{'id':'job-two','output_dir':'outputs/job','instance_id':'instance-one','platform':'xiaohongshu','format':'article','visibility':'private'}]})
        with self.assertRaises(ValueError): router.enrollment(self.root,'plan.json',True,'state/map.json')
class MetricsTests(Base):
    def row(self): return {'platform':'xiaohongshu','account_id':'one','content_id':'p1','window':'24h','published_at':'2026-10-13T12:00:00+08:00','collected_at':'2026-10-14T12:00:00+08:00','views':100,'likes':10,'comments':2,'saves':3,'shares':1}
    def test_rates_and_zero_denominator(self):
        r=self.row(); self.assertEqual(analytics.aggregate([r])[0]['engagement_per_view'],.16); r['views']=0; self.assertIsNone(analytics.aggregate([r])[0]['engagement_per_view'])
    def test_duplicate_windows_do_not_double_count(self):
        with self.assertRaises(ValueError): analytics.aggregate([self.row(),self.row()])
    def test_nan_metric_is_rejected(self):
        r=self.row(); r['views']=float('nan')
        with self.assertRaises(ValueError): analytics.aggregate([r])
    def test_small_experiment_does_not_declare_winner(self):
        r=experiment.compare([{'variant':'a','events':1,'trials':2},{'variant':'b','events':0,'trials':2}],100); self.assertEqual(r['result'],'inconclusive')
    def test_experiment_rejects_events_greater_than_trials(self):
        with self.assertRaises(ValueError): experiment.wilson(11,10)
    def test_device_serialization_and_daily_cap(self):
        jobs=[{'id':str(i),'account_id':'one','device_id':'phone'} for i in range(3)]; r=calendar.schedule(jobs,{'start':'2026-10-14T08:00:00+08:00','account_gap_minutes':60,'device_slot_minutes':5,'account_daily_cap':2}); self.assertEqual(r[2]['scheduled_at'][:10],'2026-10-15'); self.assertGreater(r[1]['scheduled_at'],r[0]['device_slot_until'])
    def test_naive_schedule_time_rejected(self):
        with self.assertRaises(ValueError): calendar.schedule([],{'start':'2026-10-14T08:00:00','account_gap_minutes':60,'device_slot_minutes':5,'account_daily_cap':2})
    def test_video_command_preserves_source_and_uses_padding(self):
        args=video.command('source.mp4','new.mp4',1920,1080,30,0,5,'ffmpeg')
        self.assertIn('-n',args); self.assertIn('pad=1920:1080',args[args.index('-vf')+1]); self.assertEqual(args[-1],'new.mp4')
    def test_video_command_rejects_bad_dimensions_and_time(self):
        with self.assertRaises(ValueError): video.command('a','b',1919,1080,30,0,5,'ffmpeg')
        with self.assertRaises(ValueError): video.command('a','b',1920,1080,30,float('nan'),5,'ffmpeg')
class ModelTests(Base):
    def profile(self): return {'base_url':'https://example.com/v1','api_key_env':'TEST_FAKE_MODEL_KEY','model':'fixture-model','daily_call_limit':10,'daily_token_budget':20000,'max_output_tokens':100,'retry_429':1}
    def response(self): return io.BytesIO(json.dumps({'choices':[{'message':{'content':'fixture reply'}}]}).encode())
    def test_budget_prevents_extra_network_call(self):
        calls=[]; p=self.profile(); p['daily_call_limit']=1
        def opener(*a,**k): calls.append(1); return self.response()
        with patch.dict(os.environ,{'TEST_FAKE_MODEL_KEY':'not-a-real-key'}):
            c=client.Client(self.root,p,opener=opener); c.chat([{'role':'user','content':'facts'}])
            with self.assertRaises(ValueError): c.chat([{'role':'user','content':'facts'}])
        self.assertEqual(len(calls),1)
    def test_only_known_rate_limit_is_retried(self):
        calls=[]
        def opener(*a,**k):
            calls.append(1)
            if len(calls)==1: raise urllib.error.HTTPError('https://example.com',429,'limited',{},None)
            return self.response()
        with patch.dict(os.environ,{'TEST_FAKE_MODEL_KEY':'not-a-real-key'}): result=client.Client(self.root,self.profile(),opener=opener,sleeper=lambda s:None).chat([{'role':'user','content':'facts'}])
        self.assertEqual(result['attempts'],2)
    def test_unknown_connection_does_not_retry(self):
        calls=[]
        def opener(*a,**k): calls.append(1); raise urllib.error.URLError('failure')
        with patch.dict(os.environ,{'TEST_FAKE_MODEL_KEY':'not-a-real-key'}):
            with self.assertRaises(RuntimeError): client.Client(self.root,self.profile(),opener=opener).chat([{'role':'user','content':'facts'}])
        self.assertEqual(len(calls),1)
if __name__=='__main__': unittest.main()
