"""One-command PC pipeline: mixed plan -> generation -> media -> queue, without silent publishing."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(script,*args):
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/script),*map(str,args)],check=True,timeout=3600)
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--root",required=True); p.add_argument("--campaign",required=True)
    p.add_argument("--profiles"); p.add_argument("--provider"); p.add_argument("--apply",action="store_true")
    p.add_argument("--enqueue",action="store_true"); a=p.parse_args(); workspace=Path(a.root).resolve()
    source=(workspace/a.campaign).resolve()
    if not source.is_relative_to(workspace): raise ValueError("计划来源须在工作区内")
    campaign=json.loads(source.read_text(encoding="utf-8-sig")); cid=campaign["id"]
    import re
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",cid): raise ValueError("批次ID无效")
    plan=workspace/"work"/(cid+"-plan.json")
    if not plan.exists(): run("skills/account-content-factory/scripts/matrix.py","--root",workspace,"--spec",a.campaign,"--output",plan)
    import hashlib
    if json.loads(plan.read_text(encoding='utf-8')).get('campaign_sha256')!=hashlib.sha256(source.read_bytes()).hexdigest(): raise ValueError('活动配置已修改或旧计划缺指纹；使用新的批次ID重新规划')
    if not a.apply:
        print(json.dumps({"plan":str(plan),"mode":"plan","next":"原生助手逐job生成，或明确选择API配置后apply"},ensure_ascii=False)); sys.exit()
    if not a.profiles or not a.provider: raise ValueError("API批量模式需profiles/provider；原生宿主按总控指令执行")
    run("skills/account-content-factory/scripts/generate.py","--root",workspace,"--plan",plan,"--profiles",a.profiles,"--provider",a.provider,"--apply")
    jobs=json.loads(plan.read_text(encoding="utf-8"))["jobs"]
    for job in jobs:
        folder=workspace/job["output_dir"]
        if job["format"] in ("image","video"):
            kind="cards" if job["format"]=="image" else "video"; out=folder/kind
            if out.exists() and not (out/'production-complete.json').is_file(): raise ValueError('素材目录未完成，请检查并另存后重试：'+str(out))
            if out.exists():
                recorded=json.loads((out/'production-complete.json').read_text(encoding='utf-8'))['files']
                if any(not (out/name).is_file() or hashlib.sha256((out/name).read_bytes()).hexdigest()!=fp for name,fp in recorded.items()): raise ValueError('已生成素材被修改，请重新检查：'+str(out))
            if not out.exists(): run("skills/desktop-media-production/scripts/media.py",kind,"--root",workspace,"--spec",folder/(kind+".json"),"--output",out)
    if a.enqueue: run("skills/platform-publish-router/scripts/queue.py","--root",workspace,"enroll","--plan",plan,"--output","state/"+cid+"-tasks.json","--apply")
    print(json.dumps({"campaign":cid,"stage":"pc-output-ready-pending-review",
        "next":"QA、真实账号草稿、当前用户确认后由selfmedia-autopilot调度控制器发布"},ensure_ascii=False))
