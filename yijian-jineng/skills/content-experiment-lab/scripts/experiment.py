"""Plan reproducible creative variants and compare evidence-backed binomial rates."""
import argparse,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import read,save,inside,finite
def assign(items,variants,seed):
    if len(variants)<2 or len(set(variants))!=len(variants): raise ValueError('至少两个不同方案')
    if len({x['id'] for x in items})!=len(items): raise ValueError('任务ID重复')
    ordered=sorted(items,key=lambda x:hashlib.sha256((str(seed)+x['id']).encode()).hexdigest())
    return [{**item,'variant':variants[i%len(variants)],'assignment_seed':str(seed)} for i,item in enumerate(ordered)]
def wilson(events,trials):
    finite(events); finite(trials)
    if trials<=0 or events>trials: raise ValueError('二项事件数必须不超过试验次数且次数大于0')
    z=1.96; p=events/trials; d=1+z*z/trials; center=(p+z*z/(2*trials))/d; width=z*math.sqrt(p*(1-p)/trials+z*z/(4*trials*trials))/d
    return [max(0,center-width),min(1,center+width)]
def compare(groups,minimum):
    if isinstance(minimum,bool) or not isinstance(minimum,int) or minimum<1: raise ValueError('最小样本量必须正整数')
    if len(groups)<2: raise ValueError('至少两个方案')
    rows=[]
    for group in groups:
        intervals=wilson(group['events'],group['trials']); rows.append({**group,'rate':group['events']/group['trials'],'interval_95':intervals})
    ordered=sorted(rows,key=lambda x:x['rate'],reverse=True)
    enough=all(x['trials']>=minimum for x in rows); separated=ordered[0]['interval_95'][0]>max(x['interval_95'][1] for x in ordered[1:])
    return {'groups':rows,'result':'separated-observed-rates' if enough and separated else 'inconclusive','best_observed':ordered[0]['variant'] if enough and separated else None,'note':'仅适用于明确的二项事件，如有点击的曝光；点赞评论合计不能当二项人数。不自动证明因果。'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('mode',choices=('assign','compare'))
    for k in ('root','spec','output'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); data=read(inside(a.root,a.spec,True)); result=assign(data['items'],data['variants'],data['seed']) if a.mode=='assign' else compare(data['groups'],data['minimum_trials']); save(inside(a.root,a.output),result)
