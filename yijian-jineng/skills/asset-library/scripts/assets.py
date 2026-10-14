"""Content-addressed media catalog with provenance, rights and account use records."""
import argparse,json,shutil,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import inside,read,digest,instant
class Assets:
    def __init__(self,root):
        self.root=Path(root).resolve(); (self.root/'state').mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.root/'state/assets.sqlite'); self.db.row_factory=sqlite3.Row
        self.db.executescript('CREATE TABLE IF NOT EXISTS assets(sha TEXT PRIMARY KEY, path TEXT, metadata TEXT); CREATE TABLE IF NOT EXISTS uses(sha TEXT, account TEXT, task TEXT, PRIMARY KEY(sha,account,task));')
    def ingest(self,file,metadata):
        p=inside(self.root,file,True); fp=digest(p)
        if metadata.get('rights') not in ('owned','licensed','public-domain') or not metadata.get('source'): raise ValueError('需明确素材来源与使用权')
        old=self.db.execute('SELECT * FROM assets WHERE sha=?',(fp,)).fetchone()
        if old:
            existing=inside(self.root,old['path'],True)
            if digest(existing)!=fp: raise ValueError('库中素材被修改')
            if json.loads(old['metadata'])!=metadata: raise ValueError('相同素材的来源/权利登记不同，先人工核对，不静默替换')
            return dict(old)
        dest=inside(self.root,'library/media/'+fp+p.suffix.lower()); dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and digest(dest)!=fp: raise ValueError('内容地址冲突')
        if not dest.exists(): shutil.copy2(p,dest)
        with self.db: self.db.execute('INSERT INTO assets VALUES(?,?,?)',(fp,str(dest.relative_to(self.root)),json.dumps(metadata,ensure_ascii=False)))
        return {'sha':fp,'path':str(dest.relative_to(self.root))}
    def use(self,sha,account,task,allow_reuse=False):
        row=self.db.execute('SELECT path FROM assets WHERE sha=?',(sha,)).fetchone()
        if not row or digest(inside(self.root,row['path'],True))!=sha: raise ValueError('素材缺失或改变')
        previous=self.db.execute('SELECT account FROM uses WHERE sha=?',(sha,)).fetchall()
        if previous and any(r[0]!=account for r in previous) and not allow_reuse: raise ValueError('跨账号复用需明确allow-reuse及权利核对')
        with self.db: self.db.execute('INSERT OR IGNORE INTO uses VALUES(?,?,?)',(sha,account,task))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',required=True); s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('ingest'); q.add_argument('--file',required=True); q.add_argument('--metadata',required=True)
    q=s.add_parser('use'); q.add_argument('--sha',required=True); q.add_argument('--account',required=True); q.add_argument('--task',required=True); q.add_argument('--allow-reuse',action='store_true')
    a=p.parse_args(); c=Assets(a.root)
    try:
        if a.action=='ingest': print(json.dumps(c.ingest(a.file,read(inside(c.root,a.metadata,True))),ensure_ascii=False))
        else: c.use(a.sha,a.account,a.task,a.allow_reuse); print('usage recorded')
    finally: c.db.close()
