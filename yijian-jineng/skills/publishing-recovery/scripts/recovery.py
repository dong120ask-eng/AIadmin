"""Audit incomplete submissions or reconcile an explicitly verified result."""
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import ledger,read,inside,proof
def recover(root,task_id,record=None):
    l=ledger(root)
    try:
        task=l.load(task_id)
        if record is None: return {'task_id':task_id,'state':task['state'],'submission_attempted':bool(task.get('submit_attempt')),'next':'核验已有作品后reconcile或not-published；不可自动重发' if task['state'] in ('publishing','uncertain') else '按台账正常阶段继续'}
        if record.get('task_id')!=task_id or record.get('fingerprint')!=task['fingerprint'] or record.get('verified') is not True or not record.get('reviewer'): raise ValueError('结果记录必须绑定当前任务并有真实核验者')
        proof(l.root,record['evidence']); l.account(task,record.get('account_id'))
        if record['outcome']=='published':
            if not record.get('result_id') or record.get('title')!=task['title']: raise ValueError('缺对应作品ID和精确标题')
            if record.get('result_url'):
                u=urlparse(record['result_url'])
                if u.scheme!='https' or u.username or u.password: raise ValueError('作品链接无效')
            return l.change(task_id,'reconcile',observed=record['account_id'],evidence=record['evidence']['path'],result=record.get('result_url') or record['result_id'])
        if record['outcome']=='not-published': return l.change(task_id,'not-published',observed=record['account_id'],evidence=record['evidence']['path'])
        raise ValueError('未知结果不能转为成功或自动重试')
    finally: l.db.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True); p.add_argument('--task',required=True); p.add_argument('--verified-result')
    a=p.parse_args(); print(json.dumps(recover(a.root,a.task,read(inside(a.root,a.verified_result,True)) if a.verified_result else None),ensure_ascii=False,indent=2))
