"""Compatible chat client with explicit provider, token reservations and limited 429 retry."""
import argparse,json,os,sqlite3,sys,time,urllib.error,urllib.request,uuid
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'selfmedia-autopilot/scripts'))
from runtime import read,save,inside
class Budget:
    def __init__(self,root):
        path=Path(root)/'state'; path.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path/'model-budget.sqlite',timeout=10)
        self.db.execute('CREATE TABLE IF NOT EXISTS budget(provider TEXT, day TEXT, calls INTEGER, reserved INTEGER, PRIMARY KEY(provider,day))')
    def reserve(self,provider,tokens,limits):
        day=datetime.now(timezone.utc).date().isoformat()
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row=self.db.execute('SELECT calls,reserved FROM budget WHERE provider=? AND day=?',(provider,day)).fetchone() or (0,0)
            if row[0]+1>limits['daily_call_limit'] or row[1]+tokens>limits['daily_token_budget']: raise ValueError('模型每日调用/令牌预算已到上限')
            self.db.execute('INSERT OR REPLACE INTO budget VALUES(?,?,?,?)',(provider,day,row[0]+1,row[1]+tokens))
class Client:
    def __init__(self,root,profile,provider='selected',opener=None,sleeper=None):
        self.root=Path(root); self.profile=profile; self.provider=provider
        self.open=opener or urllib.request.urlopen; self.sleep=sleeper or time.sleep
    def chat(self,messages):
        p=self.profile; u=urlparse(p['base_url'])
        if u.username or u.password or u.query or u.fragment or (u.scheme!='https' and not (u.scheme=='http' and u.hostname in ('localhost','127.0.0.1','::1'))): raise ValueError('仅HTTPS或显式本机端点，无嵌入凭据')
        key=os.environ.get(p['api_key_env']); model=p.get('model')
        if not key or not model: raise ValueError('缺真实模型与API环境变量，客户端登录不能代替API配置')
        if not isinstance(messages,list) or not messages or any(not isinstance(m,dict) or m.get('role') not in ('system','user','assistant') or not isinstance(m.get('content'),str) for m in messages): raise ValueError('消息格式无效')
        for field in ('daily_call_limit','daily_token_budget','max_output_tokens'):
            if isinstance(p.get(field),bool) or not isinstance(p.get(field),int) or p[field]<1: raise ValueError('需配置正整数 '+field)
        retries=p.get('retry_429',2)
        if isinstance(retries,bool) or not isinstance(retries,int) or not 0<=retries<=3: raise ValueError('429重试次数需0到3')
        raw=json.dumps(messages,ensure_ascii=False).encode('utf-8')
        if len(raw)>p.get('max_input_bytes',60000): raise ValueError('输入超过明确配置的限制')
        token_field=p.get('output_token_parameter','max_tokens')
        if token_field not in ('max_tokens','max_completion_tokens'): raise ValueError('输出令牌字段无效')
        payload={'model':model,'messages':messages,token_field:p['max_output_tokens'],'stream':False}
        request_id=uuid.uuid4().hex; b=Budget(self.root)
        try:
            for attempt in range(retries+1):
                b.reserve(self.provider,len(raw)+p['max_output_tokens']+400,p)
                request=urllib.request.Request(p['base_url'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','X-Request-ID':request_id})
                try:
                    with self.open(request,timeout=120) as response: envelope=json.load(response)
                    text=envelope['choices'][0]['message']['content']
                    if not isinstance(text,str) or not text.strip(): raise ValueError('模型返回空内容')
                    return {'content':text,'usage':envelope.get('usage'),'request_id':request_id,'model':model,'provider':self.provider,'attempts':attempt+1}
                except urllib.error.HTTPError as error:
                    if error.code==429 and attempt<retries:
                        delay=error.headers.get('Retry-After','') if error.headers else ''
                        self.sleep(min(30,max(1,int(delay))) if delay.isdigit() else min(30,2**attempt)); continue
                    raise RuntimeError('模型HTTP错误 '+str(error.code)+'；未输出响应或凭据') from None
                except (TimeoutError,urllib.error.URLError):
                    raise RuntimeError('连接结果不明，不自动重试；预算预留保留，请检查后再运行') from None
        finally: b.db.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('root','profiles','provider','messages','output'): p.add_argument('--'+k,required=True)
    p.add_argument('--apply',action='store_true'); a=p.parse_args(); profile=read(inside(a.root,a.profiles,True))['providers'][a.provider]; messages=read(inside(a.root,a.messages,True))
    if not a.apply: print(json.dumps({'provider':a.provider,'model':profile.get('model'),'messages':len(messages),'mode':'plan'},ensure_ascii=False))
    else: save(inside(a.root,a.output),Client(a.root,profile,a.provider).chat(messages))
