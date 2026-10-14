"""Preflight a mixed queue, quality-review tasks and prepare calibrated drafts, never submit."""
import argparse,importlib.util,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/selfmedia-autopilot/scripts'))
from runtime import ledger,read,save,inside,proof,instant
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
quality=load_module('batch_quality','skills/content-quality-gate/scripts/quality.py')
engine=load_module('batch_workflow','skills/publishing-workflow-runner/scripts/engine.py')
def preflight(root,spec):
    rows=[]; l=ledger(root); seen=set()
    try:
        for item in spec['tasks']:
            if item['task_id'] in seen: raise ValueError('重复任务')
            seen.add(item['task_id']); task=l.load(item['task_id']); l.check(task)
            if task['state'] not in ('prepared','reviewed','draft'): raise ValueError('批量草稿不处理发布中/未知/已批准/已发布任务')
            profile=read(inside(root,item['profile'],True)); engine.validate(profile,task)
            if profile.get('calibrated') is not True: raise ValueError('缺真实校准配置')
            if not profile.get('verified_by') or not profile.get('calibration_evidence'): raise ValueError('缺校准者和证据')
            instant(profile['verified_at'])
            for record in profile['calibration_evidence']: proof(Path(root).resolve(),record)
            if task['state']=='prepared':
                review=read(inside(root,item['review'],True)); report=quality.inspect(root,task['id'],review)
                if not report['passed']: raise ValueError('质检未通过：'+task['id'])
            else: report=None
            if task['state']=='reviewed' and l.file(task['qa']['path'])!=task['qa']: raise ValueError('质检证据已改变')
            rows.append({'task':task,'profile':profile,'qa':report})
        if not rows: raise ValueError('批次为空')
        return rows
    finally: l.db.close()
def prepare(root,spec,apply=False,backend_factory=None):
    rows=preflight(root,spec)
    if not apply: return {'mode':'plan','tasks':[{'id':r['task']['id'],'state':r['task']['state'],'platform':r['task']['instance']['platform']} for r in rows],'note':'未连接设备或页面，未发布'}
    journal=inside(root,'evidence/batch-prepare/'+uuid.uuid4().hex); journal.mkdir(parents=True); completed=[]
    for row in rows:
        task=row['task']; task_id=task['id']; l=ledger(root)
        try:
            if task['state']=='draft': completed.append({'task':task_id,'state':'existing-draft-needs-review'}); continue
            if row['qa']:
                qa=journal/(task_id+'-qa.json'); save(qa,row['qa']); l.change(task_id,'qa',evidence=str(qa))
            l.change(task_id,'claim')
        finally: l.db.close()
        b=None
        try:
            b=(backend_factory(row['profile']) if backend_factory else engine.Android(row['profile']) if row['profile']['backend']=='android' else engine.Browser(row['profile']))
            engine.execute(root,task_id,row['profile'],'prepare',b)
            l=ledger(root)
            try: l.change(task_id,'release')
            finally: l.db.close()
            record={'task':task_id,'state':'draft'}; completed.append(record); save(journal/(task_id+'-complete.json'),record)
        except BaseException:
            save(journal/(task_id+'-stopped.json'),{'task':task_id,'completed':completed,'note':'草稿准备停止；保留证据与设备锁，先核对当前页面和账号，不自动跳过或重放'})
            raise
        finally:
            if b is not None: b.close()
    return {'mode':'drafts-prepared','tasks':completed,'journal':str(journal),'note':'尚未批准或发布，最终提交另行确认'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True); p.add_argument('--spec',required=True); p.add_argument('--apply',action='store_true'); a=p.parse_args()
    print(json.dumps(prepare(a.root,read(inside(a.root,a.spec,True)),a.apply),ensure_ascii=False,indent=2))
