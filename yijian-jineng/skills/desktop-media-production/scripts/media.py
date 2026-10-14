"""Produce cards/video with bundled renderers; all final outputs stay on the PC first."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("kind",choices=("cards","video","verify-video"))
    p.add_argument("--root",required=True); p.add_argument("--spec"); p.add_argument("--output",required=True)
    p.add_argument("--python",default=sys.executable); p.add_argument("--ffmpeg",default=shutil.which("ffmpeg")); p.add_argument("--ffprobe",default=shutil.which("ffprobe"))
    a=p.parse_args(); root=Path(a.root).resolve(); out=(root/a.output).resolve(); scripts=Path(__file__).resolve().parent
    if not out.is_relative_to(root): raise ValueError("输出需在工作区内")
    env=dict(os.environ,OPS_PY=a.python,PYTHONUTF8="1")
    if a.ffmpeg: env["OPS_FFMPEG"]=a.ffmpeg
    if a.ffprobe: env["OPS_FFPROBE"]=a.ffprobe
    if a.kind=="verify-video": args=[a.python,str(scripts/"verify_output.py"),"--dir",str(out)]
    else:
        spec=(root/(a.spec or "")).resolve()
        if not spec.is_relative_to(root) or not spec.is_file() or out.exists(): raise ValueError("需工作区内规格和新输出目录")
        if a.kind=="cards":
            data=json.loads(spec.read_text(encoding="utf-8-sig")); data["output_dir"]=str(out)
            prefix=data.get("filename_prefix","card")
            if not isinstance(prefix,str) or any(c in prefix for c in "/\\:") or prefix in (".",".."): raise ValueError("图片文件名前缀无效")
            if not isinstance(data.get("cards"),list) or not data["cards"]: raise ValueError("缺少非空cards")
            temp=root/"work"/("cards-"+os.urandom(8).hex()+".json"); temp.parent.mkdir(parents=True,exist_ok=True)
            temp.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
            args=[a.python,str(scripts/"render_cards.py"),"--spec",str(temp)]
        else: args=[a.python,str(scripts/"make_video.py"),"--spec",str(spec),"--outdir",str(out)]
    try:
        r=subprocess.run(args,cwd=root,env=env,timeout=1800)
    finally:
        if a.kind=='cards': temp.unlink(missing_ok=True)
    if r.returncode==0 and a.kind!='verify-video':
        import hashlib
        files={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in out.rglob('*') if f.is_file()}
        if not files: raise ValueError('渲染器没有输出素材')
        (out/'production-complete.json').write_text(json.dumps({'files':files}),encoding='utf-8')
    raise SystemExit(r.returncode)
