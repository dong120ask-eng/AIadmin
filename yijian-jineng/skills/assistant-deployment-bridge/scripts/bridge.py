"""Deploy real execution hosts or export a knowledge pack for chat-only clients."""
import argparse,json,subprocess,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import inside,save,digest
HOSTS={'harness':'.dsh','workbuddy':'.codebuddy','codex':'.agents'}
def locate(root,explicit=None):
    root=Path(root).resolve()
    if explicit: bundle=Path(explicit).resolve()
    elif (root/'deployment-latest.json').is_file(): bundle=Path(json.loads((root/'deployment-latest.json').read_text(encoding='utf-8-sig'))['bundle']).resolve()
    else: bundle=root/'自媒体技能套件'
    if not bundle.is_relative_to(root) or not (bundle/'tools/deploy.py').is_file(): raise ValueError('需本工作区内完整工具包，或部署后的deployment-latest.json')
    return bundle
def export_knowledge(root,bundle,host,output):
    out=inside(root,output)
    if out.exists(): raise ValueError('导出目录已存在')
    out.mkdir(parents=True)
    prompt='读取技能资料，按产品事实和账号人设生成内容。当前普通聊天客户端不自动获得文件执行或手机控制权限；把操作任务交给已部署的Harness、WorkBuddy或Codex执行。API凭据与聊天登录独立。最终发布仍需具体作品/账号的用户确认。'
    save(out/'AI调用指令.md',prompt)
    with zipfile.ZipFile(out/'技能知识包.zip','x',zipfile.ZIP_DEFLATED) as z:
        for f in sorted((bundle/'skills').rglob('*')):
            if f.is_symlink(): raise ValueError('拒绝技能链接')
            if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc': z.write(f,str(f.relative_to(bundle)).replace('\\','/'))
    return {'host':host,'mode':'knowledge-export','instructions':str(out/'AI调用指令.md'),'archive':str(out/'技能知识包.zip'),'sha256':digest(out/'技能知识包.zip')}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True); p.add_argument('--bundle'); p.add_argument('--host',choices=tuple(HOSTS)+('doubao','qwen'),required=True); p.add_argument('--output'); p.add_argument('--apply',action='store_true'); a=p.parse_args(); root=Path(a.root).resolve(); bundle=locate(root,a.bundle)
    if a.host in HOSTS:
        args=[sys.executable,'-X','utf8',str(bundle/'tools/deploy.py'),'--target',str(root/HOSTS[a.host]/'skills')]
        if a.apply: args+=['--apply','--backup']
        subprocess.run(args,check=True,timeout=300)
    elif not a.apply: print(json.dumps({'host':a.host,'mode':'plan','next':'知识包导出；不假定聊天客户端有执行工具'},ensure_ascii=False))
    elif not a.output: raise ValueError('知识导出需output目录')
    else: print(json.dumps(export_knowledge(root,bundle,a.host,a.output),ensure_ascii=False))
