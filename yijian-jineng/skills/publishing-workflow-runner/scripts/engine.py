"""Execute calibrated draft steps or one approved submission against real UI evidence."""
import argparse,json,sys,uuid
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import ledger,read,save,inside,digest,instant,proof
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'platform-content-adapter/scripts'))
from adapter import validate_review
FINAL={'发布','发表','投稿','提交','发送','群发','确认发布','立即发布','publish','post','submit','send'}
def validate(profile,task=None,platform_settings=True):
    if profile.get('schema')!='publishing-profile/v1' or profile.get('backend') not in ('android','browser'): raise ValueError('发布配置版本或后端无效')
    for k in ('platform','account_id','device_id','location','identity_selector','visibility_value','visibility_selector','visibility_text'):
        if not profile.get(k): raise ValueError('发布配置缺 '+k)
    if profile['backend']=='browser':
        u=urlparse(profile.get('cdp',''))
        if u.scheme!='http' or u.hostname not in ('localhost','127.0.0.1','::1') or u.username or u.password: raise ValueError('仅本机已授权CDP')
        if urlparse(profile['location']).scheme!='https': raise ValueError('创作者页面须HTTPS')
    elif not profile.get('serial') or profile['serial']!=profile['device_id']: raise ValueError('Android须绑定精确序列号')
    if task:
        for key,actual in [('platform',task['instance']['platform']),('account_id',task['instance']['account_id']),('device_id',task['instance']['device_id'])]:
            if profile[key]!=actual: raise ValueError('任务与配置身份不一致：'+key)
        if profile['visibility_value']!=task['visibility']: raise ValueError('配置与任务可见性不一致')
        if profile['backend']=='android' and profile['location']!=task['instance']['package_name']: raise ValueError('App包名不符')
    for step in profile.get('draft_steps',[]):
        if step.get('action') not in ('fill','click','files') or not step.get('selector'): raise ValueError('草稿步骤仅支持fill/click/files及精确定位')
        if step['action']=='files' and profile['backend']!='browser': raise ValueError('Android素材选择需实际文件选择器的校准点击步骤')
        if step['action']=='fill' and step.get('value') not in ('title','body'): raise ValueError('文字只能读取当前任务的title/body')
        if step['action']=='click' and step.get('purpose') not in ('navigation','editor','save-draft'): raise ValueError('点击必须标明已校准的非发布用途')
    if task and platform_settings: validate_review(task,profile)
    return profile
class Android:
    def __init__(self,p):
        import uiautomator2 as u2
        self.device=u2.connect(p['serial']); self.profile=p
    def node(self,selector):
        if not isinstance(selector,dict) or not selector or any(k not in ('resourceId','text','description') or not isinstance(v,str) or not v for k,v in selector.items()): raise ValueError('Android定位需实际text/resourceId/description')
        return self.device(**selector)
    def identity(self):
        if self.device.app_current().get('package')!=self.profile['location']: raise ValueError('当前App不符')
        node=self.node(self.profile['identity_selector'])
        if node.count!=1: raise ValueError('账号锚点缺失或不唯一，需重新校准')
        return node.info.get('text','').strip()
    def count(self,s): return self.node(s).count
    def label(self,s):
        info=self.node(s).info; return (info.get('text') or info.get('contentDescription') or '').strip()
    def fill(self,s,value): self.node(s).set_text(value)
    def click(self,s): self.node(s).click()
    def snapshot(self,base):
        self.device.screenshot(str(base)+'.png'); save(str(base)+'.xml',self.device.dump_hierarchy())
    def close(self): pass
class Browser:
    def __init__(self,p):
        from playwright.sync_api import sync_playwright
        self.pw=sync_playwright().start(); self.profile=p
        try:
            self.browser=self.pw.chromium.connect_over_cdp(p['cdp']); pages=[page for c in self.browser.contexts for page in c.pages if page.url==p['location']]
            if len(pages)!=1: raise ValueError('必须唯一匹配指定标签页')
            self.page=pages[0]
        except BaseException: self.pw.stop(); raise
    def node(self,s):
        if not isinstance(s,str) or not s.strip(): raise ValueError('浏览器需实际精确CSS定位')
        return self.page.locator(s)
    def identity(self):
        if self.page.url!=self.profile['location']: raise ValueError('页面已切换')
        n=self.node(self.profile['identity_selector'])
        if n.count()!=1: raise ValueError('账号锚点不唯一')
        return n.inner_text().strip()
    def count(self,s): return self.node(s).count()
    def label(self,s): return self.node(s).inner_text().strip()
    def fill(self,s,v): self.node(s).fill(v)
    def files(self,s,paths): self.node(s).set_input_files(paths)
    def click(self,s): self.node(s).click()
    def snapshot(self,base): self.page.screenshot(path=str(base)+'.png',full_page=True); save(str(base)+'.html',self.page.content())
    def close(self): self.pw.stop()
def capture(backend,profile,root,folder,label):
    root=Path(root).resolve(); folder=Path(folder).resolve()
    if not folder.is_relative_to(root): raise ValueError('观察目录必须位于工作区内')
    account=backend.identity()
    if account!=profile['account_id']: raise ValueError('实际页面账号不符')
    base=inside(root,str(folder.relative_to(root))+'/'+label)
    base.parent.mkdir(parents=True,exist_ok=True); backend.snapshot(base)
    record={'schema':'ui-observation/v1','account_id':account,'location':profile['location'],'backend':profile['backend'],'files':[]}
    for f in base.parent.glob(base.name+'.*'):
        if f.is_file(): record['files'].append({'path':str(f.relative_to(Path(root).resolve())),'sha256':digest(f)})
    if not record['files']: raise ValueError('后端没有产出观察证据')
    out=Path(str(base)+'.json'); save(out,record); return out
