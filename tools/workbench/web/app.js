import {api} from './session.js';
import {allowMotionNavigation,prepareMotion,attachMotionReview} from './motion-review.js';
import {modelPreview,modelThumbnail,disposeThumbnails,canPreviewModel} from './viewer.js';
import {attachMediaViewport} from './media-viewport.js';
import {createTagManager} from './asset-tags.js';
const $=id=>document.getElementById(id);
const paths={box:'m12 3 9 5v8l-9 5-9-5V8Zm0 9 9-4M3 8l9 4v9M7.5 5.5l9 5',layers:'m12 3 9 5-9 5-9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5',chevron:'m9 5 6 7-6 7',search:'M21 21l-5-5M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16',star:'m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9Z',folder:'M3 7V5h6l2 2h10v13H3Zm0 3h18',image:'M3 4h18v16H3ZM3 16l6-6 5 6 3-3 4 4M16 8h.01',music:'M9 18V5l11-2v13M9 8l11-2M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6M17 19a3 3 0 1 0 0-6 3 3 0 0 0 0 6',spark:'m12 2 2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4ZM19 2v4M17 4h4',play:'m8 4 12 8-12 8Z',pause:'M8 4v16M16 4v16',refresh:'M20 7a8 8 0 0 0-14-2L3 8M3 3v5h5M4 17a8 8 0 0 0 14 2l3-3M21 21v-5h-5',list:'M9 5h12M9 12h12M9 19h12M3 5h.01M3 12h.01M3 19h.01',grid:'M3 3h7v7H3ZM14 3h7v7h-7ZM3 14h7v7H3ZM14 14h7v7h-7Z',expand:'M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5',copy:'M8 8h13v13H8ZM16 8V3H3v13h5',help:'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20M9 8a3 3 0 1 1 5 2.2c-2 1-2 1.8-2 3M12 17h.01',close:'m6 6 12 12M6 18 18 6',film:'M3 4h18v16H3ZM7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4',file:'M14 2H4v20h16V8ZM14 2v6h6',camera:'M8 6l2-3h4l2 3h5v14H3V6ZM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8',reset:'M3 10a9 9 0 1 1 2 8M3 3v7h7',bone:'M5 3a2 2 0 0 1 3 3l10 10a2 2 0 1 1 0 4 2 2 0 1 1-4-2L4 8a2 2 0 1 1-1-3 2 2 0 0 1 2-2',volume:'M3 9h4l5-4v14l-5-4H3ZM16 8a6 6 0 0 1 0 8M19 5a10 10 0 0 1 0 14',code:'m8 5-6 7 6 7M16 5l6 7-6 7',check:'m4 12 5 5L20 6'};
const icon=name=>`<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.file}"/></svg>`;
function icons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
icons();
const types={all:['全部资产','layers'],model:['3D 模型','box'],animation:['动画','film'],image:['2D 与贴图','image'],audio:['音效与音乐','music'],vfx:['视觉特效','spark'],engine:['引擎资源','code'],other:['其他资产','file']};
const kindName=k=>types[k]?.[0]||({texture:'特殊贴图',video:'视频'})[k]||'文件';
const kindIcon=k=>types[k]?.[1]||'file';
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const formatSize=b=>b>=1048576?(b/1048576).toFixed(2)+' MB':b>=1024?(b/1024).toFixed(1)+' KB':b+' B';
const time=t=>Number.isFinite(t)?`${Math.floor(t/60)}:${(t%60).toFixed(1).padStart(4,'0')}`:'0:00.0';
let data,scope='local',category='all',folder='',favoriteOnly=false,query='',selected,filtered=[],favorites=new Set(),cleanup=()=>{},generation=0,thumbnails=new Map(),thumbQueue=[],thumbBusy=false,toastTimer;
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),2300);}
const urlFor=path=>(data?.assetBase||'/asset/current/')+path.split('/').map(encodeURIComponent).join('/');
let libraryActive=true;
const fbxRigs=new Map();
const characterChoices=new Map(),actionChoices=new Map();
const tags=createTagManager({getData:()=>data,getSelected:()=>selected,getFiltered:()=>filtered,onChange:()=>render(),onSelect:path=>selectAsset(data.assets.find(a=>a.path===path)),refresh:()=>load(true),escape,toast});
function matchesCategory(a,c){if(c==='all')return true;if(c==='animation')return a.kind==='animation'||!!a.animations?.length;if(c==='image')return ['image','texture'].includes(a.kind);if(c==='other')return ['other','video'].includes(a.kind);return a.kind===c;}
function writeFavorites(){try{localStorage.setItem('asset-favorites:'+data.projectId,JSON.stringify([...favorites]));}catch{toast('浏览器未允许保存收藏，本次会话仍可使用');}}
const scopeName=()=>({local:'全部文件',candidate:'候补素材',game:'游戏应用'}[scope]);
const inScope=a=>!a.previewCopy&&(scope==='local'||a.location===scope);
function nav(){
 $('usage-navigation').innerHTML=[['local','全部文件',data.assets.filter(a=>!a.previewCopy).length],['candidate','候补素材',data.assets.filter(a=>!a.previewCopy&&a.location==='candidate').length],['game','游戏应用',data.assets.filter(a=>!a.previewCopy&&a.location==='game').length]].map(([id,name,n])=>`<button class="side-item ${scope===id?'active':''}" data-scope="${id}" aria-label="${name}"><span>${icon(id==='game'?'check':'folder')}</span><span>${name}</span><span class="count">${n}</span></button>`).join('');
 $('usage-navigation').querySelectorAll('button').forEach(b=>b.onclick=async()=>{if(!await allowMotionNavigation())return;scope=b.dataset.scope;category='all';folder='';favoriteOnly=false;query='';$('search').value='';tags.clear();render();const target=filtered.find(x=>x.id===selected?.id)||filtered[0];if(target)selectAsset(target);});
 $('usage-audit').textContent='按 game 文件夹内外归类，角色动作按绑定清单展示。';
 tags.renderNav();
 $('categories').innerHTML=Object.entries(types).map(([key,[name,ic]])=>{const n=data.assets.filter(a=>inScope(a)&&matchesCategory(a,key)).length;return `<button class="side-item ${category===key&&!folder&&!favoriteOnly?'active':''}" data-category="${key}" aria-label="${name}"><span>${icon(ic)}</span><span>${name}</span><span class="count">${n}</span></button>`;}).join('');
 $('categories').querySelectorAll('button').forEach(b=>b.onclick=()=>{category=b.dataset.category;folder='';favoriteOnly=false;render();});
 const roots=[...new Set(data.assets.filter(inScope).map(a=>a.path.split('/')[0]))];
 $('folders').innerHTML=roots.map(p=>`<button class="side-item folder-item ${folder===p?'active':''}" data-folder="${escape(p)}"><span>${icon('folder')}</span><span>${escape(p)}</span></button>`).join('');
 $('folders').querySelectorAll('button').forEach(b=>b.onclick=()=>{folder=b.dataset.folder;category='all';favoriteOnly=false;render();});
 $('favorites').classList.toggle('active',favoriteOnly);$('fav-count').textContent=favorites.size;
}
function card(a){const active=a.id===selected?.id;let thumb='';
 if(thumbnails.has(a.id))thumb=`<img alt="" src="${thumbnails.get(a.id)}">`;
 else if(a.kind==='image')thumb=`<img loading="lazy" alt="" class="${a.width&&a.width<=32?'pixel':''}" src="${a.url}">`;
 else if(a.kind==='vfx'&&a.texture)thumb=`<img alt="" src="${urlFor(a.texture)}" style="filter:drop-shadow(0 0 12px ${escape(a.color)}80)">`;
 else if(a.kind==='audio')thumb=`<canvas class="audio-thumb" data-url="${escape(a.url)}" aria-label="音频波形"></canvas>`;
 else thumb=icon(kindIcon(a.kind));
 return `<button class="asset-card ${active?'selected':''}" data-id="${a.id}" aria-pressed="${active}" aria-label="预览 ${escape(a.title)}"><div class="thumb ${a.kind}"><span class="file-badge">${a.ext}</span>${favorites.has(a.id)?`<span class="card-star">${icon('star')}</span>`:''}${thumb}${a.animations?.length?`<span class="anim-badge">${a.animations.length} 动作</span>`:a.kind==='vfx'?'<span class="anim-badge">演示模拟</span>':''}</div><div class="card-body"><span class="card-title">${escape(a.title)}</span><span class="card-meta"><span class="card-type"><i class="type-dot ${a.kind}"></i>${a.kind==='model'?'3D 模型':a.kind==='audio'?'音效':a.kind==='image'?'2D 图像':kindName(a.kind)}</span><span>${formatSize(a.bytes)}</span></span><span class="card-tags"><span class="badge">${a.location==='game'?'游戏应用':'候补素材'}</span>${tags.cardTags(a)}</span></div></button>`;
}
function render(){if(!data)return;nav();filtered=data.assets.filter(a=>inScope(a)&&tags.matches(a)&&matchesCategory(a,category)&&(!folder||a.path.startsWith(folder+'/'))&&(!favoriteOnly||favorites.has(a.id))&&[a.title,a.path,...a.tags].join(' ').toLowerCase().includes(query.toLowerCase()));
 const sort=$('sort').value;if(sort==='name')filtered.sort((a,b)=>a.title.localeCompare(b.title,'zh'));if(sort==='size')filtered.sort((a,b)=>b.bytes-a.bytes);if(sort==='recent')filtered.sort((a,b)=>b.modified-a.modified);
 $('view-title').firstChild.textContent=favoriteOnly?'我的收藏':folder||(scopeName()+' · '+types[category][0]);$('total-count').textContent=filtered.length;$('result-count').textContent=`${filtered.length} 个资产${query?' · 搜索结果':''}`;
 $('disk-summary').textContent=`${filtered.length} 个资产 · ${formatSize(filtered.reduce((sum,a)=>sum+a.bytes,0))}`;
 $('asset-grid').innerHTML=filtered.map(card).join('');$('empty').hidden=!!filtered.length;$('asset-grid').querySelectorAll('.asset-card').forEach(b=>b.onclick=()=>selectAsset(data.assets.find(a=>a.id===b.dataset.id)));
 for(const a of filtered){if(canPreviewModel(a)&&!thumbnails.has(a.id)&&!thumbQueue.some(x=>x.id===a.id))thumbQueue.push(a);}
 runThumbnails();drawAudioThumbs();
}
async function runThumbnails(){if(thumbBusy)return;thumbBusy=true;while(thumbQueue.length){const a=thumbQueue.shift();if(thumbnails.has(a.id))continue;try{const image=await modelThumbnail(a,metadata=>{if(a.ext==='FBX'){Object.assign(a,metadata);nav();}});thumbnails.set(a.id,image);const node=$('asset-grid').querySelector(`[data-id="${a.id}"] .thumb`);if(node){node.querySelector(':scope > svg')?.remove();const img=new Image();img.alt='';img.src=image;node.append(img);}}catch(e){console.warn('Thumbnail unavailable:',a.name,e.message);}}thumbBusy=false;}
const waves=new Map();let decoding;
async function waveform(asset){if(waves.has(asset.url))return waves.get(asset.url);decoding??=new AudioContext();const buf=await decoding.decodeAudioData(await(await fetch(asset.url)).arrayBuffer());const samples=buf.getChannelData(0),count=90,peaks=[];for(let i=0;i<count;i++){let peak=0;const start=Math.floor(i*samples.length/count),end=Math.floor((i+1)*samples.length/count);for(let j=start;j<end;j++)peak=Math.max(peak,Math.abs(samples[j]));peaks.push(peak);}const result={peaks,duration:buf.duration,sampleRate:buf.sampleRate,channels:buf.numberOfChannels};waves.set(asset.url,result);return result;}
function drawWave(canvas,peaks,progress=0){const w=canvas.clientWidth||200,h=canvas.clientHeight||56,dpr=devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);const max=Math.max(...peaks,.001);peaks.forEach((v,i)=>{const bh=Math.max(2,v/max*(h-8));ctx.fillStyle=i/peaks.length<progress?'#1749ee':'#91a8e5';ctx.fillRect(i*w/peaks.length,(h-bh)/2,Math.max(1,w/peaks.length-2),bh);});canvas.dataset.decoded='true';}
async function drawAudioThumbs(){for(const canvas of $('asset-grid').querySelectorAll('.audio-thumb')){try{const a=data.assets.find(x=>x.url===canvas.dataset.url),wave=await waveform(a);if(canvas.isConnected)drawWave(canvas,wave.peaks);}catch{canvas.replaceWith(document.createTextNode('音频'));}}}
function dataRow(k,v){return `<div class="data-row"><span>${escape(k)}</span><strong>${escape(v)}</strong></div>`;}
async function selectAsset(a,characterId,keepScroll=false){
 if(!a||!await allowMotionNavigation())return;if(a.ext==='FBX')a={...a,rig:fbxRigs.get(a.path)};
 const characters=(data.characters||[]).filter(c=>c.model===a.path);
 const character=characters.find(c=>c.id===(characterId||characterChoices.get(a.path)))||characters[0];
 if(character)characterChoices.set(a.path,character.id);
 const actionIndex=character?Math.min(actionChoices.get(character.id)??0,character.actions.length-1):-1;
 const action=character?.actions[actionIndex];
 let visual=action?data.assets.find(x=>x.path===action.path):a;
 if(visual&&(visual.previewExt||visual.ext)==='FBX')visual={...visual,rig:fbxRigs.get(visual.path)};
 cleanup();cleanup=()=>{};const gen=++generation;selected=a;if(!keepScroll)$('inspector-content').scrollTop=0;
 $('asset-grid').querySelectorAll('.asset-card').forEach(b=>{const active=b.dataset.id===a.id;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',active);});
 $('asset-title').textContent=character?.title||a.title;$('asset-subtitle').textContent=action?.label||a.name;
 $('asset-badges').innerHTML=`<span class="badge">${a.location==='game'?'游戏应用':'候补素材'}</span><span class="badge blue">${character?'角色与动作':escape(a.ext)}</span>`;
 $('file-path').textContent=a.path;$('favorite-asset').classList.toggle('active',favorites.has(a.id));$('preview').className='preview';$('preview').style.background='';$('preview').innerHTML='';$('preview-controls').innerHTML='';
 let rows=dataRow('目录归属',a.location==='game'?'工程内容目录内':'工程内容目录外')+dataRow('文件格式',a.ext)+dataRow('文件大小',formatSize(a.bytes));
 if(character)rows+=dataRow('工程关联动作',character.actions.length)+dataRow('当前动作',action?.label||'模型静态展示')+(action?dataRow('动作文件',action.path)+dataRow('关联依据',({static_single_node_reference:'引擎组件直接绑定',static_animbp_dependency_not_runtime_observation:'动画蓝图静态引用；尚未观察运行',project_readonly_available_set_not_observed_playback:'工程声明可用；尚未观察运行',explicit_manifest:'显式绑定清单'})[action.basis]||action.basis):'');
 if(a.width)rows+=dataRow('分辨率',`${a.width} × ${a.height}`);if(visual?.previewPath)rows+=dataRow('预览文件',visual.previewPath);$('details').innerHTML=rows;tags.renderEditor();
 const validSource=/^https:\/\//.test(a.source||'');$('source').innerHTML=dataRow('作者',a.author)+dataRow('许可',a.license)+(validSource?`<p><a href="${escape(a.source)}" target="_blank" rel="noopener noreferrer">查看原始素材页面 ↗</a></p>`:'<p>此文件来自项目目录，尚未登记外部来源。</p>');
 const holder=$('character-controls');holder.hidden=!character;
 if(character){
  holder.innerHTML=`${characters.length>1?`<label for="character-choice">游戏角色</label><select id="character-choice" aria-label="游戏角色">${characters.map(c=>`<option value="${escape(c.id)}" ${c.id===character.id?'selected':''}>${escape(c.title)}</option>`).join('')}</select>`:''}<label for="character-action">展示动画 · ${character.actions.length} 个工程关联动作</label><select id="character-action" aria-label="展示动画"><option value="-1" ${actionIndex===-1?'selected':''}>模型静态展示</option>${character.actions.map((x,i)=>`<option value="${i}" ${i===actionIndex?'selected':''}>${escape(x.label)}</option>`).join('')}</select>${character.note?`<p>${escape(character.note)}</p>`:''}`;
  $('character-choice')?.addEventListener('change',async e=>{if(!await allowMotionNavigation()){e.target.value=character.id;return;}selectAsset(a,e.target.value,true);});
  $('character-action').onchange=async e=>{if(!await allowMotionNavigation()){e.target.value=String(actionIndex);return;}actionChoices.set(character.id,+e.target.value);selectAsset(a,character.id,true);};
 }
 if(visual&&canPreviewModel(visual)){
  $('preview').innerHTML='<div class="preview-loading" style="position:absolute;inset:0">正在加载模型…</div>';
  let prepared;
  try{prepared=await prepareMotion(visual,character);}catch(error){prepared={error:error.message};}
  if(gen!==generation)return;
  const api=await modelPreview($('preview'),visual,{ready(api,clips){if(gen!==generation)return;
   $('details').insertAdjacentHTML('afterbegin',dataRow('骨骼',api.bones)+dataRow('动画片段',clips.length));
   if(visual.ext==='FBX'){visual.bones=api.bones;visual.animations=clips.map(c=>({name:c.name,duration:c.duration}));nav();}
   modelControls(api,clips,visual);if(character&&$('clip')&&clips.length===1)$('clip').hidden=true;
   if(clips.length)attachMotionReview($('preview-controls'),visual,character,clips,$('clip'),prepared,()=>selectAsset(a,character?.id,true));
   if((visual.previewExt||visual.ext)==='FBX'&&(api.skeletonOnly||visual.rig))fbxRigControls(visual,()=>selectAsset(a,character?.id,true));
  },error(){if(gen===generation&&visual.ext==='FBX'&&visual.rig)fbxRigControls(visual,()=>selectAsset(a,character?.id,true));},tick(t){if(gen!==generation)return;const slider=$('animation-time');if(slider&&!slider.matches(':active'))slider.value=t;if($('animation-current'))$('animation-current').textContent=time(t);}});
  if(gen!==generation)api.dispose();else cleanup=()=>api.dispose();
 }else if(!character&&a.kind==='image'){cleanup=imagePreview(a);}else if(!character&&a.kind==='audio'){cleanup=audioPreview(a,gen);}else if(!character&&a.kind==='vfx'){cleanup=vfxPreview(a,gen);}else if(!character&&a.kind==='video'){cleanup=videoPreview(a);}else{
  $('preview').innerHTML=`<div class="preview-error">${icon(kindIcon(a.kind))}<strong>${character?'当前动作预览尚未同步':'此格式暂无预览'}</strong><p>${escape(visual?.previewIssue||'需要从引擎导出并关联当前文件的预览副本。')}</p></div>`;
 }
}

function fbxRigControls(asset,reopen){
 const holder=document.createElement('div');holder.className='controls';
 const choices=data.assets.filter(a=>a.ext==='FBX'&&a.path!==asset.path&&a.meshes!==0);
 holder.innerHTML=`<label class="control-note" for="fbx-rig">角色预览（仅同名同层级骨架）</label><div class="play-row"><select id="fbx-rig" aria-label="选择 FBX 预览角色"><option value="">仅显示原骨架</option>${choices.map(a=>`<option value="${escape(a.path)}" ${a.path===asset.rig?.path?'selected':''}>${escape(a.title)}</option>`).join('')}</select><button class="button secondary" id="apply-fbx-rig">应用</button></div><p class="control-note">动作文件不含角色网格时，可选带蒙皮的 FBX 一起播放；仅用于当前浏览会话。</p>`;
 $('preview-controls').prepend(holder);
 holder.querySelector('#apply-fbx-rig').onclick=async()=>{if(!await allowMotionNavigation()){holder.querySelector('#fbx-rig').value=asset.rig?.path||'';return;}const path=holder.querySelector('#fbx-rig').value;if(path)fbxRigs.set(asset.path,data.assets.find(a=>a.path===path));else fbxRigs.delete(asset.path);reopen();};
}
function modelControls(api,clips,a){
 const controls=$('preview-controls');controls.innerHTML=`<div class="controls">${clips.length?`<div class="play-row"><button class="play-toggle" id="animation-play" aria-label="暂停动画">${icon('pause')}</button><select id="clip" aria-label="选择动画">${clips.map((c,i)=>`<option value="${i}">${escape(c.name||'动画 '+(i+1))}</option>`).join('')}</select><select id="speed" class="speed-select" aria-label="动画速度"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></div><div class="timeline-row"><span id="animation-current">0:00.0</span><input id="animation-time" type="range" min="0" max="${clips[0].duration}" step="0.001" value="0" aria-label="动画时间轴"><span id="animation-duration">${time(clips[0].duration)}</span></div>`:'<p class="control-note">静态模型 · 拖动旋转，滚轮缩放，右键平移</p>'}<div class="display-controls">${clips.length?'<button class="toggle-chip active" id="follow-character">跟随角色</button>':''}<button class="toggle-chip" id="wireframe">线框</button>${api.bones?`<button class="toggle-chip ${api.skeletonOnly?'active':''}" id="skeleton">骨骼</button>`:''}<button class="toggle-chip active" id="ground-grid">网格</button><button class="toggle-chip" id="auto-rotate">自动旋转</button><button class="toggle-chip" id="recenter" aria-label="复位镜头">${icon('reset')}</button><button class="toggle-chip" id="capture" aria-label="保存预览截图">${icon('camera')}</button></div><details class="parts"><summary>显示设置与模型部件 · ${api.meshes.length}</summary><label>曝光 <input id="exposure" type="range" min="0.2" max="2.5" step="0.05" value="1.15" aria-label="曝光"></label><label>背景 <input id="background-color" type="color" value="#f4f6fc" aria-label="预览背景颜色"></label>${api.meshes.map((m,i)=>`<label><input type="checkbox" checked data-part="${i}">${escape(m.name||'Mesh '+(i+1))}</label>`).join('')}</details></div>`;
 if(api.note)controls.insertAdjacentHTML('beforeend',`<p class="control-note">${escape(api.note)}</p>`);
 $('preview').insertAdjacentHTML('beforeend',`<div class="preview-top"><span>PERSPECTIVE</span><span>Y ↑</span></div><div class="preview-caption">拖动旋转 · 滚轮缩放</div>`);
 if(clips.length){$('follow-character').onclick=()=>{const on=$('follow-character').classList.toggle('active');api.follow(on);$('follow-character').textContent=on?'跟随角色':'完整轨迹';};$('animation-play').onclick=()=>{const paused=api.play();$('animation-play').innerHTML=icon(paused?'play':'pause');$('animation-play').setAttribute('aria-label',paused?'播放动画':'暂停动画');};$('clip').onchange=e=>{const d=api.selectClip(+e.target.value);$('animation-time').max=d;$('animation-duration').textContent=time(d);$('animation-play').innerHTML=icon('pause');$('animation-play').setAttribute('aria-label','暂停动画');};$('animation-time').oninput=e=>api.setTime(+e.target.value);$('speed').onchange=e=>api.setSpeed(+e.target.value);}
 for(const [id,fn] of [['wireframe','wireframe'],['skeleton','skeleton'],['ground-grid','grid'],['auto-rotate','rotate']])if($(id))$(id).onclick=()=>{const on=$(id).classList.toggle('active');$(id).setAttribute('aria-pressed',on);api[fn](on);};
 $('recenter').onclick=()=>api.reset();$('capture').onclick=()=>{const link=document.createElement('a');link.href=api.screenshot();link.download=a.name+'.png';link.click();toast('预览截图已导出');};$('exposure').oninput=e=>api.exposure(+e.target.value);$('background-color').oninput=e=>api.background(e.target.value);controls.querySelectorAll('[data-part]').forEach(el=>el.onchange=()=>api.part(+el.dataset.part,el.checked));
}
function imagePreview(a){
 const img=document.createElement('img');img.alt=a.title;img.draggable=false;
 if(a.width&&a.width<=32)img.className='pixel';
 img.onload=()=>{img.dataset.loaded='true';};img.src=a.url;
 const viewport=attachMediaViewport($('preview'),img,$('preview-controls'),{label:a.title+' 图片预览画布',checker:true});
 return ()=>{img.onload=null;viewport.dispose();};
}
function videoPreview(a){
 const video=document.createElement('video');video.src=a.url;video.controls=true;video.preload='metadata';video.setAttribute('aria-label',a.title+' 视频');
 const viewport=attachMediaViewport($('preview'),video,$('preview-controls'),{label:a.title+' 视频预览画布',background:'#111d49',nativeVideo:true});
 return ()=>{viewport.dispose();video.pause();video.removeAttribute('src');video.load();};
}
function audioPreview(a,gen){let active=true,raf;const audio=document.createElement('audio');audio.src=a.url;audio.preload='metadata';audio.loop=true;audio.setAttribute('aria-label',a.title+' 音频');
 $('preview').innerHTML=`<div class="audio-stage">${icon('music')}<canvas id="audio-wave" aria-label="音频实际波形"></canvas><p id="audio-spec">正在解码音频…</p></div>`;$('preview').append(audio);
 $('preview-controls').innerHTML=`<div class="controls"><div class="play-row"><button id="audio-play" class="play-toggle" aria-label="播放音频">${icon('play')}</button><span style="flex:1;font-size:14px">${escape(a.title)}</span><button class="toggle-chip active" id="audio-loop" aria-pressed="true">循环</button></div><div class="timeline-row"><span id="audio-current">0:00.0</span><input id="audio-time" type="range" min="0" max="1" step="0.001" value="0" aria-label="音频进度"><span id="audio-duration">—</span></div><div class="play-row" style="margin-top:14px;color:var(--muted)">${icon('volume')}<input style="flex:1" id="audio-volume" type="range" min="0" max="1" step="0.01" value="0.65" aria-label="音量"><span style="font-size:13px" id="volume-label">65%</span></div></div>`;
 const viewport=attachMediaViewport($('preview'),$('preview').querySelector('.audio-stage'),$('preview-controls'),{label:a.title+' 音频波形画布'});
 audio.volume=.65;let wave;
 waveform(a).then(w=>{if(!active||gen!==generation)return;wave=w;drawWave($('audio-wave'),w.peaks);$('audio-spec').textContent=`${(w.sampleRate/1000).toFixed(1)} kHz · ${w.channels===1?'MONO':'STEREO'} · ${a.ext}`;$('audio-duration').textContent=time(w.duration);$('audio-time').max=w.duration;$('details').insertAdjacentHTML('afterbegin',dataRow('时长',w.duration.toFixed(3)+' 秒')+dataRow('采样率',w.sampleRate+' Hz'));}).catch(()=>{if(active)$('audio-spec').textContent='此编码无法在当前浏览器解码';});
 const sync=()=>{if(!active)return;const t=audio.currentTime;$('audio-current').textContent=time(t);if(!$('audio-time').matches(':active'))$('audio-time').value=t;if(wave)drawWave($('audio-wave'),wave.peaks,t/wave.duration);raf=requestAnimationFrame(sync);};raf=requestAnimationFrame(sync);
 $('audio-play').onclick=async()=>{if(audio.paused){try{await audio.play();if(!active)return;$('audio-play').innerHTML=icon('pause');$('audio-play').setAttribute('aria-label','暂停音频');}catch{toast('无法播放这个音频文件');}}else{audio.pause();$('audio-play').innerHTML=icon('play');$('audio-play').setAttribute('aria-label','播放音频');}};
 audio.onended=()=>{if(active){$('audio-play').innerHTML=icon('play');$('audio-play').setAttribute('aria-label','播放音频');}};$('audio-time').oninput=e=>audio.currentTime=+e.target.value;$('audio-loop').onclick=()=>{audio.loop=!audio.loop;$('audio-loop').classList.toggle('active',audio.loop);$('audio-loop').setAttribute('aria-pressed',audio.loop);};$('audio-volume').oninput=e=>{audio.volume=+e.target.value;$('volume-label').textContent=Math.round(audio.volume*100)+'%';};
 return ()=>{active=false;viewport.dispose();cancelAnimationFrame(raf);audio.pause();audio.removeAttribute('src');audio.load();};
}
function vfxPreview(a,gen){let alive=true,paused=false,frame,last=performance.now(),timeValue=0,speed=1,config,img;const canvas=document.createElement('canvas');canvas.setAttribute('aria-label',a.title+' 粒子演示');$('preview').classList.add('vfx-stage');$('preview').append(canvas);const ctx=canvas.getContext('2d');
 $('preview').insertAdjacentHTML('beforeend','<div class="preview-top"><span>粒子预览</span><span>模拟效果</span></div>');$('preview-controls').innerHTML=`<div class="controls"><div class="play-row"><button class="play-toggle" id="vfx-play" aria-label="暂停特效">${icon('pause')}</button><span style="flex:1;font-size:14px">粒子循环预览</span><select id="vfx-speed" class="speed-select" aria-label="特效速度"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select><button class="icon-button" id="vfx-reset" aria-label="重播特效">${icon('refresh')}</button></div><p class="control-note">贴图粒子预览，暂不支持 Niagara 等引擎特效。</p></div>`;
 $('vfx-play').onclick=()=>{paused=!paused;$('vfx-play').innerHTML=icon(paused?'play':'pause');$('vfx-play').setAttribute('aria-label',paused?'播放特效':'暂停特效');};$('vfx-speed').onchange=e=>speed=+e.target.value;$('vfx-reset').onclick=()=>{timeValue=0;paused=false;$('vfx-play').innerHTML=icon('pause');$('vfx-play').setAttribute('aria-label','暂停特效');};
 const viewport=attachMediaViewport($('preview'),canvas,$('preview-controls'),{label:a.title+' 特效预览画布',background:'#111d49'});
 fetch(a.url).then(r=>r.json()).then(c=>{if(!alive||gen!==generation)return;if(!['ember','magic','smoke','spark'].includes(c.mode)||typeof c.texture!=='string')throw Error('Invalid preset');config=c;img=new Image();img.src=urlFor(c.texture);img.onload=()=>{canvas.dataset.loaded='true';};}).catch(()=>{if(alive)toast('特效配置无法读取');});
 function tick(now){if(!alive)return;const dt=Math.min((now-last)/1000,.05);last=now;if(!paused)timeValue+=dt*speed;const w=canvas.clientWidth,h=canvas.clientHeight,dpr=devicePixelRatio||1;if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  if(config&&img?.complete&&img.naturalWidth){const smoke=config.mode==='smoke';ctx.globalCompositeOperation=smoke?'source-over':'lighter';const count=Math.min(100,Math.max(1,config.count||60));for(let i=0;i<count;i++){const r=(Math.sin(i*127.1+311.7)*43758.5453)%1,seed=Math.abs(r),age=(timeValue*(.18+seed*.2)+i/count)%1,fade=Math.sin(age*Math.PI);let x,y,s,rot=timeValue*.4+i;
   if(config.mode==='magic'){const angle=i*2.399+timeValue*.45,rad=(.15+age*.8)*Math.min(w,h)*.35;x=w/2+Math.cos(angle)*rad;y=h*.5+Math.sin(angle)*rad*.6;s=9+seed*20;}
   else{x=w*.5+Math.sin(i*7.13)*(10+age*(smoke?70:95));y=h*.83-age*h*.7;s=smoke?30+age*65:config.mode==='spark'?8+seed*12:18+seed*28;}
   ctx.save();ctx.translate(x,y);ctx.rotate(rot);ctx.globalAlpha=fade*(smoke?.14:.58);ctx.drawImage(img,-s/2,-s/2,s,s);ctx.restore();}ctx.globalCompositeOperation='source-atop';ctx.globalAlpha=smoke?.2:.7;ctx.fillStyle=/^#[0-9a-f]{6}$/i.test(config.color)?config.color:'#dfb874';ctx.fillRect(0,0,w,h);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';canvas.dataset.time=timeValue.toFixed(2);}
  frame=requestAnimationFrame(tick);
 }frame=requestAnimationFrame(tick);return()=>{alive=false;viewport.dispose();cancelAnimationFrame(frame);};
}
async function load(refresh=false){if(!await allowMotionNavigation())return false;$('refresh').disabled=true;try{const response=await fetch('/api/assets?project='+encodeURIComponent('current'));if(!response.ok)throw Error('scan');const next=await response.json();if(refresh){thumbnails.clear();thumbQueue=[];}data=next;$('project-name').textContent=data.project;try{favorites=new Set(JSON.parse(localStorage.getItem('asset-favorites:'+data.projectId)||'[]'));}catch{favorites=new Set();}favorites=new Set([...favorites].filter(id=>data.assets.some(a=>a.id===id)));$('disk-summary').textContent=`${data.assets.length} 个资产 · ${formatSize(data.totalBytes)}`;$('scan-status').textContent='目录已同步';render();const target=filtered.find(a=>a.id===selected?.id)||filtered[0];if(target){selected=target;if(libraryActive)await selectAsset(target);}else{selected=null;tags.renderEditor();$('asset-title').textContent='选择一个资产';$('preview').textContent='此目录中暂无可识别资产';}window.dispatchEvent(new CustomEvent('workbench:assets-ready'));if(refresh)toast('目录已重新扫描');}catch(e){$('result-count').textContent='本地服务连接失败';toast('无法读取项目目录，请检查本地服务');console.error(e);}finally{$('refresh').disabled=false;}}
function clear(){scope='local';tags.clear();category='all';folder='';favoriteOnly=false;query='';$('search').value='';render();}
 $('search').oninput=e=>{query=e.target.value;render();};$('sort').onchange=render;$('favorites').onclick=()=>{favoriteOnly=!favoriteOnly;category='all';folder='';render();};$('favorite-asset').onclick=()=>{if(!selected)return;if(favorites.has(selected.id))favorites.delete(selected.id);else favorites.add(selected.id);writeFavorites();$('favorite-asset').classList.toggle('active',favorites.has(selected.id));$('favorite-asset').setAttribute('aria-label',favorites.has(selected.id)?'取消收藏当前资产':'收藏当前资产');render();};$('refresh').onclick=()=>load(true);$('clear-filter').onclick=clear;$('view-toggle').onclick=()=>{const on=$('asset-grid').classList.toggle('list');$('view-toggle').innerHTML=icon(on?'grid':'list');$('view-toggle').setAttribute('aria-label',on?'切换网格视图':'切换列表视图');drawAudioThumbs();};$('copy-path').onclick=async()=>{try{await navigator.clipboard.writeText(data.root.replace(/\\/g,'/')+'/'+selected.path);toast('已复制完整路径');}catch{toast('无法访问剪贴板，可从下方路径手动复制');}};$('expand').onclick=()=>{const on=$('inspector').classList.toggle('expanded');$('expand').innerHTML=icon(on?'close':'expand');$('expand').setAttribute('aria-label',on?'收起预览':'展开预览');};document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(x=>x.setAttribute('aria-selected',x===b));$('details').hidden=b.dataset.tab!=='details';$('source').hidden=b.dataset.tab!=='source';});$('close-dialog').onclick=$('dialog-done').onclick=()=>$('info-dialog').close();
 document.addEventListener('keydown',e=>{if(e.defaultPrevented||!libraryActive||e.target.closest('.pan-zoom')||e.target.matches('input,select,textarea')||document.querySelector('dialog[open]'))return;if(e.key==='/'){e.preventDefault();$('search').focus();}if(e.key==='Escape'&&$('inspector').classList.contains('expanded'))$('expand').click();if(['ArrowUp','ArrowDown'].includes(e.key)&&filtered.length){e.preventDefault();const current=filtered.findIndex(a=>a.id===selected?.id),next=(current+(e.key==='ArrowDown'?1:-1)+filtered.length)%filtered.length;selectAsset(filtered[next]);$('asset-grid').querySelector(`[data-id="${filtered[next].id}"]`)?.scrollIntoView({block:'nearest'});}});
 window.addEventListener('pagehide',()=>{cleanup();disposeThumbnails();decoding?.close();});load();

export function getLibraryData(){return data;}
export async function openLibraryAsset(path,characterId){
 const asset=data?.assets.find(a=>a.path===path);
 if(!asset){toast('资产尚未加载，请稍后再试');return;}
 if(!await allowMotionNavigation())return;clear();selectAsset(asset,characterId);
 if(characterId&&!$('inspector').classList.contains('expanded'))$('expand').click();
 $('asset-grid').querySelector('[data-id="'+asset.id+'"]')?.scrollIntoView({block:'nearest'});
}
export function setLibraryActive(active){
 if(active===libraryActive)return;libraryActive=active;
 if(!active){cleanup();cleanup=()=>{};generation++;}
 else if(data?.assets.length)selectAsset(selected||data.assets[0]);
}
export {icon,escape,toast,load as refreshLibrary};
