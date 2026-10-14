"""Archive named top-level files with a recoverable manifest; never delete."""
import argparse,hashlib,json,shutil
from pathlib import Path
def plan(root,names,archive):
    root=Path(root).resolve(); target=(root/archive).resolve()
    if not target.is_relative_to(root) or target==root: raise ValueError("目标须在工作区内")
    protected={".agents",".codebuddy",".dsh",".venv-harness","自媒体技能套件","delivery","state","outputs","evidence","work"}
    items=[]
    for name in names:
        if name in protected or Path(name).name!=name: raise ValueError("不可移动运行目录或非顶层路径："+name)
        source=(root/name).resolve(); dest=target/name
        if not source.is_relative_to(root) or not source.exists() or dest.exists() or target.is_relative_to(source): raise ValueError("来源/目标冲突："+name)
        items.append((source,dest))
    return items
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",required=True); p.add_argument("--archive",required=True); p.add_argument("--names",nargs="+",required=True); p.add_argument("--apply",action="store_true")
    a=p.parse_args(); items=plan(a.root,a.names,a.archive); manifest=[]
    for source,dest in items:
        files=[source] if source.is_file() else [f for f in source.rglob("*") if f.is_file()]
        manifest.append({"source":str(source),"target":str(dest),"files":[{"relative":f.name if source.is_file() else str(f.relative_to(source)),"sha256":hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]})
    if a.apply:
        target=(Path(a.root)/a.archive).resolve(); target.mkdir(parents=True,exist_ok=True); log=target/"移动清单.json"
        if log.exists(): raise ValueError("清单已存在")
        log.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        for source,dest in items: shutil.move(str(source),str(dest))
    print(json.dumps({"mode":"applied" if a.apply else "plan","items":manifest},ensure_ascii=False,indent=2))
