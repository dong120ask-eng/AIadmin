"""Schedule planned jobs by explicit timezone, account cooldown and device serialization."""
import argparse,json,sys
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import read,save,inside,instant
def schedule(jobs,policy):
    start=instant(policy['start']); gap=policy['account_gap_minutes']; duration=policy['device_slot_minutes']; cap=policy['account_daily_cap']
    if any(isinstance(v,bool) or not isinstance(v,int) or v<1 for v in (gap,duration,cap)): raise ValueError('日历间隔、设备时段与日上限须正整数')
    account_next={}; device_next={}; daily={}; result=[]; seen=set()
    for job in jobs:
        if job['id'] in seen: raise ValueError('任务ID重复')
        seen.add(job['id']); account=job['account_id']; device=job['device_id']
        when=max(start,account_next.get(account,start),device_next.get(device,start))
        while daily.get((account,when.date()),0)>=cap:
            when=(when+timedelta(days=1)).replace(hour=start.hour,minute=start.minute,second=start.second,microsecond=0)
            when=max(when,device_next.get(device,start),account_next.get(account,start))
        daily[(account,when.date())]=daily.get((account,when.date()),0)+1
        account_next[account]=when+timedelta(minutes=gap); device_next[device]=when+timedelta(minutes=duration)
        result.append({**job,'scheduled_at':when.isoformat(),'device_slot_until':device_next[device].isoformat()})
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','spec','output'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); data=read(inside(a.root,a.spec,True)); save(inside(a.root,a.output),{'jobs':schedule(data['jobs'],data['policy']),'stage':'scheduled-plan','note':'日历不直接发帖；仍需已质检任务、真实草稿及当前确认'})
