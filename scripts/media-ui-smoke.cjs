const assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
(async()=>{
 const base=process.argv[2];const html=await(await fetch(base+'/media.html')).text();
 const dom=new JSDOM(html,{url:base,runScripts:'outside-only'});const w=dom.window;
 w.fetch=p=>fetch(new URL(p,base));w.eval(await(await fetch(base+'/media.js')).text());
 for(let i=0;i<100&&!w.document.querySelector('#apps').children.length;i++)await new Promise(r=>setTimeout(r,20));
 assert.equal(w.document.querySelector('#apps').children.length,260);
 assert.equal(w.document.querySelector('#channels').children.length,18);
 const category=w.document.querySelector('#category');category.value='电子商务';category.dispatchEvent(new w.Event('change'));
 assert.equal(w.document.querySelector('#apps').children.length,10);
 const search=w.document.querySelector('#search');search.value='天猫';search.dispatchEvent(new w.Event('input'));
 assert.equal(w.document.querySelector('#apps').children.length,1);
 assert.match(w.document.querySelector('#apps').textContent,/天猫/);
 assert.match(w.document.querySelector('#coverage').textContent,/尚未全量验证/);
 for(const a of w.document.querySelectorAll('#channels a'))assert.ok(/^https?:/.test(a.href));
 console.log('媒体清单UI：7项检查通过（JSDOM，非视觉验收）');
 dom.window.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
