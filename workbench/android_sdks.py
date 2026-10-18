"""Optional local Android inspection SDKs, loaded only when explicitly selected."""
import html
import importlib
import json
import re
import shutil
import subprocess
from .media import validate_binding
from .store import Problem


def require_device(serial):
    if not isinstance(serial,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',serial):raise Problem('设备UDID无效')
    adb=shutil.which('adb')
    if not adb:raise Problem('本机ADB未安装或不在PATH')
    try:p=subprocess.run([adb,'devices'],capture_output=True,text=True,timeout=10,shell=False)
    except (OSError,subprocess.TimeoutExpired):raise Problem('本机ADB检查失败')
    online={parts[0] for line in p.stdout.splitlines() if len(parts:=line.split())>=2 and parts[1]=='device'}
    if p.returncode or serial not in online:raise Problem('指定设备未在线；不得改用另一台手机')


class LocalSdkInspector:
    def __init__(self,backend):
        modules={'uiautomator2':'uiautomator2','mobilerun':'mobilerun_core'}
        if backend not in modules:raise Problem('安卓后端无效')
        try:self.module=importlib.import_module(modules[backend])
        except ImportError:raise Problem('可选安卓SDK尚未安装；在本机隔离环境按官方说明安装')
        self.backend=backend;self.device=None;self.serial=None

    def connect(self,binding):
        binding=validate_binding(binding)
        if binding['route'] not in {'android_device','android_emulator'}:raise Problem('选择安卓设备路线')
        if self.device is not None:raise Problem('已有设备连接')
        serial=binding['device_udid'];require_device(serial)
        if self.backend=='uiautomator2':
            self.device=self.module.connect(serial)
            if getattr(self.device,'serial',None)!=serial:
                self.device=None;raise Problem('SDK返回的设备序列号不匹配')
        else:
            self.device=self.module.Mobilerun().connect(serial,backend='local-android-adb')
        self.serial=serial
        return {'device_verified':True,'account_verified':False,'publishing_verified':False,
                'backend':self.backend,'mode':'inspect_only','cloud_backend_selected':False}

    def source(self):
        if self.device is None:raise Problem('没有设备连接')
        require_device(self.serial)
        if self.backend=='uiautomator2':
            value=self.device.dump_hierarchy()
            if not isinstance(value,str) or not value.strip():raise Problem('SDK未返回页面结构')
        else:
            # Persist structured SDK UI in an explicitly labelled XML container.
            data=json.dumps(self.device.ui(),ensure_ascii=False)
            value='<mobilerun-ui-json>'+html.escape(data)+'</mobilerun-ui-json>'
        if len(value.encode('utf-8'))>4*1024*1024:raise Problem('页面结构过大')
        return value

    def close(self):
        # Do not invent SDK disconnect calls or kill a phone's apps/services.
        self.device=None;self.serial=None
