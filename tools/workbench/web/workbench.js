import {needsAttention} from './display-data.js';
import {createArkBrief} from './ark-brief.js';
import {createHunyuanBrief,transmissionReview,viewLabels} from './hunyuan-brief.js';
import {serviceDetails,failureDetails} from './service-details.js';
import {createVersionBrief} from './version-brief.js';
import {createAudioBrief,audioReview} from './audio-brief.js';
import {api,state as initialState} from './session.js';
import {getLibraryData,openLibraryAsset,openAssetVersions,setLibraryActive,icon,escape as esc,toast,refreshLibrary} from './app.js';
import {createAssetFits} from './asset-fits.js';
const $=id=>document.getElementById(id);
const assetFits=createAssetFits({getLibraryData,escape:esc,toast,preview:openLibraryAsset});
const arkAccount={logo:'/logos/bytedance-seed.ico',shared:true,keys:'https://ark.volcengine.com/region:cn-beijing/apiKey'};
const providers={hunyuan3d:{name:'混元 3D',logo:'/logos/hunyuan3d.png',keys:'https://console.cloud.tencent.com/ai3d/api-key'},tripo:{name:'Tripo AI',logo:'/logos/tripo.png',keys:'https://developers.tripo3d.ai/zh/keys'},elevenlabs:{name:'ElevenLabs',logo:'/logos/elevenlabs.svg',keys:'https://elevenlabs.io/app/settings/api-keys'},
  seedream:{...arkAccount,name:'Seedream',description:'图像生成与参考图改绘。与 Seedance 共用火山方舟 API Key，在任一卡片保存一次即可。'},
  seedance:{...arkAccount,name:'Seedance',description:'文本或首帧生成视频。与 Seedream 共用火山方舟 API Key；请开通所选视频模型。'}};
const providerGroups=[
  {id:'image',sortKey:'erwei',title:'2D 资产生成',description:'制作角色立绘、场景图、图标与 UI 美术。',providers:['seedream']},
  {id:'model',sortKey:'sanwei',title:'3D 资产生成',description:'生成角色、装备、道具等 3D 模型。',providers:['tripo','hunyuan3d']},
  {id:'video',sortKey:'shipin',title:'视频生成',description:'制作过场、氛围短片与镜头预演。',providers:['seedance']},
  {id:'audio',sortKey:'yinpin',title:'音频生成',description:'生成游戏音效、配乐与角色台词。',providers:['elevenlabs']}
].sort((a,b)=>a.sortKey.localeCompare(b.sortKey,'en'));
const audioBrief=createAudioBrief();
const arkBrief=createArkBrief({getLibraryData});
const versionBrief=createVersionBrief({getData:getLibraryData,escape:esc});
const hunyuanBrief=createHunyuanBrief({getLibraryData});
const providerName=j=>j.provider==='image'?(j.executionSource||'内置生图'):providers[j.provider]?.name||j.provider;

