const assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
(async()=>{
 const base=process.argv[2];const dom=new JSDOM(await(await fetch(base+'/dispatch.html')).text(),{url:base,runScripts:'outside-only'});const w=dom.window;
 w.fetch=p=>fetch(new URL(p,base));w.eval(await(await fetch(base+'/dispatch.js')).text());
 const until=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,20));}throw new Error('condition timed out');};
 await until(()=>w.document.querySelectorAll('#tasks section').length===2);
 assert.match(w.document.querySelector('#tasks').textContent,/尚未接通/);
 assert.match(w.document.querySelector('#tasks').textContent,/页面检查/);
 assert.match(w.document.querySelector('#tasks').textContent,/没有发布成功证据/);
 assert.equal(w.document.querySelector('#tasks img'),null);
 w.document.querySelector('#tenant').value='other';w.document.querySelector('#refresh').click();
 await until(()=>w.document.querySelector('#tasks').textContent.includes('尚无队列任务'));
 assert.equal(w.document.querySelectorAll('#tasks section').length,0);
 console.log('账号队列UI：6项检查通过（JSDOM，非视觉验收）');dom.window.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
