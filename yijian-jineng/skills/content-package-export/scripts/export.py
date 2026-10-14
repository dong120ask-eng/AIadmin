"""Export only one reviewed task's media and an immutable handoff manifest."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import ledger,inside
def export(root,task_id,output):
    l=ledger(root)
    try:
        task=l.load(task_id); l.check(task)
        if task['state']=='prepared': raise ValueError('任务尚未质检，不能作为发布交接包')
        out=inside(root,output)
        if out.exists(): raise ValueError('交接文件已存在，不覆盖')
        files=[('body.md',l.path(task['text']['path']))]
        files += [('media/'+str(i).zfill(3)+'-'+l.path(r['path']).name,l.path(r['path'])) for i,r in enumerate(task['media'])]
        manifest={'schema':'content-handoff/v1','task_id':task_id,'fingerprint':task['fingerprint'],'title':task['title'],'platform':task['instance']['platform'],'account_id':task['instance']['account_id'],'visibility':task['visibility'],'files':[{'path':name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for name,f in files],'note':'仅交接成果，不复制登录状态、审批或设备锁；新工作区重新登记、质检和核验账号'}
        out.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED) as z:
            for name,f in files: z.write(f,name)
            z.writestr('handoff.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        with zipfile.ZipFile(out) as z:
            if z.testzip(): raise ValueError('交接ZIP损坏')
            for f in manifest['files']:
                if hashlib.sha256(z.read(f['path'])).hexdigest()!=f['sha256']: raise ValueError('交接ZIP指纹不符')
        return {'file':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':len(files)}
    finally: l.db.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','task','output'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); print(json.dumps(export(a.root,a.task,a.output),ensure_ascii=False))
