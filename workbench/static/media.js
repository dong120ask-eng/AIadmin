'use strict';
let catalog;
const formLabels={article:'文章',image_text:'图文／动态',short_video:'短视频',long_video:'长视频',audio:'音频',novel:'小说',music:'音乐',short_drama:'短剧'};
function text(tag, value) { const e = document.createElement(tag); e.textContent = value; return e; }
function source(url) { const a = text('a', '来源'); const u = new URL(url); if (u.protocol === 'https:' || u.protocol === 'http:') { a.href = u.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; } return a; }
function render() {
  const category = document.querySelector('#category').value;
  const q = document.querySelector('#search').value.toLocaleLowerCase();
  const rows = catalog.applications.filter(x => (!category || category === x.category) && x.name.toLocaleLowerCase().includes(q));
  const target = document.querySelector('#apps'); target.replaceChildren();
  document.querySelector('#count').textContent = `当前显示 ${rows.length} 项；应用发布能力均待专项核查。`;
  for (const row of rows) { const p = text('p', `${row.name} · ${row.category} · 待核查／未接入 `); if (row.source_url) p.append(source(row.source_url)); target.append(p); }
}
fetch('/api/media-index').then(r => {if(!r.ok) throw new Error('清单读取失败');return r.json();}).then(data => {
  catalog = data;
  document.querySelector('#coverage').textContent = `已查看 ${data.coverage.primary_categories} 个一级分类，记录 ${data.coverage.observed_applications} 个榜单应用，另补 ${data.coverage.requested_additions} 个指定渠道。二级榜单、全部应用、发布能力和自动化尚未全量验证。`;
  const select = document.querySelector('#category');
  for(const c of [...data.categories.map(x=>x.name),'用户指定补查']) { const opt = text('option', c); opt.value = c; select.append(opt); }
  for(const c of data.channels) { const p = text('p', `${c.name}｜资料支持形式：${c.forms.map(x=>formLabels[x]||x).join('、') || '待核查'}｜${c.route_priority==='web_first_candidate'?'网页优先候选，编辑器待核查':'操作入口待核查'}｜未接入。${c.notes} `);for(const u of c.evidence_urls) p.append(source(u), document.createTextNode(' '));document.querySelector('#channels').append(p); }
  select.addEventListener('change', render); document.querySelector('#search').addEventListener('input', render); render();
}).catch(e=>{document.querySelector('#error').textContent=e.message;});
