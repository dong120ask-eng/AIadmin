"""Loopback Appium inspection transport. No login or publish actions."""
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from .media import validate_binding
from .store import Problem

LIMIT=4*1024*1024

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise Problem('Appium服务重定向已拒绝')

class AndroidInspector:
    def __init__(self, server='http://127.0.0.1:4723', timeout=15):
        parsed=urlsplit(server)
        if parsed.scheme!='http' or parsed.hostname not in {'localhost','127.0.0.1','::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise Problem('Appium仅连接本机HTTP服务，不接收认证信息')
        try: port=parsed.port
        except ValueError:raise Problem('Appium端口无效')
        if port is not None and not 1<=port<=65535:raise Problem('Appium端口无效')
        if parsed.path.rstrip('/') not in {'','/wd/hub'}:raise Problem('Appium路径只支持根路径或/wd/hub')
        self.server=server.rstrip('/')
        self.timeout=timeout
        self.session=None
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def request(self,method,path,payload=None):
        req=urllib.request.Request(self.server+path,method=method,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type':'application/json'})
        try:
            with self.opener.open(req,timeout=self.timeout) as response:
                raw=response.read(LIMIT+1)
            if len(raw)>LIMIT:raise Problem('Appium响应过大')
            data=json.loads(raw)
        except (OSError,ValueError,urllib.error.URLError):
            raise Problem('无法读取本机Appium响应；检查服务、驱动和设备')
        if not isinstance(data,dict) or 'value' not in data:raise Problem('Appium响应格式无效')
        value=data['value']
        if isinstance(value,dict) and value.get('error'):raise Problem('Appium操作失败；在本机检查驱动状态')
        return value

    def connect(self,binding):
        binding=validate_binding(binding)
        if binding['route'] not in {'android_device','android_emulator'}:raise Problem('请选择安卓设备路线')
        if self.session:raise Problem('已有设备会话')
        value=self.request('POST','/session',{'capabilities':{'alwaysMatch':{
            'platformName':'Android','appium:automationName':'UiAutomator2',
            'appium:udid':binding['device_udid'],'appium:appPackage':binding['app_package'],
            'appium:noReset':True,'appium:fullReset':False,'appium:autoLaunch':False,
            'appium:newCommandTimeout':60},'firstMatch':[{}]}})
        if not isinstance(value,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value.get('sessionId','')):
            raise Problem('Appium未返回有效会话')
        self.session=value['sessionId']
        caps=value.get('capabilities',{})
        actual=caps.get('appium:udid',caps.get('udid')) if isinstance(caps,dict) else None
        if actual!=binding['device_udid']:
            try:self.close()
            finally:raise Problem('Appium返回的设备身份不匹配或缺失')
        return {'session_created':True,'device_verified':True,'account_verified':False,
                'publishing_verified':False,'mode':'inspect_only'}

    def source(self):
        if not self.session:raise Problem('没有设备会话')
        value=self.request('GET','/session/'+self.session+'/source')
        if not isinstance(value,str):raise Problem('页面结构响应无效')
        return value

    def close(self):
        if self.session:
            session=self.session;self.session=None
            self.request('DELETE','/session/'+session)
