import {api} from './session.js';

// Filtering happens before grouping, so game scope never displays a source-only snapshot.
export function groupAssets(assets){
  const result=[],groups=new Map();
  for(const a of assets){
    if(!a.versionGroup){result.push(a);continue;}
    // Explicit catalogs and category/search filters may omit a group's primary.
    // Keep actual companion files visible instead of silently dropping them.
    if(a.versionPart){
      if(!assets.some(x=>x.versionGroup===a.versionGroup&&!x.versionPart))result.push(a);
      continue;
    }
    const current=groups.get(a.versionGroup);
    const score=x=>(!x.versionHidden?10:0)+(x.versionSelected?4:0)+(x.location==='game'?1:0);
    if(!current||score(a)>score(current))groups.set(a.versionGroup,a);
  }
  return [...result,...groups.values()];
}

export function createVersions({getData,getSelected,refresh,preview,escape:esc,toast,canLeave}){
  const host=document.createElement('section');host.className='asset-version-controls';host.id='asset-version-controls';
  document.getElementById('asset-subtitle').after(host);
  const dialog=document.createElement('dialog');dialog.id='versions-dialog';dialog.className='versions-dialog';document.body.append(dialog);
  let groupId='',showArchived=false,comparison=new Set(),busy=false;
  const report=()=>getData()?.versions||{groups:[]};
  const group=()=>report().groups.find(g=>g.id===groupId);
  const url=f=>(getData().assetBase||'/asset/current/')+f.path.split('/').map(encodeURIComponent).join('/');
  const visual=(f,label)=>/\.(png|jpe?g|webp|svg)$/i.test(f.path)?`<img src="${esc(url(f))}" alt="${esc(label)}" loading="lazy">`:
    /\.(mp4|webm)$/i.test(f.path)?`<video src="${esc(url(f))}" controls preload="metadata"></video>`:
    /\.(wav|mp3|ogg|flac)$/i.test(f.path)?`<audio src="${esc(url(f))}" controls preload="metadata"></audio>`:`<p class="version-file-type">${esc(f.path.split('.').pop().toUpperCase())} · ${esc(f.role)}</p>`;
  async function write(payload){
    if(busy)return;busy=true;
    try{const result=await api('/api/asset-versions',{revision:report().revision,...payload});await refresh();return result;}
    catch(e){toast(e.message);throw e;}finally{busy=false;}
  }
  function render(){
    const a=getSelected(),g=report().groups.find(g=>g.id===a?.versionGroup);
    if(!a){host.innerHTML='';return;}
    host.innerHTML=report().error?`<p>${esc(report().error)}</p>`:g?
      `<p>${g.versions.length} 个版本 · ${g.selected?'当前选用 V'+g.versions.find(v=>v.id===g.selected)?.number:'尚未选用'} · 正在查看 V${a.versionNumber}</p><button class="button secondary" data-history>版本历史与对比</button>`:
      '<button class="button secondary" data-register-version>加入版本记录</button>';
    host.querySelector('[data-history]')?.addEventListener('click',()=>open(g.id));
    host.querySelector('[data-register-version]')?.addEventListener('click',()=>register(a));
  }
  function close(){dialog.querySelectorAll('audio,video').forEach(x=>x.pause());dialog.close();}
  function shell(title,body){dialog.innerHTML=`<header><h2>${esc(title)}</h2><button class="button secondary" data-close-versions>关闭</button></header>${body}`;dialog.querySelector('[data-close-versions]').onclick=close;}
  async function open(id){if(!await canLeave())return;groupId=id;comparison.clear();showArchived=false;history();if(!dialog.open)dialog.showModal();}
  function history(){
    const g=group();if(!g)return;
    const chosen=g.versions.filter(v=>comparison.has(v.id));
    shell(g.title,`<p>最新版本 V${g.versions.at(-1)?.number||'—'} · ${g.selected?'当前选用 V'+g.versions.find(v=>v.id===g.selected)?.number:'尚未选用'}。选用版本不会替换游戏工程文件。</p>
      <label class="version-check"><input type="checkbox" id="show-archived" ${showArchived?'checked':''}>显示归档版本</label>
      ${chosen.length?'<section class="version-comparison" aria-label="版本对比">'+chosen.map(v=>`<article><h3>V${v.number}</h3>${v.files.map(f=>visual(f,'V'+v.number+' · '+f.role)).join('')}<p>${esc(v.note)}</p></article>`).join('')+'</section>':''}
      <div class="version-list">${g.versions.filter(v=>showArchived||!v.archived).slice().reverse().map(v=>`<article class="version-entry">
        <div class="version-entry-heading"><h3>V${v.number}${g.selected===v.id?' · 当前选用':''}${g.latest===v.id?' · 最新版本':''}${v.archived?' · 已归档':''}</h3><label class="version-check"><input type="checkbox" data-compare="${v.id}" ${comparison.has(v.id)?'checked':''}>对比</label></div>
        ${v.intact?visual(v.files[0],'V'+v.number):'<p role="alert">此版本文件缺失或已变化，无法选用。</p>'}
        <p>${esc(v.note||'未填写修改说明')}</p><small>${esc(new Date(v.createdAt).toLocaleString())}${v.parent?' · 修改自 V'+g.versions.find(p=>p.id===v.parent)?.number:' · 独立方案'}</small>
        ${v.references.map(r=>{const rg=report().groups.find(x=>x.id===r.group),rv=rg?.versions.find(x=>x.id===r.version);return `<p class="version-reference">${esc(r.role)}：${esc(rg?.title||r.group)} · V${rv?.number||'?'}</p>`;}).join('')}
        ${v.warnings.map(w=>`<p class="version-warning">${esc(w)}</p>`).join('')}
        ${v.gameFiles.length?`<p>工程目录包含该版文件：${v.gameFiles.map(esc).join('、')}（运行效果另行验证）</p>`:''}
        <details><summary>文件、来源与选用记录</summary>${v.files.map(f=>`<p>${esc(f.role)} · <a href="${esc(url(f))}" target="_blank" rel="noopener">${esc(f.sourcePath)}</a></p>`).join('')}<pre>${esc(JSON.stringify(v.provenance,null,2))}</pre>${g.decisions.filter(d=>d.to===v.id).map(d=>`<p>${esc(d.at)} · ${esc(d.reason)}</p>`).join('')}</details>
        <div class="version-actions"><button class="button secondary" data-preview-version="${v.id}" ${!v.intact?'disabled':''}>查看版本</button><button class="button primary" data-select-version="${v.id}" ${!v.intact||g.selected===v.id?'disabled':''}>选用此版</button><button class="button secondary" data-edit-version="${v.id}" ${!v.intact?'disabled':''}>从此版继续修改</button><button class="button secondary" data-archive-version="${v.id}" ${g.selected===v.id?'disabled':''}>${v.archived?'取消归档':'归档'}</button></div>
      </article>`).join('')}</div>`);
    dialog.querySelector('#show-archived').onchange=e=>{showArchived=e.target.checked;history();};
    dialog.querySelectorAll('[data-compare]').forEach(el=>el.onchange=()=>{if(el.checked&&comparison.size>=2){el.checked=false;toast('每次选择两个版本对比');return;}el.checked?comparison.add(el.dataset.compare):comparison.delete(el.dataset.compare);history();if(comparison.size===2)dialog.scrollTop=0;});
    dialog.querySelectorAll('[data-preview-version]').forEach(b=>b.onclick=async()=>{const v=g.versions.find(x=>x.id===b.dataset.previewVersion);close();await preview(v.files[0].path);});
    dialog.querySelectorAll('[data-select-version]').forEach(b=>b.onclick=async()=>{try{await write({action:'select',group:g.id,version:b.dataset.selectVersion,reason:'用户在资产库选择此版作为当前制作依据'});history();render();toast('已更新当前选用版本');}catch{}});
    dialog.querySelectorAll('[data-archive-version]').forEach(b=>b.onclick=async()=>{const v=g.versions.find(x=>x.id===b.dataset.archiveVersion);try{await write({action:'archive',group:g.id,version:v.id,archived:!v.archived});comparison.delete(v.id);history();}catch{}});
    dialog.querySelectorAll('[data-edit-version]').forEach(b=>b.onclick=()=>{close();window.dispatchEvent(new CustomEvent('workbench:revise-asset',{detail:{group:g.id,parent:b.dataset.editVersion}}));});
  }
  function register(a){
    const groups=report().groups.filter(g=>g.kind===a.kind);
    shell('保存资产版本',`<form id="version-register-form"><label>归入资产<select id="version-target"><option value="">新建版本组</option>${groups.map(g=>`<option value="${g.id}">${esc(g.title)}</option>`).join('')}</select></label>
      <label>资产名称<input id="version-title" required maxlength="100" value="${esc(a.title)}"></label>
      <label>修改底稿<select id="version-parent"><option value="">独立方案</option></select></label>
      <label>本次说明<textarea id="version-note" placeholder="例如：保留造型，调整盔甲比例"></textarea></label>
      <details><summary>配套文件（多视图、贴图等）</summary><div class="version-file-options">${getData().assets.filter(x=>x.path!==a.path&&!x.versionGroup&&!x.previewCopy).map(x=>`<label class="version-check"><input type="checkbox" name="companion" value="${esc(x.path)}">${esc(x.title)}</label>`).join('')}</div></details>
      <p>保存实际文件的独立副本；新版本保留为候选。</p><button class="button primary" type="submit">保存版本</button><p id="version-register-error" role="alert"></p></form>`);
    dialog.querySelector('#version-target').onchange=e=>{const g=groups.find(g=>g.id===e.target.value);dialog.querySelector('#version-title').disabled=!!g;dialog.querySelector('#version-parent').innerHTML='<option value="">独立方案</option>'+(g?.versions||[]).map(v=>`<option value="${v.id}" ${v.id===g.selected?'selected':''}>V${v.number} · ${esc(v.note)}</option>`).join('');};
    dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();const target=dialog.querySelector('#version-target').value;
      const files=[a,...Array.from(dialog.querySelectorAll('[name=companion]:checked')).map(x=>getData().assets.find(a=>a.path===x.value))].map((x,i)=>({path:x.path,sha256:x.classification?.version,role:i?'配套文件':'主文件'}));
      try{const result=await write({action:target?'add':'create',group:target,title:dialog.querySelector('#version-title').value,kind:a.kind,files,parent:dialog.querySelector('#version-parent').value||null,note:dialog.querySelector('#version-note').value,provenance:{method:'project-file',source:a.source||'',license:a.license||''}});groupId=result.group;history();toast('版本已保存');}catch(error){dialog.querySelector('#version-register-error').textContent=error.message;}
    };
    dialog.showModal();
  }
  dialog.addEventListener('close',()=>dialog.querySelectorAll('audio,video').forEach(x=>x.pause()));
  return {render,open};
}
