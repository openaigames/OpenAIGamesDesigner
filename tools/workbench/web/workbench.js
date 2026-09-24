import {api,state as initialState} from './session.js';
import {getLibraryData,openLibraryAsset,setLibraryActive,icon,escape as esc,toast,refreshLibrary} from './app.js';
const $=id=>document.getElementById(id);
const providers={hunyuan3d:{name:'混元 3D',logo:'/logos/hunyuan3d.png'},tripo:{name:'Tripo AI',logo:'/logos/tripo.png'}};
const names={queued:'待确认 / 待执行',running:'制作中',succeeded:'已生成',registered:'已登记结果',failed:'失败',blocked:'受阻',cancelled:'已取消',interrupted:'已中断'};
let state=initialState,jobs=[],view='assets',filter='all',selected=new URLSearchParams(location.search).get('job'),reviewVersion=0,refreshing=false;
function icons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
function setView(next,hash=true){
  view=['assets','tasks','services'].includes(next)?next:'assets';$('workbench').dataset.view=view;
  $('current-view-label').textContent={assets:'资产库',tasks:'制作任务',services:'服务与密钥'}[view];
  document.querySelector('.library').hidden=view!=='assets';$('inspector').hidden=view!=='assets';
  $('task-view').hidden=view!=='tasks';$('service-view').hidden=view!=='services';
  $('asset-navigation').hidden=view!=='assets';$('task-navigation').hidden=view!=='tasks';$('service-navigation').hidden=view!=='services';
  document.querySelectorAll('.workspace-tab').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  setLibraryActive(view==='assets');if(hash)history.replaceState(null,'',location.pathname+location.search+'#'+view);
  if(view==='tasks')refreshJobs(true);if(view==='services')refreshServices();
}
function taskNav(){
  $('pending-count').textContent=jobs.filter(j=>j.status==='queued').length;
  const entries=[['all','全部任务'],['queued','待确认 / 待执行'],['running','制作中'],['succeeded','已生成'],['issues','需要处理']];
  $('task-filters').innerHTML=entries.map(([key,name])=>`<button class="side-item ${key===filter?'active':''}" data-filter="${key}"><span>${name}</span><span class="count">${jobs.filter(j=>matches(j,key)).length}</span></button>`).join('');
}
const matches=(j,key=filter)=>key==='all'||(key==='issues'?['failed','blocked','interrupted','cancelled'].includes(j.status):key==='succeeded'?['succeeded','registered'].includes(j.status):j.status===key);
function renderJobs(){
  taskNav();const visible=jobs.filter(j=>matches(j));$('task-list-count').textContent=visible.length;
  $('task-overview').innerHTML=`<div class="task-summary"><strong>${jobs.length}</strong><span> 个项目制作任务</span></div><button class="button secondary" id="refresh-tasks">刷新任务</button>`;
  $('refresh-tasks').onclick=()=>refreshJobs(true);
  $('task-list').innerHTML=visible.map(j=>`<button class="task-row ${j.id===selected?'selected':''}" data-job="${esc(j.id)}"><span class="task-row-main"><strong>${esc(j.title)}</strong><small>${esc(providers[j.provider]?.name||j.provider)}</small></span><span class="status-pill">${esc(names[j.status]||j.status)}</span></button>`).join('')||'<p class="task-empty">还没有此类任务。可在这里新建，或由助手提交制作需求。</p>';
  $('task-list').querySelectorAll('[data-job]').forEach(b=>b.onclick=()=>{selected=b.dataset.job;renderJobs();showJob();});
}
async function refreshJobs(detail=false){
  if(refreshing)return;refreshing=true;
  try{const result=await api('/api/jobs'),before=JSON.stringify(jobs);jobs=result.jobs;if(!jobs.some(j=>j.id===selected))selected=jobs[0]?.id;renderJobs();if(view==='tasks'&&(detail||before!==JSON.stringify(jobs)))await showJob();if(result.unreadable)toast(`${result.unreadable} 个任务记录无法读取，请检查文件`);}
  catch(e){toast(e.message);}finally{refreshing=false;}
}
async function showJob(){
  const version=++reviewVersion;if(!selected){$('task-detail').innerHTML='<div class="task-empty"><h2>选择一个制作任务</h2><p>查看制作需求、确认状态和生成结果。</p></div>';return;}
  try{
    const result=await api('/api/job-review?job='+encodeURIComponent(selected));if(version!==reviewVersion)return;
    const j=result.job,a=result.approval;
    $('task-detail').innerHTML=`<div class="detail-heading"><span class="status-pill">${esc(names[j.status]||j.status)}</span><h2>${esc(j.title)}</h2><p>${esc(providers[j.provider]?.name||j.provider)} · ${esc(j.id)}</p></div><h3>制作请求</h3><pre class="request-details">${esc(JSON.stringify(j.parameters,null,2))}</pre>${j.inputs.length?'<h3>输入文件</h3>'+j.inputs.map(x=>`<p><code>${esc(x.path)}</code><small class="input-hash">SHA-256 ${esc(x.sha256)}</small></p>`).join(''):''}`+
      (a?`<section class="confirmation-panel"><h3>确认本次制作</h3><p>${esc(a.error||(a.approved?'本次请求已授权，等待助手执行。':'请核对服务、制作需求和输入文件。确认仅授权这一份请求。'))}</p>${!a.error&&!a.approved?'<label class="consent"><input type="checkbox" id="accept-charge">我确认本次请求，并接受生成服务可能产生的费用。</label><button class="button primary" id="approve-job" disabled>确认并授权本次制作</button>':''}${a.error?'<button class="button secondary" id="configure-service">服务与密钥</button>':''}</section>`:j.status==='running'?'<p>制作进行中，任务状态会自动更新。</p>':j.status==='queued'?'<p>本地工具任务由助手按项目配置执行。</p>':'')+
      (j.artifacts.length?'<h3>生成结果</h3><div class="art-editor-actions">'+j.artifacts.map(x=>`<button class="button secondary" data-result="${esc(x.path)}">查看 ${esc(x.path.split('/').pop())}</button>`).join('')+'</div><p>生成文件可在资产库中查看；导入游戏后请检查实际效果。</p>':'')+
      (['failed','blocked','cancelled','interrupted'].includes(j.status)?`<p>请让助手检查此任务的运行记录${j.remoteId?'并恢复已有云端任务':''}，避免重复提交。</p>`:'');
    if($('configure-service'))$('configure-service').onclick=()=>setView('services');
    if($('accept-charge')){
      $('accept-charge').onchange=()=>{$('approve-job').disabled=!$('accept-charge').checked;};
      $('approve-job').onclick=async()=>{if(!$('accept-charge').checked)return;const button=$('approve-job');button.disabled=true;$('accept-charge').disabled=true;
        try{await api('/api/job-approve',{job:j.id,fingerprint:a.fingerprint,accept_charge:true});toast('已授权，等待助手执行');await showJob();}
        catch(e){toast(e.message);await showJob();}
      };
    }
    $('task-detail').querySelectorAll('[data-result]').forEach(b=>b.onclick=async()=>{await refreshLibrary(true);setView('assets');openLibraryAsset(b.dataset.result);});
  }catch(e){if(version===reviewVersion)$('task-detail').innerHTML=`<p class="art-record-warning">${esc(e.message)}</p>`;}
}
function renderServices(){
  $('provider-grid').innerHTML=Object.entries(providers).map(([key,p])=>{const info=state.providers[key];return `<article class="provider-card" data-provider="${key}"><div class="provider-top"><img class="provider-logo" src="${p.logo}" alt=""><div><h2>${p.name}</h2><span class="status-pill">${info.environment_present?'使用环境变量':info.saved?'本机已保存':'未配置'}</span></div></div><p>${info.environment_present?'调用时优先使用环境变量；不会回显已有密钥。':info.saved?'已保存供后续任务使用，尚未验证服务账户。':'输入此服务的 API Key，供后续任务使用。'}</p><form><label for="key-${key}">API Key</label><input id="key-${key}" type="password" autocomplete="off" placeholder="输入完整 API Key" required><div class="art-editor-actions"><button type="submit" class="button primary" ${state.storage_available?'':'disabled'}>加密保存</button><button type="button" class="button secondary" data-remove-key="${key}" ${info.saved?'':'disabled'}>移除本机密钥</button></div><p class="provider-notice" role="status"></p></form></article>`;}).join('');
  $('provider-grid').querySelectorAll('form').forEach(form=>form.onsubmit=async e=>{e.preventDefault();const card=form.closest('[data-provider]'),input=form.querySelector('input'),button=form.querySelector('button');button.disabled=true;
    try{state=await api('/api/save',{provider:card.dataset.provider,key:input.value});input.value='';renderServices();toast('密钥已在本机加密保存，未启动生成');}
    catch(error){form.querySelector('.provider-notice').textContent=error.message;button.disabled=false;}
  });
  $('provider-grid').querySelectorAll('[data-remove-key]').forEach(button=>button.onclick=async()=>{if(!window.confirm('移除这个服务的本机密钥？环境变量和平台密钥不会被删除。'))return;try{state=await api('/api/remove',{provider:button.dataset.removeKey});renderServices();toast('已移除本机保存的密钥');}catch(e){toast(e.message);}});
  if(!state.storage_available)toast('此系统请使用环境变量配置密钥');
}
async function refreshServices(){try{state=await api('/api/state');renderServices();}catch(e){toast(e.message);}}
document.querySelectorAll('.workspace-tab').forEach(b=>b.onclick=()=>setView(b.dataset.view));
$('task-filters').onclick=e=>{const b=e.target.closest('[data-filter]');if(b){filter=b.dataset.filter;renderJobs();}};
$('new-task').onclick=()=>{$('brief-form').reset();$('brief-dialog').showModal();};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
$('brief-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;
  try{const result=await api('/api/jobs',{provider:$('brief-provider').value,prompt:$('brief-prompt').value});selected=result.job.id;filter='all';$('brief-dialog').close();await refreshJobs(true);toast('已保存制作请求，尚未提交生成');}
  catch(error){toast(error.message);}finally{button.disabled=false;}
};
$('help').onclick=()=>{$('dialog-body').innerHTML='<ul><li>看板读取当前游戏目录，点击刷新发现新增资产。</li><li>标签来自 Art Direction；检查美术清单可查找漏登、缺少归属和版本变化。</li><li>在制作任务中核对需求、确认请求和查看结果；确认后由助手执行。</li><li>Windows 可加密保存服务密钥；其他系统使用环境变量。保存配置不会启动任务。</li><li>可预览的图片、粒子配置和音频波形支持拖动与缩放。GLB/glTF、OBJ 支持旋转、缩放与平移；引擎模型需先关联导出的 GLB。</li></ul>';$('info-dialog').showModal();};
window.addEventListener('hashchange',()=>setView(location.hash.slice(1),false));
window.addEventListener('workbench:assets-ready',()=>{document.title=getLibraryData().project+' · 项目工作台';});
setInterval(()=>{if(view==='tasks'&&!document.hidden)refreshJobs();},4000);
icons();setView(location.hash.slice(1)||'assets',false);refreshJobs();
