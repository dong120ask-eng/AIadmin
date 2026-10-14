"""Build one deliverable, excluding credentials, runtime state, caches and machine evidence."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--output",required=True); a=p.parse_args()
    output=Path(a.output).resolve()
    if output.exists(): raise ValueError("交付文件已存在，不覆盖")
    files=[]
    for f in ROOT.rglob("*"):
        if f.is_symlink(): raise ValueError('包内不允许符号链接')
        if not f.is_file() or "__pycache__" in f.parts or f.suffix in (".pyc",".sqlite") or f.name.lower().startswith(".env"): continue
        if f.name=='bundle-manifest.json': continue
        if f.suffix=='.zip' and 'offline' not in f.relative_to(ROOT).parts: continue
        files.append(f)
    manifest=[{"path":str(f.relative_to(ROOT)).replace("\\","/"),"bytes":f.stat().st_size,
               "sha256":hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]
    output.parent.mkdir(parents=True,exist_ok=True)
    manifest_path=ROOT/'bundle-manifest.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile(output,"x",zipfile.ZIP_DEFLATED) as z:
        for f in files: z.write(f,"自媒体技能套件/"+str(f.relative_to(ROOT)).replace("\\","/"))
        z.write(manifest_path,'自媒体技能套件/bundle-manifest.json')
        z.writestr("文件指纹清单.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None: raise ValueError("ZIP损坏")
        for item in manifest:
            if hashlib.sha256(z.read("自媒体技能套件/"+item["path"])).hexdigest()!=item["sha256"]: raise ValueError("文件指纹不符")
    print(json.dumps({"file":str(output),"files":len(manifest)+2,"sha256":hashlib.sha256(output.read_bytes()).hexdigest(),
                      "integrity":"passed"},ensure_ascii=False))
