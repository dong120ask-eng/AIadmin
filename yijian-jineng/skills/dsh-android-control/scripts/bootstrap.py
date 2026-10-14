"""Initialize the installed uiautomator2 device service and save read-only evidence."""
import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--serial", required=True)
    p.add_argument("--root", required=True)
    a = p.parse_args()
    adb = shutil.which("adb")
    if not adb:
        raise RuntimeError("未找到 adb")
    raw = subprocess.check_output([adb, "devices"], timeout=20).decode()
    if not any(line.split()[:2] == [a.serial, "device"] for line in raw.splitlines()):
        raise RuntimeError("指定设备不在线或未授权")
    import uiautomator2 as u2
    device = u2.connect(a.serial)
    now = datetime.now(timezone(timedelta(hours=8)))
    folder = Path(a.root).resolve() / "evidence" / "device-setup" / (a.serial[-4:] + "-" + now.strftime("%Y%m%d-%H%M%S"))
    folder.mkdir(parents=True, exist_ok=False)
    info = dict(device.info)
    current = device.app_current()
    xml = device.dump_hierarchy()
    (folder / "界面.xml").write_text(xml, encoding="utf-8")
    device.screenshot(str(folder / "屏幕.png"))
    jar = subprocess.check_output([adb, "-s", a.serial, "shell", "ls", "-l", "/data/local/tmp/u2.jar"], timeout=20).decode("utf-8", errors="replace").strip()
    result = {
        "checked_at": now.isoformat(), "serial": a.serial,
        "uiautomator2_version": importlib.metadata.version("uiautomator2"),
        "device_service": "connected", "device_jar": jar,
        "device_info": info, "foreground": current,
        "hierarchy_nodes": xml.count("<node "),
        "screenshot": str(folder / "屏幕.png"),
        "hierarchy_sha256": hashlib.sha256(xml.encode()).hexdigest(),
        "note": "仅初始化官方包随附设备服务并读取画面，未输入、登录、改变账号或发布"
    }
    (folder / "检查结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
