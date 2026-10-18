'use strict';
const states={queued:'等待设备',blocked:'尚未接通',running:'正在执行',unknown:'结果未知，设备隔离',inspected:'页面检查完成',cancelled:'核查后已取消'};
const actions={inspect_only:'页面检查',draft:'保存草稿',publish:'发布内容'};
function text(tag,value){const e=document.createElement(tag);e.textContent=value;return e;}
async function render(){
 const error=document.querySelector('#error');error.textContent='';
 try{
  const response=await fetch('/api/dispatch?tenant='+encodeURIComponent(document.querySelector('#tenant').value));
  const rows=await response.json();if(!response.ok)throw new Error(rows.error||'读取失败');
  const list=document.querySelector('#tasks');list.replaceChildren();
  if(!rows.length){list.append(text('p','尚无队列任务。请先在本机终端录入账号执行配置。'));return;}
  for(const row of rows){const section=document.createElement('section');const binding=row.payload.binding;
   section.append(text('h2',actions[row.action]||row.action),text('p',`账号：${binding.account_id} · ${states[row.state]||row.state}`));
   section.append(text('p','设备／会话：'+row.resource),text('p','没有发布成功证据'));
   if(row.state==='blocked'){for(const reason of row.payload.plan.blockers)section.append(text('p',reason));}
   list.append(section);
  }
 }catch(e){error.textContent=e.message;}
}
document.querySelector('#refresh').addEventListener('click',render);render();
