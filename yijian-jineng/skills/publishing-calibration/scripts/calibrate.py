"""Bind a real observation and task to a reviewed publishing profile."""
import argparse,importlib.util,json,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import ledger,read,save,inside,digest,proof,SKILLS
spec=importlib.util.spec_from_file_location('workflow_engine',SKILLS/'publishing-workflow-runner/scripts/engine.py'); engine=importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
def calibrate(root,task_id,profile,observation,reviewer):
    l=ledger(root)
    try:
        task=l.load(task_id); engine.validate(profile,task); obs_path=inside(root,observation,True); obs=read(obs_path)
        if not reviewer or obs.get('schema')!='ui-observation/v1' or obs.get('account_id')!=profile['account_id'] or obs.get('location')!=profile['location'] or obs.get('backend')!=profile['backend']: raise ValueError('观察证据不匹配当前配置或审核者缺失')
        if not obs.get('files'): raise ValueError('观察没有截图/结构证据')
        for f in obs['files']: proof(l.root,f)
        return {**profile,'calibrated':True,'verified_by':reviewer,'verified_at':datetime.now(timezone.utc).isoformat(),'calibration_evidence':[{'path':str(obs_path.relative_to(l.root)),'sha256':digest(obs_path)},*obs['files']]}
    finally: l.db.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','task','profile','observation','reviewer','output'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); save(inside(a.root,a.output),calibrate(a.root,a.task,read(inside(a.root,a.profile,True)),a.observation,a.reviewer))
