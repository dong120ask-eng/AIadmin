"""Shared contracts for local skill execution; no credentials or external calls."""
import importlib.util,json,math
from datetime import datetime
from pathlib import Path
from common import inside,read,save,digest
SKILLS=Path(__file__).resolve().parents[2]
def ledger(root):
    spec=importlib.util.spec_from_file_location('selfmedia_ledger',SKILLS/'dsh-selfmedia-hub/scripts/ops.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.Ledger(root)
def instant(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None: raise ValueError('时间必须带时区')
    return parsed
def finite(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0: raise ValueError('指标必须是非负有限数')
    return value
def proof(root,record):
    if not isinstance(record,dict) or not record.get('path') or not record.get('sha256'): raise ValueError('缺带指纹的证据')
    if digest(inside(root,record['path'],True))!=record['sha256']: raise ValueError('证据指纹不一致')
    return record