def execute(root,task_id,profile,mode,backend):
    l=ledger(root); folder=inside(root,'evidence/workflows/'+task_id+'/'+uuid.uuid4().hex); folder.mkdir(parents=True)
    try:
        task=l.load(task_id); validate(profile,task); l.check(task); l.owns(task)
        for item in profile.get('platform_review',{}).get('evidence',[]): proof(l.root,item)
        if profile.get('calibrated') is not True or not profile.get('verified_by'): raise ValueError('配置尚未校准')
        instant(profile['verified_at'])
        for item in profile.get('calibration_evidence',[]): proof(l.root,item)
        if not profile.get('calibration_evidence'): raise ValueError('缺校准证据')
        before=capture(backend,profile,l.root,folder,'before')
        if mode=='prepare':
            if task['state']!='reviewed' or not profile.get('draft_steps'): raise ValueError('准备草稿需reviewed及非空校准步骤')
            if l.file(task['qa']['path'])!=task['qa']: raise ValueError('质检证据已改变')
            for i,step in enumerate(profile['draft_steps']):
                l.check(l.load(task_id))
                if backend.identity()!=profile['account_id'] or backend.count(step['selector'])!=1: raise ValueError('身份或控件唯一性改变')
                if backend.label(step['selector']).strip().lower() in FINAL: raise ValueError('草稿流程命中发布控件，停止')
                if step['action']=='fill': backend.fill(step['selector'],task['title'] if step['value']=='title' else l.path(task['text']['path']).read_text(encoding='utf-8-sig'))
                elif step['action']=='files': backend.files(step['selector'],[str(l.path(r['path'])) for r in task['media']])
                else: backend.click(step['selector'])
                capture(backend,profile,l.root,folder,'after-'+str(i))
            report=folder/'draft.json'; save(report,{'task_id':task_id,'fingerprint':task['fingerprint'],'profile':profile,'before':str(before.relative_to(l.root)),'steps':len(profile['draft_steps']),'account_id':profile['account_id']})
            if backend.count(profile['visibility_selector'])!=1 or backend.label(profile['visibility_selector']).strip()!=profile['visibility_text']: raise ValueError('真实草稿可见性未核验')
            return l.change(task_id,'draft',observed=profile['account_id'],evidence=str(report))
        if mode!='submit' or task['state']!='publishing' or not profile.get('submit_selector'): raise ValueError('提交需本任务approval、begin及校准控件')
        selector=profile['submit_selector']
        if backend.count(profile['visibility_selector'])!=1 or backend.label(profile['visibility_selector']).strip()!=profile['visibility_text']: raise ValueError('提交前可见性不符')
        if backend.count(selector)!=1 or backend.identity()!=profile['account_id']: raise ValueError('提交节点或账号不唯一')
        l.change(task_id,'attempt',observed=profile['account_id'])
        try:
            backend.click(selector); capture(backend,profile,l.root,folder,'after-submit')
        except BaseException:
            failure=folder/'submission-unknown.json'; save(failure,{'task_id':task_id,'status':'submission-result-unknown','note':'提交已经登记；先核验作品，禁止自动重复提交'})
            l.change(task_id,'uncertain',evidence=str(failure)); raise
        return {'task_id':task_id,'status':'submitted-awaiting-result-verification','evidence':str(folder.relative_to(l.root))}
    finally: l.db.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('mode',choices=('observe','prepare','submit'))
    for k in ('root','task','profile'): p.add_argument('--'+k,required=True)
    p.add_argument('--apply',action='store_true'); a=p.parse_args(); profile=read(inside(a.root,a.profile,True)); l=ledger(a.root)
    try: task=l.load(a.task); validate(profile,task,platform_settings=a.mode!='observe')
    finally: l.db.close()
    if not a.apply:
        print(json.dumps({'mode':'plan','operation':a.mode,'platform':profile['platform'],'task':a.task,'steps':profile.get('draft_steps',[]),'note':'未连接设备或浏览器'},ensure_ascii=False)); sys.exit()
    if a.mode!='observe':
        if profile.get('calibrated') is not True or not profile.get('calibration_evidence'): raise ValueError('配置未校准；尚未连接设备')
        if task['state']!=('reviewed' if a.mode=='prepare' else 'publishing'): raise ValueError('任务阶段不允许该操作；尚未连接设备')
        for record in profile['calibration_evidence']: proof(Path(a.root).resolve(),record)
        for record in profile.get('platform_review',{}).get('evidence',[]): proof(Path(a.root).resolve(),record)
        l=ledger(a.root)
        try: l.check(task); l.owns(task)
        finally: l.db.close()
    b=Android(profile) if profile['backend']=='android' else Browser(profile)
    try:
        if a.mode=='observe': result={'observation':str(capture(b,profile,Path(a.root).resolve(),inside(a.root,'evidence/calibration/'+uuid.uuid4().hex),'observation'))}
        else: result=execute(a.root,a.task,profile,a.mode,b)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally: b.close()
