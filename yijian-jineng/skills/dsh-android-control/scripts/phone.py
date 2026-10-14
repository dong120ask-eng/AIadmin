"""Explicit-device ADB bridge. No install, login, delete or publish commands."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

def run(adb, *args, binary=False):
    r = subprocess.run([adb, *args], capture_output=True, timeout=40)
    if r.returncode:
        raise ValueError(r.stderr.decode("utf-8", errors="replace").strip() or "ADB failed")
    return r.stdout if binary else r.stdout.decode("utf-8", errors="replace").strip()

def parse_devices(raw):
    result = []
    for line in raw.splitlines():
        match = re.match(r"^(\S+)\s+(device|unauthorized|offline)(?:\s|$)", line)
        if match:
            result.append({"serial": match[1], "state": match[2]})
    return result

def require_device(rows, serial):
    if not serial:
        raise ValueError("必须显式指定 --serial，多设备不能默认选第一台")
    row = next((r for r in rows if r["serial"] == serial), None)
    if not row or row["state"] != "device":
        raise ValueError("设备不在线或未授权，请在手机确认 USB 调试")
    return row

def main():
    p = argparse.ArgumentParser(description=__doc__)
    candidate=shutil.which('adb')
    if not candidate:
        try:
            from adbutils._utils import adb_path
            candidate=adb_path()
        except ImportError: pass
    p.add_argument("--adb", default=candidate)
    p.add_argument("--serial")
    p.add_argument("--root", required=True)
    s = p.add_subparsers(dest="cmd", required=True)
    for name in ("devices", "info", "apps", "users"):
        s.add_parser(name)
    capture = s.add_parser("screenshot"); capture.add_argument("--output", required=True)
    op = s.add_parser("open"); op.add_argument("--package", required=True); op.add_argument("--user", type=int)
    push = s.add_parser("push"); push.add_argument("--file", required=True); push.add_argument("--task", required=True)
    a = p.parse_args()
    if not a.adb or not Path(a.adb).is_file():
        raise ValueError("未找到 adb，请传入 --adb 的完整路径")
    root = Path(a.root).resolve()
    rows = parse_devices(run(a.adb, "devices", "-l"))
    if a.cmd == "devices":
        print(json.dumps(rows, ensure_ascii=False, indent=2)); return
    require_device(rows, a.serial)
    prefix = ("-s", a.serial)
    if a.cmd == "info":
        result = {k: run(a.adb, *prefix, "shell", "getprop", k) for k in
                  ("ro.product.manufacturer", "ro.product.model", "ro.build.version.release", "ro.build.version.sdk")}
    elif a.cmd == "apps":
        result = run(a.adb, *prefix, "shell", "pm", "list", "packages")
    elif a.cmd == "users":
        result = run(a.adb, *prefix, "shell", "pm", "list", "users")
    elif a.cmd == "screenshot":
        dest = (root / a.output).resolve()
        if not dest.is_relative_to(root) or dest.exists():
            raise ValueError("截图必须是工作区内的新文件")
        raw = run(a.adb, *prefix, "exec-out", "screencap", "-p", binary=True)
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("截图不是有效 PNG，未保存")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(raw)
        result = {"file": str(dest), "sha256": hashlib.sha256(raw).hexdigest()}
    elif a.cmd == "open":
        if not re.fullmatch(r"[A-Za-z0-9_.]+", a.package) or (a.user is not None and a.user < 0):
            raise ValueError("包名或系统用户无效")
        args = ["shell", "monkey"]
        if a.user is not None:
            args += ["--user", str(a.user)]
        args += ["-p", a.package, "-c", "android.intent.category.LAUNCHER", "1"]
        result = {"output": run(a.adb, *prefix, *args), "note": "仅发起启动，仍需截图核对实例和账号"}
    else:
        local = (root / a.file).resolve()
        if not local.is_relative_to(root) or not local.is_file():
            raise ValueError("只能传工作区内已有文件")
        if not re.fullmatch(r"[a-zA-Z0-9-]+", a.task):
            raise ValueError("task 参数格式无效")
        # ASCII names avoid shell interpolation and preserve each task's media identity.
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        ext = local.suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".mp4", ".mp3", ".srt", ".txt"):
            raise ValueError("不支持此素材类型")
        folder = "/sdcard/Download/selfmedia/" + a.task
        run(a.adb, *prefix, "shell", "mkdir", "-p", folder)
        target = folder + "/" + digest + ext
        result = {"output": run(a.adb, *prefix, "push", str(local), target), "remote": target,
                  "note": "仅传到主用户共享存储；分身或工作资料的素材可见性须单独验证"}
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.TimeoutExpired) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False)); sys.exit(2)
