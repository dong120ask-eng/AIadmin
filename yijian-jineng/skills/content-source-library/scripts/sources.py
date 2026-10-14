"""Import provided text, HTML or RSS with provenance and a recoverable content hash."""
import argparse,hashlib,json,sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import inside,read,save,digest,instant
class Text(HTMLParser):
    def __init__(self): super().__init__(); self.hidden=0; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript'): self.hidden+=1
        if tag in ('p','div','br','h1','h2','li'): self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'): self.hidden=max(0,self.hidden-1)
    def handle_data(self,text):
        if not self.hidden: self.parts.append(text)
def ingest(root,file,metadata):
    path=inside(root,file,True); meta=read(inside(root,metadata,True)); instant(meta['collected_at'])
    if meta.get('access') not in ('public','authorized') or not meta.get('source_url'): raise ValueError('需公开/授权来源与真实来源链接')
    u=urlparse(meta['source_url'])
    if u.scheme!='https' or u.username or u.password or u.query and any(k in u.query.lower() for k in ('token=','password=','cookie=')): raise ValueError('来源链接需HTTPS且不得携带凭据')
    raw=path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() in ('.html','.htm'):
        parser=Text(); parser.feed(raw); body=''.join(parser.parts).strip()
    elif path.suffix.lower() in ('.xml','.rss'):
        if '<!DOCTYPE' in raw.upper() or '<!ENTITY' in raw.upper(): raise ValueError('不接受XML实体声明')
        tree=ET.fromstring(raw); entries=[]
        for node in tree.iter():
            if node.tag.split('}')[-1] in ('item','entry'):
                values={child.tag.split('}')[-1]:''.join(child.itertext()).strip() for child in node}
                entries.append(values)
        body=json.dumps(entries,ensure_ascii=False,indent=2)
    else: body=raw.strip()
    if not body: raise ValueError('没有可入库正文')
    fp=hashlib.sha256(body.encode('utf-8')).hexdigest(); folder=inside(root,'library/sources/'+fp)
    if folder.exists():
        if digest(folder/'body.md')!=fp: raise ValueError('已入库正文改变')
        origin_id=hashlib.sha256((digest(path)+json.dumps(meta,sort_keys=True,ensure_ascii=False)).encode()).hexdigest()
        origin=folder/'origins'/(origin_id+'.json')
        if not origin.exists(): save(origin,{'source_file_sha256':digest(path),'metadata':meta})
        return {'id':fp,'state':'existing','path':str(folder.relative_to(Path(root).resolve()))}
    save(folder/'body.md',body); save(folder/'source.json',{'id':fp,'source_file_sha256':digest(path),'metadata':meta,'body_sha256':fp,'status':'source-recorded-not-automatically-verified-popularity'})
    return {'id':fp,'path':str(folder.relative_to(Path(root).resolve()))}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','file','metadata'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); print(json.dumps(ingest(a.root,a.file,a.metadata),ensure_ascii=False))
