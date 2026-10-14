"""Prepare repository source only; keep offline binaries in release assets."""
import argparse,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ALLOWED=('skills','tools','config','docs','tests','README.md','AI一键部署指令.md','requirements-base.txt','requirements-video.txt','requirements-browser.txt','一键部署.cmd','查看工作进度.cmd')
def prepare(target):
    target=Path(target).resolve()
    if target.exists() or target.is_relative_to(ROOT) or ROOT.is_relative_to(target): raise ValueError('需新目录，不能与源码互相包含')
    selected=[]
    for name in ALLOWED:
        source=ROOT/name
        for f in (source.rglob('*') if source.is_dir() else [source]):
            if f.is_symlink(): raise ValueError('拒绝源码链接')
            if not f.is_file() or '__pycache__' in f.parts or f.suffix=='.pyc': continue
            if f.name.startswith('.env') or f.suffix.lower() in ('.zip','.sqlite','.exe','.dll','.whl'): raise ValueError('源码树混入运行数据或二进制')
            selected.append(f)
    target.mkdir(parents=True)
    for f in selected:
        d=target/f.relative_to(ROOT); d.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(f,d)
    (target/'.gitignore').write_text('.env*\n__pycache__/\n*.pyc\noffline/\nstate/\nevidence/\noutputs/\nwork/\n*.zip\n*.sqlite\n',encoding='utf-8')
    return {'source':str(target),'files':len(selected)+1,'remote_created':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',required=True); a=p.parse_args()
    print(json.dumps(prepare(a.output),ensure_ascii=False))
