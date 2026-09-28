const $=id=>document.getElementById(id);
const kinds={character:'角色与动作',model:'模型',animation:'动作',engine:'引擎资源',image:'图片',texture:'贴图',vfx:'特效',audio:'音频',video:'视频',other:'其他'};
const roles={player:'主角',boss:'Boss',shared:'共享',unassigned:'其他'};

export function createAssetReview({getLibraryData,refreshLibrary,preview,escape:esc,toast}){
 let limits={candidate:30,game:30},mobileLane='game';
 $('review-view').innerHTML=`<header class="page-heading"><div><div class="review-eyebrow">PROJECT ASSETS</div><h1>素材看板</h1><p>候补素材先浏览，游戏角色直接选动作。</p></div><button class="button secondary" id="review-refresh">刷新目录</button></header>
 <div class="review-toolbar"><label class="search"><input id="review-search" type="search" placeholder="搜索素材、角色、动作…" aria-label="搜索看板"></label><select id="review-role" aria-label="筛选角色"><option value="">全部角色</option>${Object.entries(roles).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select><select id="review-kind" aria-label="筛选类型"><option value="">全部类型</option>${Object.entries(kinds).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></div>
 <div id="review-message" role="status" class="review-message">正在读取项目目录…</div><nav id="review-lanes" class="review-lanes" aria-label="素材分区"><button data-lane="candidate">候补素材</button><button data-lane="game">游戏应用</button></nav><div id="review-columns" class="review-columns"></div>`;
 function render(){
  const data=getLibraryData();if(!data)return;
  const files=data.assets.filter(a=>!a.previewCopy),characters=data.characters||[],members=new Set(characters.flatMap(c=>[c.model,...c.actions.map(a=>a.path)]));
  const entries=[...characters.map(c=>({id:'character:'+c.id,title:c.title,path:c.model,location:'game',kind:'character',role:c.role,character:c,search:c.actions.map(a=>a.label+' '+a.path).join(' ')})),
   ...files.filter(a=>!members.has(a.path)).map(a=>({...a,role:'unassigned'})),
   ...(data.fits||[]).map(f=>({id:'fit:'+f.id,title:f.spec.title,path:f.spec.goal_ref,location:f.location,kind:'other',role:f.spec.role,fit:f,search:f.spec.requirements.map(r=>r.description).join(' ')}))];
  const q=$('review-search').value.toLowerCase(),role=$('review-role').value,kind=$('review-kind').value;
  const rows=entries.filter(a=>(!role||a.role===role)&&(!kind||a.kind===kind)&&[a.title,a.path,a.search||''].join(' ').toLowerCase().includes(q));
  $('review-message').textContent=data.characterBindingError||`自动读取目录 · ${files.filter(a=>a.location==='candidate').length} 个候补文件 · ${files.filter(a=>a.location==='game').length} 个游戏文件 · ${characters.length} 个角色组合`;
  $('review-view').dataset.lane=mobileLane;
  $('review-lanes').querySelectorAll('button').forEach(b=>{b.setAttribute('aria-pressed',b.dataset.lane===mobileLane);b.onclick=()=>{mobileLane=b.dataset.lane;render();};});
  $('review-message').classList.toggle('review-warning',!!data.characterBindingError);
  $('review-columns').innerHTML=[['candidate','候补素材','实际工程内容目录外 · 点击即可预览'],['game','游戏应用','实际工程内容目录内 · 角色与工程关联动作一起展示']].map(([key,title,note],i)=>{
   const list=rows.filter(a=>a.location===key);
   return `<section class="review-column ${key}" aria-label="${title}"><header><div><span class="review-step">0${i+1}</span><h2>${title}</h2><span class="review-count">${list.length}</span></div><p>${note}</p></header><div class="review-card-list">${list.slice(0,limits[key]).map(a=>`<button class="review-card ${a.character?'character-card':''}" data-entry="${esc(a.id)}" aria-label="预览 ${esc(a.title)}"><div class="review-card-top"><span>${esc(kinds[a.kind]||a.kind)}</span><span>${a.character?esc(roles[a.role]):esc(a.ext||'')}</span></div><h3>${esc(a.title)}</h3>${a.character?`<p class="review-use">${a.character.actions.length} 个工程关联动作，可切换播放</p><div class="review-chips">${a.character.actions.slice(0,3).map(x=>`<span>${esc(x.label)}</span>`).join('')}${a.character.actions.length>3?'<span>…</span>':''}</div>`:`<p class="review-use">${esc(a.path)}</p>`}<div class="review-card-bottom"><span>${a.character?'查看角色与动作':'打开预览'}</span><span aria-hidden="true">↗</span></div></button>`).join('')||'<p class="review-empty">没有匹配的素材</p>'}</div>${list.length>limits[key]?`<button class="button secondary review-more" data-more="${key}">再显示 30 个（剩余 ${list.length-limits[key]}）</button>`:''}</section>`;
  }).join('');
  $('review-columns').querySelectorAll('[data-entry]').forEach(b=>b.onclick=()=>{const a=entries.find(a=>a.id===b.dataset.entry);if(a.fit)showFit(a.fit);else preview(a.path,a.character?.id);});
  $('review-columns').querySelectorAll('[data-entry]').forEach(b=>{const a=entries.find(a=>a.id===b.dataset.entry);if(!a.fit)return;const f=a.fit;b.querySelector('.review-use').textContent=`${f.spec.object} · ${f.status==='stale'?'证据过期':'当前证据'} · ${f.gaps.length} 个待满足项`;b.querySelector('.review-card-bottom span').textContent='查看能力、缺口与方案取舍';});
  $('review-columns').querySelectorAll('[data-more]').forEach(b=>b.onclick=()=>{limits[b.dataset.more]+=30;render();});
 }
 function showFit(f){
  let dialog=$('asset-fit-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='asset-fit-dialog';dialog.style.cssText='max-width:900px;width:90vw;max-height:85vh;overflow:auto;border:1px solid #ccd;border-radius:14px;padding:28px';document.body.append(dialog);}
  const s=f.spec;dialog.innerHTML=`<button class="button secondary" data-close style="float:right">关闭</button><h2>${esc(s.title)}</h2><p>${esc(s.object)} / ${esc(s.role)} · ${esc(s.use)}</p><p>原目标：${esc(s.goal_ref)} · ${f.status==='stale'?'来源已变化，结论需复核':'当前版本'}。资产已在游戏目录不代表品质通过。</p><h3>选材与实际能力</h3>${s.members.map(m=>`<p><strong>${esc(m.id)}</strong> · ${esc(m.path||'尚未下载')}<br>${m.capabilities.map(c=>`${esc(c.label)}：${esc(c.availability)} / ${esc(c.preview_type)} · ${esc(c.conditions)}`).join('<br>')}</p>`).join('')}<h3>目标覆盖与缺口</h3><table>${s.requirements.map(r=>`<tr><td style="padding:8px">${esc(r.description)}</td><td>${esc(r.coverage)}</td><td style="padding:8px">${esc(r.notes)}</td></tr>`).join('')}</table><h3>组合取舍</h3>${(s.tradeoffs||[]).map(t=>`<p>${esc(t)}</p>`).join('')}<h3>原始来源</h3>${s.sources.map(o=>`<p><a href="${esc(o.url)}" target="_blank" rel="noopener noreferrer">${esc(o.title)}</a> · ${esc(o.version)} · ${esc(o.price)} · ${esc(o.license)}</p>`).join('')}`;dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.showModal();
 }
 $('review-refresh').onclick=async()=>{const b=$('review-refresh');b.disabled=true;try{await refreshLibrary(true);render();}catch(e){toast(e.message);}finally{b.disabled=false;}};
 ['review-search','review-role','review-kind'].forEach(id=>$(id).addEventListener(id==='review-search'?'input':'change',()=>{limits={candidate:30,game:30};render();}));
 window.addEventListener('workbench:assets-ready',render);
 return {activate:render};
}
