"""Commit native-assistant or API content into complete, fingerprinted PC job outputs."""
import argparse,json,shutil,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import read,save,inside,digest
def validate_content(value,job):
    if not isinstance(value,dict) or any(not isinstance(value.get(k),str) or not value[k].strip() for k in ('title','body')): raise ValueError('需非空标题正文字符串')
    for key in ('cards','segments','tags','sources'):
        if not isinstance(value.get(key,[]),list): raise ValueError('字段需数组：'+key)
    if job['format']=='image' and not value.get('cards'): raise ValueError('图文缺卡片')
    if job['format']=='video' and not value.get('segments'): raise ValueError('视频缺段落')
def commit(root,job,value):
    root=Path(root).resolve(); validate_content(value,job)
    if digest(inside(root,job['brief'],True))!=job['brief_sha256']: raise ValueError('产品资料改变，重新规划')
    out=inside(root,job['output_dir'])
    if out.exists():
        marker=read(out/'generation-complete.json')
        if read(out/'job.json')!=job or read(out/'content.json')!=value or any(digest(inside(out,name,True))!=fp for name,fp in marker['files'].items()): raise ValueError('已有成果不一致或不完整，不覆盖')
        return {'state':'existing-output-needs-review','output':str(out)}
    stage=inside(root,'work/generation-stage/'+uuid.uuid4().hex); stage.mkdir(parents=True)
    try:
        save(stage/'content.json',value); save(stage/'body.md',value['body']); save(stage/'job.json',job)
        if value.get('cards'): save(stage/'cards.json',{'theme':'swiss-blue','size':'3:4','brand':job['account_id'],'filename_prefix':'card','output_dir':str((out/'cards').relative_to(root)),'cards':value['cards']})
        if value.get('segments'): save(stage/'video.json',{'title':value['title'],'brand':job['account_id'],'theme':'swiss-blue','segments':value['segments'],'regulated_health':job['regulated_health']})
        save(stage/'generation-complete.json',{'files':{p.name:digest(p) for p in stage.iterdir() if p.is_file()}})
        out.parent.mkdir(parents=True,exist_ok=True); stage.rename(out)
        return {'state':'generated-pending-review','output':str(out)}
    finally:
        if stage.exists() and stage.is_relative_to(root): shutil.rmtree(stage)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','plan','job','content'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); jobs=read(inside(a.root,a.plan,True))['jobs']; matches=[j for j in jobs if j['id']==a.job]
    if len(matches)!=1: raise ValueError('计划内需唯一任务ID')
    print(json.dumps(commit(a.root,matches[0],read(inside(a.root,a.content,True))),ensure_ascii=False))
