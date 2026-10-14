"""Verified staging, preserved unrelated skills and rollback on rename failure."""
import argparse, hashlib, json, os, shutil, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def deploy(source,target,apply=False,backup=False):
    source=Path(source).resolve(); target=Path(target).absolute()
    if target.is_symlink() or any(p.is_symlink() for p in target.parents): raise ValueError('目标不能经过符号链接')
    target=target.resolve()
    if target==source or target.is_relative_to(source) or source.is_relative_to(target): raise ValueError('源码与部署目标不得互相包含')
    if target.name!='skills' or target.parent.name not in ('.agents','.dsh','.codebuddy'): raise ValueError('只支持宿主 skills 目录')
    files=[]
    for p in sorted(source.rglob('*')):
        if p.is_symlink(): raise ValueError('拒绝源码符号链接')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc': files.append(p)
    count=len(list(source.glob('*/SKILL.md')))
    if not count: raise ValueError('没有技能')
    changed=sum(1 for p in files if (target/p.relative_to(source)).exists() and (not (target/p.relative_to(source)).is_file() or sha(target/p.relative_to(source))!=sha(p)))
    result={'mode':'applied' if apply else 'plan','skill_count':count,'files':len(files),'changed':changed}
    if not apply: return result
    if changed and not backup: raise ValueError('已有差异；需 --backup 保存原文件')
    target.parent.mkdir(parents=True,exist_ok=True)
    lock=target.parent/'.skill-deploy.lock'; fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    run=uuid.uuid4().hex; stage=target.parent/('.skill-stage-'+run); old=target.parent/('.skill-backup-'+run); swapped=False
    try:
        if target.exists(): shutil.copytree(target,stage,symlinks=True)
        else: stage.mkdir()
        for p in files:
            d=stage/p.relative_to(source)
            if d.is_symlink() or any(q.is_symlink() for q in d.parents): raise ValueError('目标包含符号链接')
            if d.exists() and not d.is_file(): raise ValueError('文件/目录冲突')
            d.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,d)
            if sha(p)!=sha(d): raise ValueError('暂存文件校验失败')
        if target.exists(): target.rename(old)
        try: stage.rename(target); swapped=True
        except BaseException:
            if old.exists(): old.rename(target)
            raise
        result['backup']=str(old) if old.exists() else None
        return result
    finally:
        os.close(fd); lock.unlink(missing_ok=True)
        if not swapped and stage.exists(): shutil.rmtree(stage)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--target',required=True)
    p.add_argument('--apply',action='store_true'); p.add_argument('--backup',action='store_true')
    a=p.parse_args(); print(json.dumps(deploy(ROOT/'skills',a.target,a.apply,a.backup),ensure_ascii=False))
