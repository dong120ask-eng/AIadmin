"""Render a conservative Markdown subset into escaped, inline-styled article HTML."""
import argparse,html,re,sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import inside,save
def inline(value):
    escaped=html.escape(value)
    escaped=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',escaped)
    def link(match):
        label,url=match.groups(); raw=html.unescape(url); parsed=urlparse(raw)
        if parsed.scheme!='https' or parsed.username or parsed.password: return label+'（链接未纳入排版）'
        return '<a href="'+html.escape(raw,quote=True)+'">'+label+'</a>'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,escaped)
def render(title,body):
    blocks=[]; paragraph=[]
    def flush():
        if paragraph: blocks.append('<p style="margin:16px 0;line-height:1.8">'+inline(' '.join(paragraph))+'</p>'); paragraph.clear()
    for line in body.splitlines():
        heading=re.match(r'^(#{1,3})\s+(.+)$',line)
        if heading: flush(); level=len(heading[1])+1; blocks.append(f'<h{level} style="margin:24px 0 12px;color:#163a5f">'+inline(heading[2])+f'</h{level}>')
        elif re.match(r'^[-*]\s+',line): flush(); blocks.append('<p style="line-height:1.8">• '+inline(line[2:])+'</p>')
        elif line.startswith('> '): flush(); blocks.append('<blockquote style="padding:12px;border-left:3px solid #2868a0;background:#f4f7fa">'+inline(line[2:])+'</blockquote>')
        elif not line.strip(): flush()
        else: paragraph.append(line.strip())
    flush()
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+html.escape(title)+'</title><body><article style="max-width:740px;margin:auto;color:#222;font-size:17px"><h1>'+html.escape(title)+'</h1>'+''.join(blocks)+'</article></body></html>'
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','title','text','output'): p.add_argument('--'+k,required=True)
    a=p.parse_args(); body=inside(a.root,a.text,True).read_text(encoding='utf-8-sig'); save(inside(a.root,a.output),render(a.title,body))
