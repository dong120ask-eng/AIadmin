"""Controlled Windows software and project dependency installation. Plan by default."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
KNOWN={"scrcpy":"Genymobile.scrcpy","ffmpeg":"Gyan.FFmpeg","python":"Python.Python.3.12"}
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("kind",choices=("winget","python","installer")); p.add_argument("--package",choices=KNOWN)
    p.add_argument("--python",default=sys.executable); p.add_argument("--requirements"); p.add_argument("--installer")
    p.add_argument("--sha256"); p.add_argument("--args-json",default="[]"); p.add_argument("--apply",action="store_true")
    a=p.parse_args()
    if a.kind=="winget":
        if not a.package: raise ValueError("缺少已知软件包")
        exe=shutil.which("winget")
        if not exe: raise ValueError("本机无winget")
        args=[exe,"install","--id",KNOWN[a.package],"--exact","--source","winget","--silent","--disable-interactivity"]
    elif a.kind=="python":
        req=Path(a.requirements or "")
        if not req.is_file(): raise ValueError("缺项目requirements文件")
        # Explicit requirements only, no arbitrary pip switches or local code URLs.
        lines=[l.strip() for l in req.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        import re
        if any(not re.fullmatch(r"[A-Za-z0-9_.-]+(?:==[A-Za-z0-9_.+-]+)?",l) for l in lines): raise ValueError("requirements只允许包名或精确版本")
        args=[a.python,"-m","pip","install","--index-url","https://pypi.org/simple",*lines]
    else:
        installer=Path(a.installer or "").resolve()
        if not installer.is_file() or installer.suffix.lower() not in (".exe",".msi"): raise ValueError("需官方本地安装包")
        actual=hashlib.sha256(installer.read_bytes()).hexdigest()
        if not a.sha256 or actual!=a.sha256: raise ValueError("安装包指纹未确认")
        extra=json.loads(a.args_json)
        if not isinstance(extra,list) or any(not isinstance(x,str) for x in extra): raise ValueError("安装参数需字符串数组")
        args=[str(installer),*extra]
        if installer.suffix.lower()==".msi": args=["msiexec.exe","/i",str(installer),"/norestart",*extra]
    if not a.apply: print(json.dumps({"mode":"plan","command":args,"note":"先核对来源、签名、版本和授权；无全量升级、卸载或安全设置变更"},ensure_ascii=False)); sys.exit()
    r=subprocess.run(args,timeout=1800)
    print(json.dumps({"returncode":r.returncode,"note":"遇到UAC或系统权限提示由用户处理，不自动接受或重启"},ensure_ascii=False))
    raise SystemExit(r.returncode)
