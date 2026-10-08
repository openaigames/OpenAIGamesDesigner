import {createActionEditor} from './action-editor.js';
const statusText={within_tolerance:'指定时序在容差内',issues:'有时序问题',incomplete:'记录未完成或有丢失',observed:'仅记录，未设定检查标准'};
const rowStatus={within_tolerance:'在容差内',outside_tolerance:'超出容差',missing:'未记录',uncertain:'精度不足'};
const engineText={unreal:'UE5',unity:'Unity',godot:'Godot',threejs:'Three.js',phaser:'Phaser',web:'网页通用'};
const inputText={human:'人工操作',software:'软件输入',mixed:'混合输入',unknown:'输入方式未确认'};
const n=v=>typeof v==='number'?v.toFixed(3):'—';
export function createActionReview({api,esc,toast}) {
  const root=document.getElementById('action-view'); let enabled=false, runs=[], selected='', record=null, request=0;
  root.innerHTML=`<header class="page-heading"><div><h1>动作检查</h1><p>对照游戏实际发生的事件与设定时间。</p></div><button id="action-refresh" class="button secondary">刷新记录</button></header>
    <details class="action-import"><summary>导入项目记录</summary><form id="action-import-form">
    <label>记录名称<input name="title" required maxlength="100" placeholder="例如：跳跃落地 · 调整后"></label>
    <label>事件文件<input name="capture" required placeholder="game/Saved/ActionTiming/记录.json"></label>
    <label>时间设定（可选）<input name="spec" placeholder="production/action-timing/设定.json"></label>
    <label>实机录像（可选）<input name="video" placeholder="production/video/演示.mp4"></label>
    <label>录像中动作开始于（秒）<input name="video_zero_s" type="number" min="0" step="0.001" value="0"></label>
    <button class="button primary" type="submit">保存这次记录</button><p>路径相对于当前项目。导入会保留事件和设定的副本，后续调整不会改写旧记录。</p></form></details>
    <div class="action-selectors"><label>引擎<select id="action-engine"><option value="">全部引擎</option>${Object.entries(engineText).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label>
    <label>当前记录<select id="action-run"><option>尚无记录</option></select></label><label>对照记录<select id="action-baseline"><option value="">不对照</option></select></label></div>
    <p id="action-message" role="status"></p><section id="action-detail" aria-live="polite"></section>`;
  root.insertAdjacentHTML('afterbegin','<div class="ae-tabs"><button class="button primary" id="ae-mode-edit">片段编辑</button><button class="button secondary" id="ae-mode-record">实机记录</button></div><section id="action-editor"></section>');
  const editor=createActionEditor({root:root.querySelector('#action-editor'),api,esc,toast,onRunSaved:id=>{selected=id;refresh();}});
  function mode(edit){root.classList.toggle('ae-edit-mode',edit);editor.active(enabled&&edit);if(!edit&&enabled)refresh();}
  root.querySelector('#ae-mode-edit').onclick=()=>mode(true);
  root.querySelector('#ae-mode-record').onclick=()=>mode(false);
  mode(true);
  const $=id=>root.querySelector('#'+id);
  async function refresh() {
    try { const data=await api('/api/action-runs'); runs=data.runs;
      $('action-message').textContent=[data.unreadable.length?`${data.unreadable.length} 份记录无法读取。`:'',data.older_runs?`显示最近 200 份，另有 ${data.older_runs} 份保存在项目中。`:''].join(' '); choices();
    } catch(e){$('action-message').textContent=e.message;}
  }
  function choices() {
    const available=runs.filter(r=>!$('action-engine').value||r.engine===$('action-engine').value);
    if(!available.some(r=>r.id===selected))selected=available[0]?.id||'';
    $('action-run').innerHTML=available.map(r=>`<option value="${r.id}" ${r.id===selected?'selected':''}>${esc(r.title)} · ${engineText[r.engine]}</option>`).join('')||'<option value="">尚无记录</option>';
    $('action-baseline').innerHTML='<option value="">不对照</option>'+available.filter(r=>r.id!==selected).map(r=>`<option value="${r.id}">${esc(r.title)}</option>`).join('');
    show();
  }
  async function show() {
    const version=++request; record=null;
    if(!selected){$('action-detail').innerHTML='<div class="action-empty"><h2>还没有实际运行记录</h2><p>接入对应引擎的记录组件，运行一次动作并导入事件文件。UE5、Unity、Godot、Three.js、Phaser 和其他网页游戏使用同一页检查。</p><p>动作编辑仍在引擎里进行；这里查看输入、动作、规则和声音触发的实际时刻。</p></div>';return;}
    $('action-detail').innerHTML='<p role="status">正在读取记录…</p>';
    try {const result=await api('/api/action-run?id='+selected);if(version!==request)return;record=result;render();}
    catch(e){if(version===request)$('action-detail').textContent=e.message;}
  }
  function render() {
    const r=record,c=r.capture,s=r.spec||{},report=r.result.report;
    const trackName=t=>s.track_labels?.[t]||t,eventName=(t,id)=>s.event_labels?.[t]?.[id]||id;
    const tracks=[...new Set([...c.events,...(s.events||[]),...(s.clips||[]),...(s.windows||[])].map(e=>e.track))];
    const duration=Math.max(c.duration_s,s.duration_s||0,0.001), pos=t=>Math.max(0,Math.min(100,100*t/duration));
    const bars=(kind,track)=> (s[kind]||[]).filter(e=>e.track===track).map(e=>`<span class="action-bar ${kind}" style="left:${pos(e.start_s)}%;width:${pos(e.end_s)-pos(e.start_s)}%" title="${esc(eventName(track,e.id))} ${n(e.start_s)}–${n(e.end_s)} s">${esc(eventName(track,e.id))}</span>`).join('');
    $('action-detail').innerHTML=`<section class="action-summary"><div><h2>${esc(r.title)}</h2><span class="action-result ${r.result.status}">${statusText[r.result.status]}</span></div><p>${engineText[c.engine]} ${esc(c.engine_version)} · ${inputText[c.input_mode]} · ${c.events.length} 个事件 · ${n(c.duration_s)} 秒</p><p>版本：${esc(c.revision)}　来源：${esc(c.source)}</p><p>输入：${esc(c.input_description)}</p><p>本页检查已记录的事件时间。画面品质、听感和网络同步需另行验证。</p><button id="action-export" class="button secondary">导出这次检查</button></section>
      <div class="action-timeline-heading"><h3>动作时间轴</h3><label>放大<input id="action-zoom" type="range" min="1" max="4" step="0.5" value="1"></label><label>轨道<select id="action-track"><option value="">全部轨道</option>${tracks.map(t=>`<option value="${esc(t)}">${esc(trackName(t))}</option>`).join('')}</select></label><span>蓝条：动作　绿条：允许区间　空心点：设定　实心点：实际</span></div>
      <div class="action-scroll"><div id="action-timeline" class="action-timeline"><div class="action-ruler"><div aria-hidden="true"></div><div>${[0,.25,.5,.75,1].map(t=>`<span style="left:${t*100}%">${n(t*duration)}s</span>`).join('')}</div></div>
      ${tracks.map(track=>`<div class="action-lane" data-track="${esc(track)}"><strong>${esc(trackName(track))}</strong><div class="action-lane-track">${bars('clips',track)}${bars('windows',track)}${(s.events||[]).filter(e=>e.track===track).map(e=>`<button class="action-event expected" style="left:${pos(e.time_s)}%" data-time="${e.time_s}" title="设定 ${esc(eventName(track,e.id))} ${n(e.time_s)} s" aria-label="设定 ${esc(eventName(track,e.id))}"></button>`).join('')}${c.events.filter(e=>e.track===track).map(e=>`<button class="action-event actual" style="left:${pos(e.t_s-c.zero_s)}%" data-time="${e.t_s-c.zero_s}" title="实际 ${esc(eventName(track,e.id))} ${n(e.t_s-c.zero_s)} s" aria-label="实际 ${esc(eventName(track,e.id))}"></button>`).join('')}</div></div>`).join('')}</div></div>
      <p id="action-selected-time" role="status">点击事件查看时刻${r.video?'，并定位到对应录像。':'。本次未关联录像。'}</p>
      ${r.video?`<video id="action-video" controls preload="metadata" src="/api/action-video?id=${r.id}"></video>`:''}
      <h3>${report?.events.length?'设定与实际':'实际事件'}</h3><div class="action-table-wrap"><table class="action-table"><thead><tr><th>轨道</th><th>事件</th><th>设定 / s</th><th>实际 / s</th><th>差值 / ms</th><th>误差 ± / ms</th><th>结果</th></tr></thead><tbody>${(report?.events.length?report.events:c.events.map(e=>({...e,actual_s:e.t_s-c.zero_s}))).map(e=>`<tr><td>${esc(trackName(e.track))}</td><td>${esc(eventName(e.track,e.id))}</td><td>${n(e.expected_s)}</td><td>${n(e.actual_s)}</td><td>${n(e.delta_s===undefined?undefined:e.delta_s*1000)}</td><td>${n((e.uncertainty_s||0)*1000)}</td><td>${rowStatus[e.status]||'已记录'}</td></tr>`).join('')}</tbody></table></div>
      ${report?`<h3>其他检查</h3><p>${report.unplanned_events.length} 个事件未指定设定时间。${report.synchronization.length} 项轨道同步比较。</p><ul>${report.issues.map(i=>`<li>${esc(({outside_window:'事件超出允许区间',window_uncertain:'事件靠近区间边缘，采样精度不足',outside_capture:'事件超出设定总时长',missing_event:'缺少事件',timing:'时刻需要核对',synchronization:'轨道同步需要核对',delay:'事件间隔需要核对'})[i.kind]||i.kind)}：${esc(i.track||i.a?.join(' / ')||i.from?.join(' / ')||'')} ${esc(i.id||i.b?.join(' / ')||i.to?.join(' / ')||'')}</li>`).join('')}</ul>`:''}
      <section id="action-comparison"></section><details><summary>文件与版本依据</summary><pre>${esc(JSON.stringify(r.files,null,2))}</pre></details>`;
    if(report?.delays?.length)$('action-comparison').insertAdjacentHTML('beforebegin',`<h3>事件之间的间隔</h3><div class="action-table-wrap"><table class="action-table"><thead><tr><th>开始 → 结束</th><th>允许 / ms</th><th>实际 / ms</th><th>结果</th></tr></thead><tbody>${report.delays.map(d=>`<tr><td>${esc(eventName(...d.from))} → ${esc(eventName(...d.to))}</td><td>${n(d.min_s*1000)}–${n(d.max_s*1000)}</td><td>${n(d.actual_s===undefined?undefined:d.actual_s*1000)}</td><td>${rowStatus[d.status]}</td></tr>`).join('')}</tbody></table></div>`);
    $('action-track').onchange=()=>{for(const lane of root.querySelectorAll('.action-lane'))lane.hidden=Boolean($('action-track').value&&lane.dataset.track!==$('action-track').value);};
    $('action-zoom').oninput=e=>{$('action-timeline').style.width=`${Number(e.target.value)*100}%`;};
    $('action-timeline').onclick=e=>{const b=e.target.closest('[data-time]');if(!b)return;const t=Number(b.dataset.time);$('action-selected-time').textContent=`${b.title}。`;if($('action-video')){$('action-video').pause();$('action-video').currentTime=t+r.video.zero_s;}};
    $('action-export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`action-${r.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  }
  $('action-refresh').onclick=refresh;
  $('action-engine').onchange=choices;
  $('action-run').onchange=()=>{selected=$('action-run').value;choices();};
  $('action-baseline').onchange=async()=>{const id=$('action-baseline').value, current=selected, section=$('action-comparison');if(!section)return;section.textContent='';if(!id)return;
    try {const result=await api(`/api/action-compare?a=${id}&b=${current}`);if(selected!==current||$('action-baseline').value!==id)return;
      section.innerHTML=`<h3>${esc(result.a.title)} → ${esc(result.b.title)}</h3><p>${esc(result.note)}</p><div class="action-table-wrap"><table class="action-table"><thead><tr><th>轨道 / 事件</th><th>对照 / s</th><th>当前 / s</th><th>变化 / ms</th></tr></thead><tbody>${result.rows.map(x=>`<tr><td>${esc(x.track+' / '+x.id)}</td><td>${n(x.a_s)}</td><td>${n(x.b_s)}</td><td>${n(x.delta_s===null?undefined:x.delta_s*1000)}</td></tr>`).join('')}</tbody></table></div>`;
    }catch(e){if(selected===current)section.textContent=e.message;}
  };
  $('action-import-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button');button.disabled=true;
    try{const values=Object.fromEntries(new FormData(form));values.video_zero_s=Number(values.video_zero_s);const result=await api('/api/action-import',values);selected=result.id;$('action-engine').value='';await refresh();toast('已保存动作记录');}
    catch(error){toast(error.message);}finally{button.disabled=false;}
  };
  return {active(value){const changed=value!==enabled;enabled=value;if(value&&changed){refresh();editor.active(root.classList.contains('ae-edit-mode'));}if(!value)editor.active(false);if(!value){const v=$('action-video');if(v)v.pause();}}};
}