const names={queued:'待确认 / 待执行',running:'制作中',succeeded:'已生成',registered:'已登记结果',failed:'失败',blocked:'受阻',cancelled:'已取消',interrupted:'已中断'};
let state=initialState,jobs=[],view='assets',filter='all',selected=new URLSearchParams(location.search).get('job'),reviewVersion=0,refreshing=false;
function icons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
async function setView(next,hash=true){
  const target=['assets','tasks','services'].includes(next)?next:'assets';
  view=target;$('workbench').dataset.view=view;
  $('current-view-label').textContent={assets:'资产库',tasks:'生成任务',services:'生成服务'}[view];
  document.querySelector('.library').hidden=view!=='assets';$('inspector').hidden=view!=='assets';
  $('task-view').hidden=view!=='tasks';$('service-view').hidden=view!=='services';
  $('asset-navigation').hidden=view!=='assets';$('task-navigation').hidden=view!=='tasks';$('service-navigation').hidden=view!=='services';
  document.querySelectorAll('.workspace-tab').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  setLibraryActive(view==='assets');if(hash||target!==next)history.replaceState(null,'',location.pathname+location.search+'#'+view);
  if(view==='tasks')refreshJobs(true);if(view==='services')refreshServices();
}
function taskNav(){
  $('pending-count').textContent=jobs.filter(j=>j.status==='queued').length;
  const entries=[['all','全部任务'],['queued','待确认 / 待执行'],['running','制作中'],['succeeded','已生成'],['issues','需要处理']];
  $('task-filters').innerHTML=entries.map(([key,name])=>`<button class="side-item ${key===filter?'active':''}" data-filter="${key}"><span>${name}</span><span class="count">${jobs.filter(j=>matches(j,key)).length}</span></button>`).join('');
}
const matches=(j,key=filter)=>key==='all'||(key==='issues'?needsAttention(j):key==='succeeded'?['succeeded','registered'].includes(j.status):j.status===key);
function jobLineage(j){
  const c=j.lineage,groups=getLibraryData()?.versions?.groups||[];
  const describe=(gid,vid)=>{const g=groups.find(g=>g.id===gid),v=g?.versions.find(v=>v.id===vid);return esc(g?.title||gid)+(vid?' · V'+(v?.number||'?'):'');};
  return (c?`<section class="job-lineage"><h3>版本与制作依据</h3><p>关联资产：${c.group?describe(c.group):'新资产'}</p><p>修改底稿：${c.parent?describe(c.group,c.parent):'独立方案'}</p>${c.references.map(r=>`<p>${esc(r.role)}：${describe(r.group,r.version)}</p>`).join('')}<p>${esc(c.note)}</p><p class="reference-note">实际传给生成工具的文件列在下方“输入文件”；版本关联本身不会上传额外文件。</p></section>`:'')+
    (j.assetVersion?`<button class="button secondary" id="job-version-history">查看资产版本历史</button>`:'')+
    (j.versionError?`<p role="alert">结果已保留，版本记录尚未同步。</p><details><summary>查看原因</summary><p>${esc(j.versionError)}</p></details>`:'')+
    (j.artRegistrationError?`<p role="alert">文件已保留，美术清单尚未同步。请让 Agent 修复登记，无需重新生成。</p><details><summary>查看原因</summary><p>${esc(j.artRegistrationError)}</p></details>`:'');
}
function referenceInputs(job){
  if(!job.inputs.length)return '';
  const role=job.provider==='seedance'?'视频首帧':job.provider==='seedream'?'改绘参考图':'输入参考图';
  return '<h3>输入文件</h3><div class="task-inputs">'+job.inputs.map(x=>{const label=esc(viewLabels[x.view]||role);return `<figure class="task-input">${x.previewUrl?`<a href="${esc(x.previewUrl)}" target="_blank" rel="noopener noreferrer" aria-label="打开${label}原图"><img src="${esc(x.previewUrl)}" alt="${label}" loading="lazy"></a><figcaption>${label}</figcaption>`:''}<code>${esc(x.path)}</code><details><summary>文件版本</summary><small class="input-hash">SHA-256 ${esc(x.sha256)}</small></details></figure>`;}).join('')+'</div><p class="reference-note">展示的是本次任务保存的参考图；生成时使用同一份文件。</p>';
}
function renderJobs(){
  taskNav();$('task-list-title').textContent=({all:'全部任务',queued:'待确认 / 待执行',running:'制作中',succeeded:'已生成',issues:'需要处理'})[filter];const visible=jobs.filter(j=>matches(j));$('task-list-count').textContent=visible.length;
  $('task-overview').innerHTML=`<div class="task-summary"><strong>${jobs.length}</strong><span> 个项目生成任务</span></div><button class="button secondary" id="refresh-tasks">刷新任务</button>`;
  $('refresh-tasks').onclick=()=>refreshJobs(true);
  $('task-list').innerHTML=visible.map(j=>`<button class="task-row ${j.id===selected?'selected':''}" data-job="${esc(j.id)}"><span class="task-row-main"><strong>${esc(j.title)}</strong><small>${esc(providerName(j))}</small></span><span class="status-pill">${esc(needsAttention(j)?'需要处理':names[j.status]||'状态待核对')}</span></button>`).join('')||'<p class="task-empty">还没有此类任务。可在这里新建，或由 Agent 提交制作需求。</p>';
  $('task-list').querySelectorAll('[data-job]').forEach(b=>b.onclick=()=>{selected=b.dataset.job;renderJobs();showJob();});
}
async function refreshJobs(detail=false){
  if(refreshing)return;refreshing=true;
  try{const result=await api('/api/jobs'),before=JSON.stringify(jobs);jobs=result.jobs;if(!jobs.some(j=>j.id===selected))selected=jobs[0]?.id;if(detail||before!==JSON.stringify(jobs))renderJobs();if(view==='tasks'&&(detail||before!==JSON.stringify(jobs)))await showJob();if(result.unreadable)toast(`${result.unreadable} 个任务记录无法读取，请检查文件`);}
  catch(e){toast(e.message);}finally{refreshing=false;}
}
async function showJob(){
  const version=++reviewVersion;if(!selected){$('task-detail').innerHTML='<div class="task-empty"><h2>选择一个生成任务</h2><p>查看制作需求、确认状态和生成结果。</p></div>';return;}
  try{
    const [result,history]=await Promise.all([api('/api/job-review?job='+encodeURIComponent(selected)),api('/api/asset-versions')]);if(version!==reviewVersion)return;if(getLibraryData())getLibraryData().versions=history;
    const j=result.job,a=result.approval;
    $('task-detail').innerHTML=`<div class="detail-heading"><span class="status-pill">${esc(names[j.status]||j.status)}</span><h2>${esc(j.title)}</h2><p>${esc(providerName(j))} · ${esc(j.id)}</p></div>${audioReview(j.audio,esc)}${jobLineage(j)}${transmissionReview(j,esc)}${failureDetails(j.failure,esc)}${referenceInputs(j)}<h3>制作需求</h3><p class="request-prompt">${esc(j.parameters?.prompt||j.parameters?.text||'详细设置见下方参数。')}</p><details><summary>详细参数</summary><pre class="request-details">${esc(JSON.stringify(j.parameters,null,2))}</pre></details>`+
      (a?`<section class="confirmation-panel"><h3>确认本次制作</h3><p>${esc(a.error||(a.approved?'本次请求已授权，等待 Agent 执行。':'请核对服务、制作需求和输入文件。确认仅授权这一份请求。'))}</p>${!a.error&&!a.approved?'<label class="consent"><input type="checkbox" id="accept-charge">我确认本次请求，并接受生成服务可能产生的费用。</label><button class="button primary" id="approve-job" disabled>确认并授权本次制作</button>':''}${a.error?'<button class="button secondary" id="configure-service">生成服务</button>':''}</section>`:j.status==='running'?'<p>制作进行中，任务状态会自动更新。</p>':j.status==='queued'?(j.host?'<p>由 Agent 调用内置生图工具，完成后登记实际输出。</p>':'<p>本地工具任务由 Agent 按项目配置执行。</p>'):'')+
      (j.artifacts.length?'<h3>生成结果</h3><div class="art-editor-actions">'+j.artifacts.map(x=>`<button class="button secondary" data-result="${esc(x.path)}">查看 ${esc(x.path.split('/').pop())}</button>`).join('')+'</div><p>生成文件可在资产库中查看；导入游戏后请检查实际效果。</p>':'')+
      (['failed','blocked','cancelled','interrupted'].includes(j.status)?`<p>请让 Agent 检查此任务的运行记录${j.remoteId?'并恢复已有云端任务':''}，避免重复提交。</p>`:'');
    if($('job-version-history'))$('job-version-history').onclick=async()=>{await refreshLibrary(true);await openAssetVersions(j.assetVersion.group);};
    if($('configure-service'))$('configure-service').onclick=()=>setView('services');
    if($('accept-charge')){
      $('accept-charge').onchange=()=>{$('approve-job').disabled=!$('accept-charge').checked;};
      $('approve-job').onclick=async()=>{if(!$('accept-charge').checked)return;const button=$('approve-job');button.disabled=true;$('accept-charge').disabled=true;
        try{await api('/api/job-approve',{job:j.id,fingerprint:a.fingerprint,accept_charge:true});toast('已授权，等待 Agent 执行');await showJob();}
        catch(e){toast(e.message);await showJob();}
      };
    }
    $('task-detail').querySelectorAll('[data-result]').forEach(b=>b.onclick=async()=>{await refreshLibrary(true);if(await setView('assets')!==false)await openLibraryAsset(b.dataset.result);});
  }catch(e){if(version===reviewVersion)$('task-detail').innerHTML=`<p class="art-record-warning">${esc(e.message)}</p>`;}
}
function renderServices(){
  const providerCard=key=>{const p=providers[key],info=state.providers[key]||{};
    return `<article class="provider-card" data-provider="${key}"><div class="provider-top"><img class="provider-logo" src="${p.logo}" alt="${p.shared?'ByteDance Seed 官方标识':esc(p.name)+' Logo'}"><div><h3>${p.name}</h3><span class="status-pill">${info.environment_present?'使用环境变量':info.saved?'本机已保存':'未配置'}</span></div></div>${p.description?`<p>${esc(p.description)}</p>`:''}<p>${info.environment_present?'调用时优先使用环境变量；不会回显已有密钥。':info.saved?'已保存供后续任务使用，尚未验证服务账户。':'输入此服务的 API Key，供后续任务使用。'}</p><form><label for="key-${key}">API Key</label><input id="key-${key}" type="password" autocomplete="off" placeholder="输入完整 API Key" required><div class="art-editor-actions"><button type="submit" class="button primary" ${state.storage_available?'':'disabled'}>加密保存</button><button type="button" class="button secondary" data-remove-key="${key}" ${info.saved?'':'disabled'}>${p.shared?'移除共用密钥':'移除本机密钥'}</button></div><p class="provider-notice" role="status"></p></form>${['tripo','hunyuan3d'].includes(key)?`<button type="button" class="button secondary" data-check-service="${key}">检查当前设置</button><div data-service-details="${key}"></div>`:''}${p.keys?`<div class="provider-links"><a href="${p.keys}" target="_blank" rel="noopener noreferrer">获取密钥 ↗</a></div>`:''}</article>`;
  };
  $('service-categories').innerHTML=providerGroups.map(g=>`<button class="side-item" data-service-group="${g.id}"><span>${g.title}</span></button>`).join('');
  $('service-categories').querySelectorAll('[data-service-group]').forEach(b=>b.onclick=()=>{
    $('provider-group-'+b.dataset.serviceGroup).scrollIntoView({block:'start'});
  });
  $('service-home').onclick=()=>{$('service-view').scrollTo({top:0});};
  $('provider-grid').innerHTML=providerGroups.map(group=>`<section class="provider-group" aria-labelledby="provider-group-${group.id}"><header><h2 id="provider-group-${group.id}">${group.title}</h2><p>${group.description}</p></header><div class="provider-grid">${group.providers.map(providerCard).join('')}</div></section>`).join('');
  $('provider-grid').querySelectorAll('form').forEach(form=>form.onsubmit=async e=>{e.preventDefault();const card=form.closest('[data-provider]'),input=form.querySelector('input'),button=form.querySelector('button');button.disabled=true;
    try{state=await api('/api/save',{provider:card.dataset.provider,key:input.value});input.value='';renderServices();toast('密钥已在本机加密保存，未启动生成');}
    catch(error){form.querySelector('.provider-notice').textContent=error.message;button.disabled=false;}
  });
  $('provider-grid').querySelectorAll('[data-remove-key]').forEach(button=>button.onclick=async()=>{if(!window.confirm(providers[button.dataset.removeKey]?.shared?'移除 Seedream 和 Seedance 共用的本机密钥？两张卡片会同时变为未配置；环境变量和平台密钥不会删除。':'移除这个服务的本机密钥？环境变量和平台密钥不会被删除。'))return;try{state=await api('/api/remove',{provider:button.dataset.removeKey});renderServices();toast('已移除本机保存的密钥');}catch(e){toast(e.message);}});
  $('provider-grid').querySelectorAll('[data-check-service]').forEach(button=>button.onclick=async()=>{button.disabled=true;const key=button.dataset.checkService;const output=$('provider-grid').querySelector(`[data-service-details="${key}"]`);try{output.innerHTML=serviceDetails(await api('/api/service-diagnostics?provider='+encodeURIComponent(key)),esc);}catch(error){output.textContent=error.message;}finally{button.disabled=false;}});
  if(!state.storage_available)toast('此系统请使用环境变量配置密钥');
}
async function refreshServices(){try{state=await api('/api/state');renderServices();}catch(e){toast(e.message);}}
document.querySelectorAll('.workspace-tab').forEach(b=>b.onclick=()=>setView(b.dataset.view));
$('task-filters').onclick=e=>{const b=e.target.closest('[data-filter]');if(b){filter=b.dataset.filter;renderJobs();}};
async function newTask(context){
  try{
    if(!getLibraryData())await refreshLibrary();
    if(!getLibraryData())throw new Error('项目资产尚未读取完成，请稍后重试');
    $('brief-form').reset();
    if(context){const g=getLibraryData()?.versions?.groups.find(g=>g.id===context.group);$('brief-provider').value=['image','texture'].includes(g?.kind)?'image':g?.kind==='audio'?'elevenlabs':g?.kind==='video'?'seedance':'';}
    audioBrief.update();arkBrief.refresh();versionBrief.refresh(context);hunyuanBrief.refresh();$('brief-dialog').showModal();
  }catch(error){toast('无法打开制作表单：'+error.message);console.error(error);}
}
$('new-task').onclick=()=>newTask();
window.addEventListener('workbench:revise-asset',event=>newTask(event.detail));
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
$('brief-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;
  try{const result=await api('/api/jobs',{provider:$('brief-provider').value,prompt:$('brief-prompt').value,...($('brief-provider').value==='elevenlabs'?{audio:audioBrief.parameters()}:['seedream','seedance'].includes($('brief-provider').value)?arkBrief.request():{}),...versionBrief.request(),...($('brief-provider').value==='hunyuan3d'?hunyuanBrief.request():{})});selected=result.job.id;filter='all';$('brief-dialog').close();setView('tasks');await refreshJobs(true);toast('已保存制作请求，尚未提交生成');}
  catch(error){toast(error.message);}finally{button.disabled=false;}
};
$('help').onclick=()=>{$('dialog-body').innerHTML='<ul><li>看板读取当前游戏目录，点击刷新发现新增资产。</li><li>标签来自美术清单；检查美术清单可查找漏登、缺少归属和版本变化。</li><li>在生成任务中核对需求、确认请求和查看结果；确认后由 Agent 执行。</li><li>Windows 可加密保存服务密钥；其他系统使用环境变量。保存配置不会启动任务。</li><li>可预览的图片、粒子配置和音频波形支持拖动与缩放。GLB/glTF、FBX、OBJ 支持旋转、缩放与平移；引擎角色关联导出预览后可切换已绑定动作。</li></ul>';$('info-dialog').showModal();};
window.addEventListener('hashchange',()=>setView(location.hash.slice(1),false));
window.addEventListener('workbench:assets-ready',()=>{document.title=getLibraryData().project+' · 项目工作台';assetFits.refresh();});
setInterval(()=>{if(view==='tasks'&&!document.hidden)refreshJobs();},4000);
icons();setView(location.hash.slice(1)||'assets',false);refreshJobs();
