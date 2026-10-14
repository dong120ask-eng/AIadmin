"""Enroll real PC outputs and report the next publishing stage. No platform submission."""
import argparse,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(HERE/"selfmedia-autopilot/scripts"))
from common import read,save,inside,digest
spec=importlib.util.spec_from_file_location("ledger",HERE/"dsh-selfmedia-hub/scripts/ops.py")
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
def enrollment(root,plan,apply,output):
    ledger=module.Ledger(root); jobs=read(inside(root,plan,True))["jobs"]; candidates=[]
    try:
        for job in jobs:
            folder=inside(root,job["output_dir"]); body=inside(root,str((folder/"body.md").relative_to(Path(root).resolve())),True)
            content=read(folder/"content.json"); identity=ledger.instance(job["instance_id"])
            if identity["platform"]!=job["platform"]: raise ValueError("账号实例平台与任务不符")
            media=[str(f.relative_to(Path(root).resolve())) for f in sorted((folder/"cards").glob("*.png"))] if job["format"]=="image" else [
                str(f.relative_to(Path(root).resolve())) for f in sorted((folder/"video").glob("*.mp4"))] if job["format"]=="video" else []
            if job["format"] in ("image","video") and not media: raise ValueError("电脑素材尚未生成："+job["id"])
            candidates.append((job,body,content,media))
        if not apply: return {"mode":"plan","jobs":len(candidates),"note":"未建台账，未操作手机"}
        out=inside(root,output)
        if out.exists():
            mapping=read(out)
            if mapping.get('plan_sha256')!=digest(inside(root,plan,True)): raise ValueError('批次映射不属于当前精确计划')
            expected={job['id']:(job,body,content,media) for job,body,content,media in candidates}
            if set(expected)!={x['job'] for x in mapping['tasks']}: raise ValueError('批次映射任务不完整')
            for row in mapping['tasks']:
                t=ledger.load(row['task']); job,body,content,media=expected[row['job']]; ledger.check(t)
                if t['instance']['id']!=job['instance_id'] or t['title']!=content['title'] or t['visibility']!=job['visibility'] or t['text']!=ledger.file(body) or t['media']!=[ledger.file(f) for f in media]: raise ValueError('已入队任务和当前成果不一致')
                row['state']=t['state']
            return {'mode':'resumed','tasks':mapping['tasks']}
        mapped=[]
        for job,body,content,media in candidates:
            existing=next((t for t in ledger.listing() if t["instance"]["id"]==job["instance_id"] and
                t["title"]==content["title"] and t["visibility"]==job["visibility"] and
                t["text"]==ledger.file(body) and t["media"]==[ledger.file(f) for f in media]),None)
            task=existing or ledger.create(job["instance_id"],content["title"],str(body),media,job["visibility"])
            mapped.append({"job":job["id"],"task":task["id"],"platform":job["platform"],"state":task["state"]})
        save(out,{"tasks":mapped,'plan_sha256':digest(inside(root,plan,True)),"note":"QA/草稿/发布授权另行记录，电脑产物先留存"})
        return {"mode":"enrolled","tasks":mapped}
    finally: ledger.db.close()
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--root",required=True)
    s=p.add_subparsers(dest="action",required=True)
    q=s.add_parser("enroll"); q.add_argument("--plan",required=True); q.add_argument("--output",required=True); q.add_argument("--apply",action="store_true")
    q=s.add_parser("next"); q.add_argument("--task",required=True)
    a=p.parse_args()
    if a.action=="enroll": result=enrollment(a.root,a.plan,a.apply,a.output)
    else:
        ledger=module.Ledger(a.root)
        try:
            t=ledger.load(a.task); result={"task":t["id"],"state":t["state"],"platform":t["instance"]["platform"],
                "next":{"prepared":"完成事实与媒体QA","reviewed":"claim设备并按对应平台准备草稿",
                        "draft":"展示实际草稿，等待当前任务确认","approved":"claim、核对账号、begin",
                        "publishing":"先核验是否已提交；只有无attempt时才允许首次submit",
                        "uncertain":"核验已有作品，不重复提交","published":"回收实际数据并复盘"}[t["state"]]}
        finally: ledger.db.close()
    print(json.dumps(result,ensure_ascii=False,indent=2))
