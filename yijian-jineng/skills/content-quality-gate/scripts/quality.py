"""Validate actual task files, required human fact review and platform rules."""
import argparse,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import ledger,read,save,inside,proof
def inspect(root,task_id,review):
    l=ledger(root)
    try:
        task=l.load(task_id); l.check(task); issues=[]
        text=l.path(task['text']['path']).read_text(encoding='utf-8-sig')
        if re.search(r'待补充|待核对|TODO|PLACEHOLDER|示例正文',text,re.I): issues.append('正文有未完成占位')
        rules=review.get('platform_rules')
        if not isinstance(rules,dict) or rules.get('platform')!=task['instance']['platform']: issues.append('缺当前平台规则')
        else:
            for field,value in [('title',task['title']),('body',text)]:
                limit=rules.get(field+'_max_chars')
                if limit is not None and (not isinstance(limit,int) or limit<1 or len(value)>limit): issues.append(field+'长度超限或规则无效')
            for word in rules.get('blocked_phrases',[]):
                if word in text or word in task['title']: issues.append('命中禁用表达：'+word)
        if review.get('facts_reviewed') is not True or review.get('rights_reviewed') is not True or not review.get('reviewer'): issues.append('缺事实、素材权利审核及审核者')
        if review.get('task_id')!=task_id or review.get('fingerprint')!=task['fingerprint']: issues.append('审核不绑定当前任务')
        if not review.get('evidence'): issues.append('缺审核证据')
        for record in review.get('evidence',[]): proof(l.root,record)
        if review.get('regulated_health') is True:
            if review.get('health_reviewed') is not True or not review.get('required_disclaimer') or review['required_disclaimer'] not in text: issues.append('健康类审核/声明未完成')
        media=[]
        for record in task['media']:
            p=l.path(record['path']); item={'path':record['path'],'bytes':p.stat().st_size}
            if p.stat().st_size==0: issues.append('空素材')
            if p.suffix.lower() in ('.jpg','.jpeg','.png','.webp'):
                from PIL import Image
                with Image.open(p) as image:
                    image.verify()
                with Image.open(p) as image: item['size']=list(image.size)
            elif p.suffix.lower() in ('.mp4','.mov'):
                report=review.get('video_quality_report')
                if not report: issues.append('缺视频质检报告')
                else:
                    proof(l.root,report); data=read(inside(l.root,report['path'],True))
                    if data.get('全部通过') is not True or record['sha256'] not in report.get('media_sha256',[]): issues.append('视频质检未通过或未绑定当前视频指纹')
            else: issues.append('未支持的媒体格式')
            media.append(item)
        return {'schema':'content-qa/v1','task_id':task_id,'fingerprint':task['fingerprint'],'passed':not issues,'issues':issues,'reviewer':review.get('reviewer'),'media':media,'review':review}
    finally: l.db.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','task','review','output'): p.add_argument('--'+k,required=True)
    p.add_argument('--apply',action='store_true'); a=p.parse_args(); root=Path(a.root).resolve()
    report=inspect(root,a.task,read(inside(root,a.review,True))); out=inside(root,a.output); save(out,report)
    if a.apply:
        if not report['passed']: raise ValueError('质检未通过，任务不进入reviewed')
        l=ledger(root)
        try: l.change(a.task,'qa',evidence=str(out))
        finally: l.db.close()
    print(json.dumps(report,ensure_ascii=False,indent=2))
