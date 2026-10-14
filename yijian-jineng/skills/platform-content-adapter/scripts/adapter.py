"""Validate platform-specific task handoff and settings before calibrated UI execution."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import ledger,inside,read,save,proof

CATALOG=Path(__file__).resolve().parents[1]/'references/capabilities.json'

def capabilities():
    return read(CATALOG)['platforms']

def validate_review(task,profile):
    policy=capabilities().get(task['instance']['platform'])
    if not policy: return
    fmt=profile.get('content_format')
    if fmt not in policy['formats']: raise ValueError('平台不支持本交付工具的体裁：'+str(fmt))
    review=profile.get('platform_review',{})
    if review.get('task_id')!=task['id'] or review.get('fingerprint')!=task['fingerprint'] or not review.get('reviewer'):
        raise ValueError('平台设置审核必须绑定精确任务和素材指纹')
    fields=review.get('confirmed',{})
    if not isinstance(fields,dict) or any(fields.get(k) is not True for k in policy['review_fields']):
        raise ValueError('缺平台设置核验：'+','.join(policy['review_fields']))
    if not review.get('evidence'): raise ValueError('缺平台设置真实证据')
    suffixes=[Path(x['path']).suffix.lower() for x in task['media']]
    if fmt=='video' and (len(suffixes)!=1 or suffixes[0] not in ('.mp4','.mov')): raise ValueError('视频体裁需要一个已保存视频')
    if fmt=='image' and (not suffixes or any(s not in ('.png','.jpg','.jpeg','.webp') for s in suffixes)): raise ValueError('图文体裁需要真实图片')
    if fmt in ('article','text') and any(s not in ('.png','.jpg','.jpeg','.webp') for s in suffixes): raise ValueError('正文体裁不接收视频混入')
    if fmt=='text' and suffixes: raise ValueError('纯文本体裁不能包含媒体，请选图文或视频')
    needed={'body'} | ({'title'} if policy['uses_title'] else set())
    fills={s.get('value') for s in profile.get('draft_steps',[]) if s.get('action')=='fill'}
    if not needed.issubset(fills): raise ValueError('校准草稿步骤缺正文或标题字段')
    if task['media'] and profile.get('backend')=='browser' and not any(s.get('action')=='files' for s in profile.get('draft_steps',[])):
        raise ValueError('网页素材交接缺真实文件上传步骤')

def handoff(root,task_id,profile,output):
    l=ledger(root)
    try:
        task=l.load(task_id);l.check(task)
        if profile.get('platform')!=task['instance']['platform'] or profile.get('account_id')!=task['instance']['account_id'] or profile.get('device_id')!=task['instance']['device_id']:
            raise ValueError('交接配置与任务平台、账号或设备不符')
        if profile.get('visibility_value')!=task['visibility']: raise ValueError('交接可见性不符')
        if task['state'] not in ('prepared','reviewed','draft'): raise ValueError('只交接尚未提交的任务；提交中或结果不明先恢复')
        validate_review(task,profile)
        policy=capabilities().get(profile['platform'])
        if not policy: raise ValueError('本交接工具未登记该平台')
        for record in profile['platform_review']['evidence']: proof(l.root,record)
        result={'schema':'platform-handoff/v1','task_id':task_id,'fingerprint':task['fingerprint'],
                'platform':profile['platform'],'content_format':profile['content_format'],
                'uses_title':policy['uses_title'],'text':task['text'],'media':task['media'],
                'visibility':task['visibility'],'required_review_fields':policy['review_fields'],
                'platform_review':profile['platform_review'],'state':task['state'],
                'next':'质检与真实页面校准后prepare草稿；本文件不是发布授权，也不证明上传成功'}
        save(inside(root,output),result);return result
    finally:l.db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','task','profile','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args()
    try:print(json.dumps(handoff(a.root,a.task,read(inside(a.root,a.profile,True)),a.output),ensure_ascii=False,indent=2))
    except (ValueError,KeyError) as e:p.exit(2,'平台交接未完成：'+str(e)+'\n')
