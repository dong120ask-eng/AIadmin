"""Build a facts-and-framework generation prompt without copying the sample text."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import read,save,inside,digest
def remix(root,brief,framework,account):
    facts=inside(root,brief,True); structure=read(inside(root,framework,True)); persona=read(inside(root,account,True))
    keys=('hook_type','logic','outline','rhythm','proof_strategy','audience')
    selected={k:structure[k] for k in keys if k in structure}
    if not selected: raise ValueError('缺已拆解的结构信息；原文不是框架')
    return {'inputs':{'brief':{'path':brief,'sha256':digest(facts)},'framework':{'path':framework,'sha256':digest(inside(root,framework,True))}},'messages':[{'role':'system','content':'使用自己的产品事实与账号人设原创表达。参考材料只借用抽象结构，不复制原文、画面、个人经历、虚假证据。输出JSON title/body/tags/cards/segments/sources；缺事实明确标待核对。'},{'role':'user','content':json.dumps({'product_facts':facts.read_text(encoding='utf-8-sig'),'abstract_framework':selected,'account':persona},ensure_ascii=False)}]}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','brief','framework','account','output'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); save(inside(a.root,a.output),remix(a.root,a.brief,a.framework,a.account))
