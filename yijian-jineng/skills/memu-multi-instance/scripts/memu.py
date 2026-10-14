"""Official MEMUC adapter; mutating commands default to plan."""
import argparse,json,shutil,subprocess
from pathlib import Path
def command(exe,action,index=None,name=None,path=None):
    if action=="list": return [exe,"listvms"]
    if action=="create": return [exe,"create"]
    if index is None or index<0: raise ValueError("必须明确实际模拟器索引")
    items={"status":[exe,"isvmrunning","-i",str(index)],"start":[exe,"start","-i",str(index),"-b"],
           "stop":[exe,"stop","-i",str(index)],"clone":[exe,"clone","-i",str(index)]+(["-r",name] if name else []),
           "apps":[exe,"getappinfolist","-i",str(index)]}
    if action=="install":
        if not path or not Path(path).is_file() or Path(path).suffix.lower()!=".apk": raise ValueError("需已核验官方APK")
        return [exe,"installapp","-i",str(index),str(Path(path).resolve())]
    return items[action]
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("list","status","create","clone","start","stop","apps","install"))
    p.add_argument("--memuc",default=shutil.which("memuc")); p.add_argument("--index",type=int)
    p.add_argument("--name"); p.add_argument("--apk"); p.add_argument("--apply",action="store_true")
    a=p.parse_args(); exe=a.memuc or "memuc.exe"; args=command(exe,a.action,a.index,a.name,a.apk)
    if a.action in ("list","status","apps") or a.apply:
        if not Path(exe).is_file(): raise ValueError("未找到memuc.exe，安装官方模拟器后给出路径")
        r=subprocess.run(args,capture_output=True,timeout=180)
        print(json.dumps({"returncode":r.returncode,"output":r.stdout.decode("utf-8",errors="replace"),"error":r.stderr.decode("utf-8",errors="replace")},ensure_ascii=False))
        raise SystemExit(r.returncode)
    print(json.dumps({"command":args,"mode":"plan","note":"未执行；无删除、随机换机或伪装命令"},ensure_ascii=False))
