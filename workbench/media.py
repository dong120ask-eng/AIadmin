"""Evidence-aware media discovery and execution planning, without publishing."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from .store import Problem, identifier
from .recipes import TYPES

INDEX = Path(__file__).parent / 'data' / 'media-index.json'


def media_index(category=None, keyword=None):
    data = json.loads(INDEX.read_text(encoding='utf-8'))
    data['applications'] = [r for r in data['applications']
                            if (not category or r['category'] == category)
                            and (not keyword or keyword.casefold() in r['name'].casefold())]
    data['filtered_count'] = len(data['applications'])
    return data


def android_doctor():
    bins = {name: shutil.which(name) for name in ('node', 'java', 'adb', 'appium', 'emulator')}
    result = {'tools': {k: bool(v) for k, v in bins.items()}, 'devices': [],
              'user_windows_access': False, 'publishing_verified': False,
              'emulator_compatibility': 'per_app_test_required'}
    if bins['adb']:
        try:
            p = subprocess.run([bins['adb'], 'devices', '-l'], capture_output=True, text=True,
                               timeout=10, shell=False)
            for line in p.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2 and re.fullmatch(r'[a-zA-Z0-9_.:-]{1,128}', parts[0]):
                    result['devices'].append({'udid': parts[0], 'state': parts[1]})
            result['adb_check'] = 'ok' if p.returncode == 0 else 'failed'
        except (OSError, subprocess.TimeoutExpired):
            result['adb_check'] = 'failed'
    return result


def validate_binding(data):
    if not isinstance(data, dict):
        raise Problem('账号执行配置必须为对象')
    permitted = {'tenant_id','project_id','channel_id','account_id','account_unique_id',
                 'route','profile_ref','device_udid','app_package','identity_verified_at'}
    if set(data) - permitted:
        raise Problem('配置含未知字段；不得提交密码、Cookies或令牌')
    for field in ('tenant_id','project_id','account_id'):
        identifier(data.get(field, ''))
    channel = next((r for r in media_index()['channels'] if r['id'] == data.get('channel_id')), None)
    if not channel:
        raise Problem('发布渠道不存在')
    if data.get('route') not in {'browser','android_device','android_emulator'}:
        raise Problem('选择浏览器、安卓真机或安卓模拟器')
    account = data.get('account_unique_id')
    if not isinstance(account, str) or not account.strip() or len(account) > 200:
        raise Problem('必须绑定实际账号唯一标识，不能只用昵称')
    if data['route'] == 'browser':
        identifier(data.get('profile_ref', ''))
    else:
        if not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,128}', data.get('device_udid', '')):
            raise Problem('设备标识无效')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', data.get('app_package', '')):
            raise Problem('须填写实际应用包名；不使用猜测的包名')
    return dict(data)


def execution_plan(binding, request):
    binding = validate_binding(binding)
    if not isinstance(request, dict):
        raise Problem('任务必须为对象')
    for field in ('tenant_id','project_id','account_id','channel_id'):
        if request.get(field) != binding[field]:
            raise Problem('任务与账号执行配置不匹配', 409)
    kind = request.get('content_type')
    if kind not in TYPES:
        raise Problem('内容类型无效')
    mode = request.get('publish_mode', 'draft_only')
    if mode not in {'draft_only','review_then_publish','auto_publish'}:
        raise Problem('发布模式无效')
    channel = next(r for r in media_index()['channels'] if r['id'] == binding['channel_id'])
    reasons = []
    if channel['evidence_status'] == 'closure_notice_found':
        reasons.append('发现关闭入口公告；禁止复用旧流程')
    if kind not in channel['forms']:
        reasons.append('该形式尚无可用发布证据')
    if not binding.get('identity_verified_at'):
        reasons.append('实际会话中的账号身份尚未核验')
    surface = channel['surface']
    if surface == 'browser' and binding['route'] != 'browser':
        reasons.append('官方资料指向网页渠道；安卓入口尚未核实')
    if binding['route'] == 'browser':
        resource = 'browser-profile:' + binding['profile_ref']
    else:
        resource = 'android-device:' + binding['device_udid']
    reasons.append('平台专用执行器和选择器未接入实测')
    return {'status':'blocked', 'execution':'plan_only', 'published':False,
            'binding':binding, 'content_type':kind, 'publish_mode':mode,
            'exclusive_resource':resource, 'entry_url':channel['entry_url'],
            'blockers':reasons, 'steps':[
                '检查发布规则、账号资质与执行授权', '打开指定会话／设备，不切换其他账号',
                '从实际界面核验账号唯一ID', '检查真实产物与审核版本',
                '进入已核实的内容编辑器并填写', '核验预览、声明、权限及频次',
                '按授权保存草稿或提交', '查作品记录并保存真实发布证据'],
            'recovery':'结果不明时先查询；禁止盲目重复提交',
            'credential_handling':'登录、验证码、实名验证在官方界面完成；不经聊天或任务JSON传输',
            'agent_clients':['codex','workbuddy','doubao','qianwen'],
            'agent_client_status':'规则交接；未证明四端均具备本机浏览器／设备权限'}
