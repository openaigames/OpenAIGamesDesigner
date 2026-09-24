import {api} from './session.js';
export function createTagManager({getData,getSelected,getFiltered,onChange,onSelect,refresh,escape:esc,toast}) {
  let active=null,busy=false;
  const nav=document.getElementById('tag-navigation'),editor=document.getElementById('asset-tag-editor'),filter=document.getElementById('active-tag-filter');
  const dialog=document.createElement('dialog');dialog.id='art-work-dialog';dialog.className='art-source-dialog';document.body.append(dialog);
  const summary=document.createElement('div');summary.className='art-audit-summary';document.querySelector('.library-caption').after(summary);
  const status=a=>a.art?.state||'unregistered';
  const labels={unregistered:'未登记',incomplete:'待补齐','version-changed':'版本变化'};
  const matches=a=>!active||(active.type==='tag'?a.tags.includes(active.value):status(a)===active.value);
  const splitTags=value=>[...new Set(value.split(/[,，、\n]/).map(t=>t.trim()).filter(Boolean))];
  const heading=title=>`<div class="dialog-heading"><h2>${esc(title)}</h2><button type="button" data-close aria-label="关闭美术记录">×</button></div>`;
  const errors=()=>'<p class="art-form-error" role="alert"></p>';
  function choose(type,value){
    active=active?.type===type&&active?.value===value?null:{type,value};onChange();
    if(getSelected()&&!matches(getSelected())&&getFiltered()[0])onSelect(getFiltered()[0].path);
  }
  function renderNav(){
    const data=getData(),counts=new Map();
    for(const a of data?.assets||[])for(const tag of new Set(a.tags))counts.set(tag,(counts.get(tag)||0)+1);
    nav.innerHTML=[...counts].sort(([a],[b])=>a==='主角'?-1:b==='主角'?1:a.localeCompare(b,'zh')).map(([tag,count])=>`<button class="side-item tag-filter ${active?.type==='tag'&&active.value===tag?'active':''}" data-tag="${esc(tag)}" aria-pressed="${active?.type==='tag'&&active.value===tag}" aria-label="筛选标签 ${esc(tag)}"><span class="tag-symbol">#</span><span class="tag-name">${esc(tag)}</span><span class="count">${count}</span></button>`).join('')||'<p class="tag-empty">美术记录中暂无标签</p>';
    const audit=data?.artAudit,c=audit?.counts||{};
    nav.innerHTML+='<div class="tag-origin-heading">记录检查</div>'+Object.entries(labels).map(([key,label])=>{
      const count=key==='version-changed'?c.changedFiles:c[key];
      return `<button class="side-item ${active?.type==='audit'&&active.value===key?'active':''}" data-audit="${key}" aria-pressed="${active?.type==='audit'&&active.value===key}"><span class="tag-name">${label}</span><span class="count">${count||0}</span></button>`;
    }).join('');
    filter.hidden=!active;filter.textContent=active?(active.type==='tag'?'标签：'+active.value:labels[active.value])+' ×':'';
    filter.setAttribute('aria-label','清除标签或记录筛选');
    summary.innerHTML=audit?.error?`<span class="art-record-warning">美术记录无法读取</span><button data-check>查看原因</button>`:`<span>Art Direction · 已登记 ${(audit?.totalFiles||0)-(c.unregistered||0)} / ${audit?.totalFiles||0}</span>`+[['unregistered','未登记'],['incomplete','待补齐'],['changedFiles','版本变化'],['missingFiles','文件丢失']].filter(([key])=>c[key]).map(([key,label])=>`<button data-summary="${key}">${label} ${c[key]}</button>`).join('');
  }
  function renderEditor(){
    const a=getSelected();if(!a){editor.innerHTML='';return;}
    const art=a.art;
    editor.innerHTML=`<div class="tag-editor-heading"><strong>标签</strong><span>来自 Art Direction</span></div><div class="editable-tags inherited-tags">${a.tags.map(tag=>`<button type="button" data-tag="${esc(tag)}">${esc(tag)}</button>`).join('')||'<span class="tag-empty">尚未确定归属</span>'}</div>`+
      (art?`<p class="art-record-state">${esc(art.id)}${art.object?' · '+esc(art.object):''}</p><p class="art-record-state">${esc(art.stage)}</p>`:'<p class="art-record-warning">这个文件尚未记入 Art Direction。</p>')+
      (art?.state==='incomplete'?`<p class="art-record-warning">待补齐：${esc(art.missingFields.join('、'))}</p>`:art?.state==='version-changed'?'<p class="art-record-warning">文件内容与登记版本不同，请核对后更新 Art Direction。</p>':'')+
      `<div class="art-editor-actions"><button type="button" class="button secondary" data-edit-record>${art?.state==='linked'?'编辑美术归属':'补齐美术记录'}</button>${art?.objectId?'<button type="button" class="text-button" data-edit-object>修改对象标签</button>':''}<button type="button" class="text-button" data-view-source>查看 Art Direction ↗</button></div>`;
  }
  function setBusy(value){busy=value;dialog.querySelectorAll('button,input,select').forEach(el=>el.disabled=value);}
  async function mutate(route,payload){
    setBusy(true);const error=dialog.querySelector('.art-form-error');if(error)error.textContent='';
    try{
      const data=getData(),result=await api(route,{project:data.projectKey,revision:data.artRevision,...payload});
      const lookup=new Map(result.assets.map(a=>[a.path,a]));
      for(const a of data.assets){const next=lookup.get(a.path);if(next){a.art=next.art;a.tags=next.tags;}}
      for(const key of ['artAudit','artObjects','artRevision'])data[key]=result[key];
      if(active&&!data.assets.some(matches))active=null;
      onChange();renderEditor();toast('已更新 Art Direction');return true;
    }catch(e){if(error)error.textContent=e.message;toast(e.message);return false;}finally{setBusy(false);}
  }
  function auditSection(title,items){
    return `<section class="audit-issue-group"><h3>${title}<span>${items.length}</span></h3>${items.length?items.map(a=>`<div class="audit-issue"><strong>${esc(a.title)}</strong><code>${esc(a.path)}</code>${a.missingFields?`<small>缺少 ${esc(a.missingFields.join('、'))}</small>`:''}</div>`).join(''):'<p class="tag-empty">没有此类问题</p>'}</section>`;
  }
  function renderAudit(){
    const a=getData().artAudit;
    dialog.innerHTML=heading('美术清单检查')+`<p>对照项目目录和 Art Direction，检查资产是否登记、归属是否完整。</p>`+(a.error?`<p class="art-record-warning">${esc(a.error)}。修复文档后刷新目录。</p>`:'')+
      `<div class="audit-issue-grid">${auditSection('未登记文件',a.unregistered)}${auditSection('记录待补齐',a.incomplete)}${auditSection('登记文件丢失',a.missingFiles)}${auditSection('文件版本变化',a.changedFiles)}</div><p>补登记只记录文件、类型、来源和版本。用途不明确的资产保留为待补齐，采用、导入与验收状态另行确认。</p>${errors()}<div class="art-editor-actions">${a.canInitialize?'<button class="button primary" data-initialize-art>建立资产记录区</button>':''}${!a.error&&a.unregistered.length?`<button class="button primary" data-register-missing>补登记 ${a.unregistered.length} 个文件</button>`:''}${a.incomplete.length?'<button class="button secondary" data-review-incomplete>查看待补齐资产</button>':''}<button class="text-button" data-view-source>查看 Art Direction ↗</button></div>`;
  }
  async function showAudit(){await refresh();renderAudit();if(!dialog.open)dialog.showModal();}
  function openRecord(editObject=false){
    const a=getSelected();if(!a)return;
    const objects=getData().artObjects||[],current=objects.find(o=>o.id===a.art?.objectId),count=current?getData().assets.filter(x=>x.art?.objectId===current.id).length:0;
    dialog.innerHTML=heading(editObject?'修改对象标签':'补齐美术归属')+`<p>${esc(a.title)}<br><code>${esc(a.path)}</code></p><form id="art-record-form" data-path="${esc(a.path)}" data-edit-object="${editObject}">`+
      (editObject?`<input type="hidden" id="art-object-choice" value="${esc(current.id)}"><p>这组标签用于「${esc(current.label)}」的所有关联资产，当前共 ${count} 个文件。</p>`:`<label for="art-object-choice">所属对象</label><select id="art-object-choice" required><option value="">选择 Art Direction 中的对象</option>${objects.map(o=>`<option value="${esc(o.id)}" ${current?.id===o.id?'selected':''}>${esc(o.label)} · ${esc(o.tags.join(' / '))}</option>`).join('')}<option value="__new__">新建对象与用途…</option></select>`)+
      `<div id="art-object-fields" ${editObject?'':'hidden'}><label for="art-object-label">对象 / 用途</label><input id="art-object-label" maxlength="64" value="${editObject?esc(current.label):''}" placeholder="例如：玩家角色"><label for="art-object-tags">对象标签</label><input id="art-object-tags" maxlength="500" value="${editObject?esc(current.tags.join('、')):''}" placeholder="例如：主角、角色"><p class="art-record-state">用逗号或顿号分隔。关联到此对象的资产共享这些标签。</p></div>${errors()}<div class="art-editor-actions"><button class="button primary" type="submit">保存到 Art Direction</button><button class="button secondary" type="button" data-close>取消</button></div></form>`;
    const select=dialog.querySelector('#art-object-choice'),fields=dialog.querySelector('#art-object-fields');
    const toggle=()=>{fields.hidden=!editObject&&select.value!=='__new__';fields.querySelectorAll('input').forEach(i=>i.required=!fields.hidden);};select.onchange=toggle;toggle();
    if(!dialog.open)dialog.showModal();
  }
  function renderDocument(text){
    const container=document.createElement('div');container.className='art-document';
    const lines=text.split(/\r?\n/);let table=null;
    for(const line of lines){
      if(/^<!--/.test(line)||!line.trim()){table=null;continue;}
      if(line.startsWith('|')){
        const cells=line.slice(1,-1).split('|').map(c=>c.trim());if(cells.every(c=>/^:?-+:?$/.test(c)))continue;
        if(!table){const wrap=document.createElement('div');wrap.className='art-table-wrap';table=document.createElement('table');wrap.append(table);container.append(wrap);}
        const row=table.insertRow();for(const value of cells){const cell=row.insertCell();const decoder=document.createElement('textarea');decoder.innerHTML=value.replace(/</g,'&lt;');cell.textContent=decoder.value;}continue;
      }
      table=null;const match=line.match(/^(#{1,6}) (.*)/),el=document.createElement(match?'h'+Math.min(match[1].length+1,6):'p');el.textContent=match?match[2]:line;container.append(el);
    }
    return container;
  }
  async function showSource(){
    dialog.innerHTML=heading('Art Direction')+'<p>正在读取…</p>';if(!dialog.open)dialog.showModal();
    try{const response=await fetch('/api/art-source?project='+encodeURIComponent(getData().projectKey));if(!response.ok)throw Error('美术记录无法读取');const source=await response.json();dialog.innerHTML=heading('Art Direction')+`<p class="art-source-path">${esc(source.path)}</p>`;dialog.append(renderDocument(source.text));}catch(e){dialog.innerHTML=heading('Art Direction')+`<p class="art-record-warning">${esc(e.message)}</p>`;}
  }
  nav.onclick=e=>{const tag=e.target.closest('[data-tag]'),audit=e.target.closest('[data-audit]');if(tag)choose('tag',tag.dataset.tag);else if(audit)choose('audit',audit.dataset.audit);};
  filter.onclick=()=>{active=null;onChange();};
  summary.onclick=e=>{const target=e.target.closest('[data-summary]');if(target&&target.dataset.summary!=='missingFiles')choose('audit',target.dataset.summary==='changedFiles'?'version-changed':target.dataset.summary);else if(target||e.target.closest('[data-check]'))showAudit();};
  editor.onclick=e=>{const tag=e.target.closest('[data-tag]');if(tag)choose('tag',tag.dataset.tag);else if(e.target.closest('[data-edit-record]'))openRecord();else if(e.target.closest('[data-edit-object]'))openRecord(true);else if(e.target.closest('[data-view-source]'))showSource();};
  dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
  dialog.onclick=async e=>{
    if(busy)return;
    if(e.target.closest('[data-close]'))dialog.close();
    else if(e.target.closest('[data-initialize-art]')){if(await mutate('/api/art-initialize',{}))renderAudit();}
    else if(e.target.closest('[data-register-missing]')){const paths=getData().artAudit.unregistered.map(a=>a.path);let ok=true;for(let i=0;i<paths.length;i+=100){if(!await mutate('/api/art-register',{paths:paths.slice(i,i+100)})){ok=false;break;}}if(ok)renderAudit();}
    else if(e.target.closest('[data-review-incomplete]')){dialog.close();active=null;choose('audit','incomplete');}
    else if(e.target.closest('[data-view-source]'))showSource();
  };
  dialog.onsubmit=async e=>{
    e.preventDefault();if(busy||e.target.id!=='art-record-form')return;
    const form=e.target,choice=dialog.querySelector('#art-object-choice').value,edit=form.dataset.editObject==='true';
    const payload={path:form.dataset.path};
    if(edit||choice==='__new__')payload.object={...(edit?{id:choice}:{}),label:dialog.querySelector('#art-object-label').value,tags:splitTags(dialog.querySelector('#art-object-tags').value)};else payload.objectId=choice;
    if(await mutate(edit?'/api/art-object':'/api/art-record',payload))dialog.close();
  };
  const check=document.getElementById('bulk-tags');check.textContent='检查美术清单';check.onclick=showAudit;
  return {renderNav,renderEditor,matches,clear:()=>{active=null;},cardTags:a=>a.tags.slice(0,3).map(t=>`<span>${esc(t)}</span>`).join('')+(status(a)!=='linked'?`<span class="record-pending">${labels[status(a)]}</span>`:'')};
}
