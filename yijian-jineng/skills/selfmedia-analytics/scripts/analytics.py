"""Import evidence-backed content metrics and compute account/platform rates."""
import argparse,csv,json,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import read,save,inside,digest,instant,finite
def aggregate(rows):
    groups=defaultdict(lambda:{'posts':0,'views':0,'likes':0,'comments':0,'saves':0,'shares':0})
    seen=set()
    for row in rows:
        key=(row['platform'],row['account_id'],row['content_id'],row['window'])
        if key in seen: raise ValueError('同作品同观察窗重复，不能重复累计')
        seen.add(key)
        if instant(row['collected_at'])<instant(row['published_at']): raise ValueError('采集时间早于发布')
        if row['window'] not in ('2h','24h','72h','custom'): raise ValueError('观察窗口无效')
        g=groups[(row['platform'],row['account_id'],row['window'])]; g['posts']+=1
        for k in ('views','likes','comments','saves','shares'): g[k]+=finite(row[k])
    return [{'platform':k[0],'account_id':k[1],'window':k[2],**v,'engagement_per_view':(v['likes']+v['comments']+v['saves']+v['shares'])/v['views'] if v['views'] else None} for k,v in sorted(groups.items())]
def import_metrics(root,file):
    file=inside(root,file,True)
    with file.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    for row in rows:
        for k in ('views','likes','comments','saves','shares'): row[k]=float(row[k])
    return {'source':{'path':str(file.relative_to(Path(root).resolve())),'sha256':digest(file)},'groups':aggregate(rows),'rows':rows,'note':'导入值来自实际导出文件；统计不自动证明因果或原始数据真实性'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','csv','output'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); report=import_metrics(a.root,a.csv); save(inside(a.root,a.output),report); print(json.dumps(report,ensure_ascii=False,indent=2))
