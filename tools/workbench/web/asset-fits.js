const $=id=>document.getElementById(id);
const roles={player:'主角',boss:'Boss',shared:'共享',unassigned:'其他'};
const availability={observed:'已观察',claimed:'来源说明，待验证',missing:'缺失',unknown:'未确认'};
const coverage={supported:'已覆盖',partial:'部分覆盖',missing:'缺失',unknown:'未确认'};
const previewTypes={motion:'动态预览',image:'静态图片',native:'原生播放',audio:'音频试听',none:'无预览'};

export function createAssetFits({getLibraryData,escape:esc,toast,preview}){
  const dialog=document.createElement('dialog');
  dialog.id='asset-fit-dialog';dialog.className='asset-fit-dialog';
  dialog.setAttribute('aria-labelledby','asset-fit-title');document.body.append(dialog);
  let selected=null;
  const note=f=>`${f.location==='game'?'游戏应用':'候补素材'} · ${f.status==='stale'?'来源已变化，需复核':'当前版本'} · ${f.gaps.length} 个待满足项`;
  function frame(title,body){
    dialog.innerHTML=`<header><h2 id="asset-fit-title">${esc(title)}</h2><button class="button secondary" data-fit-close>关闭</button></header>${body}`;
    dialog.querySelector('[data-fit-close]').onclick=()=>dialog.close();
  }
  function showList(){
    selected=null;const data=getLibraryData()||{},fits=data.fits||[];
    frame('素材方案',`<p class="fit-note">查看素材组合的实际能力、目标覆盖与缺口。方案可以先于下载建立，进入游戏目录不代表品质通过。</p>${(data.fit_errors||[]).map(e=>`<p class="fit-warning">${esc(e.path)}：${esc(e.error)}</p>`).join('')}<div class="fit-list">${fits.map(f=>`<button data-fit="${esc(f.id)}"><strong>${esc(f.spec.title)}</strong><span>${esc(f.spec.object)} · ${esc(roles[f.spec.role]||f.spec.role)}</span><span>${esc(note(f))}</span></button>`).join('')||'<p class="fit-note">尚未记录素材方案。与 Agent 确定组合后，可在这里查看能力与缺口。</p>'}</div>`);
    dialog.querySelectorAll('[data-fit]').forEach(b=>b.onclick=()=>showFit(b.dataset.fit));
  }
  function showFit(id){
    const data=getLibraryData()||{},f=(data.fits||[]).find(x=>x.id===id);
    if(!f){showList();return;}
    selected=id;const s=f.spec,files=new Set((data.assets||[]).map(a=>a.path));
    frame(s.title,`<button class="button secondary fit-back" data-fit-back>返回方案列表</button><p>${esc(s.object)} / ${esc(roles[s.role]||s.role)} · ${esc(s.use)}</p><p class="${f.status==='stale'?'fit-warning':'fit-note'}">${esc(note(f))}。游戏目录归属不代表品质通过。</p><p>原目标：${esc(s.goal_ref)}</p><h3>选材与实际能力</h3>${s.members.map(m=>`<section class="fit-member"><p><strong>${esc(m.id)}</strong> · ${esc(m.path||'尚未下载')}</p>${m.capabilities.map(c=>`<p>${esc(c.label)}：${esc(availability[c.availability]||c.availability)} / ${esc(previewTypes[c.preview_type]||c.preview_type)}<br><span class="fit-note">${esc(c.conditions)}</span></p>`).join('')}${files.has(m.path)?`<button class="button secondary" data-fit-preview="${esc(m.path)}">在资产库预览</button>`:''}</section>`).join('')}<h3>目标覆盖与缺口</h3><table><thead><tr><th>需求</th><th>覆盖情况</th><th>说明</th></tr></thead><tbody>${s.requirements.map(r=>`<tr><td>${esc(r.description)}</td><td>${esc(coverage[r.coverage]||r.coverage)}</td><td>${esc(r.notes)}</td></tr>`).join('')}</tbody></table><h3>组合取舍</h3>${(s.tradeoffs||[]).map(t=>`<p>${esc(t)}</p>`).join('')||'<p class="fit-note">未记录</p>'}<h3>原始来源</h3>${s.sources.map(o=>`<p>${/^https:\/\//i.test(o.url)?`<a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">${esc(o.title)}</a>`:esc(o.title)} · ${esc(o.version)} · ${esc(o.price)} · ${esc(o.license)}</p>`).join('')}`);
    dialog.querySelector('[data-fit-back]').onclick=showList;
    dialog.querySelectorAll('[data-fit-preview]').forEach(b=>b.onclick=async()=>{
      dialog.close();
      try{await preview(b.dataset.fitPreview);}catch(e){toast(e.message);}
    });
  }
  function refresh(){
    const data=getLibraryData()||{};
    $('asset-fit-count').textContent=(data.fits||[]).length;
    const warning=$('character-binding-warning');
    warning.textContent=data.characterBindingError||'';warning.hidden=!data.characterBindingError;
    if(dialog.open)selected?showFit(selected):showList();
  }
  $('asset-fits').onclick=()=>{showList();dialog.showModal();};
  refresh();
  return {refresh};
}
