"""Read-only local USB/ADB check. Does not log in, switch accounts or publish."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path


def check(adb=None):
    binary=str(Path(adb).resolve()) if adb else shutil.which('adb')
    if not binary or not Path(binary).is_file():
        return {'adb_available':False,'devices':[],'ready':False,'next_step':'从Android官方Platform Tools安装ADB，或用--adb指定已安装的adb.exe'}
    try:
        p=subprocess.run([binary,'devices','-l'],capture_output=True,text=True,timeout=10,shell=False)
    except (OSError,subprocess.TimeoutExpired):
        return {'adb_available':True,'devices':[],'ready':False,'next_step':'ADB启动失败或超时，请在本机检查工具与驱动'}
    devices=[]
    for line in p.stdout.splitlines():
        parts=line.split()
        if len(parts)>=2 and parts[1] in {'device','unauthorized','offline','recovery','sideload'}:
            devices.append({'udid':parts[0],'state':parts[1]})
    ready=p.returncode==0 and any(d['state']=='device' for d in devices)
    return {'adb_available':True,'devices':devices,'ready':ready,
            'multiple_devices':len(devices)>1,'account_verified':False,'publishing_verified':False,
            'next_step':'指定实际UDID后连接本机Appium；多设备不得猜测' if ready else '检查数据线、USB调试、驱动，并在手机上允许这台电脑调试',
            'scope':'仅检测ADB连接，没有执行手机界面动作'}


def main():
    parser=argparse.ArgumentParser(description='USB安卓手机连接检查；不登录、不切号、不发布')
    parser.add_argument('--adb',help='本机已安装的adb.exe路径')
    args=parser.parse_args()
    result=check(args.adb);print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ready'] else 2

if __name__=='__main__':raise SystemExit(main())
