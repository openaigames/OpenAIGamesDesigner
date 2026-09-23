/* Project-local editor. Art choices remain authored data, never inferred approval. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), clone = value => JSON.parse(JSON.stringify(value));
  const states = {candidate:'候选方向', selected:'已选用方向', deferred:'暂缓'};
  let board = clone(window.MOODBOARD_DATA), expected = null, diskRevision = board.revision, dirty = false, busy = false;
  const originalIdentity = {id:board.id, scope:board.scope, assetId:board.assetId};
  function status(message, error=false) { $('status').textContent=message; $('status').classList.toggle('error',error); }
  function changed() { dirty=true; headings(); status('有未保存的修改；导出图片后更新项目中的图板版本。'); }
  function headings() {
    $('title-display').textContent=board.title; $('intent-display').textContent=board.intent;
    $('board-meta').textContent=(board.scope==='asset'?'资产板':'游戏主题')+' · '+states[board.status]+' · 已保存 v'+diskRevision+(dirty?' / 编辑中':'');
    document.title=board.title+' · Moodboard';
  }
  function node(tag, className, text) { const el=document.createElement(tag); if(className)el.className=className; if(text!==undefined)el.textContent=text; return el; }
  function bindField(label, value, update, multiline=false) {
    const wrap=node('label','',label), input=node(multiline?'textarea':'input');
    input.value=value||''; input.maxLength=multiline?2000:200; if(multiline)input.rows=2;
    input.addEventListener('input',()=>{update(input.value); changed();}); wrap.append(input); return wrap;
  }
  function action(label, callback) { const button=node('button','',label); button.type='button'; button.onclick=callback; return button; }
  function imageSource(ref) { return ref.data||ref.file; }
  function renderGallery() {
    $('gallery').replaceChildren(); $('supporting-gallery').replaceChildren(); let primaryIndex=0;
    board.references.forEach((ref,index)=>{
      const figure=node('figure',ref.role==='primary'&&primaryIndex++===0?'hero':''); figure.dataset.ref=ref.id;
      const open=action('',()=>{ $('large-image').src=imageSource(ref); $('large-image').alt=ref.title; $('large-caption').textContent=ref.id+' · '+ref.title+'\n'+ref.note+'\n不继承：'+ref.exclude; $('image-dialog').showModal(); });
      open.className='image-open'; open.setAttribute('aria-label','查看原图 '+ref.id);
      const img=node('img'); img.src=imageSource(ref); img.alt=ref.title;
      img.onerror=()=>{if(!figure.querySelector('.image-error'))figure.prepend(node('p','image-error','图片无法加载；请替换或恢复原文件。'));}; open.append(img);
      const caption=node('div','caption'), title=node('div','caption-title'), titleText=node('span','',ref.title), note=node('p','caption-note',ref.note);
      title.append(node('span','ref-id',ref.id),titleText);
      const source=node('a','source',ref.sourceLabel||'来源待补充');
      if(/^https?:\/\//.test(ref.sourceUrl)){source.href=ref.sourceUrl;source.target='_blank';source.rel='noopener noreferrer';}
      const details=node('details','reference-fields'); details.append(node('summary','','编辑图注与来源'));
      details.append(bindField('图片名称',ref.title,value=>{ref.title=value;titleText.textContent=value;}));
      details.append(bindField('借鉴点与入选理由',ref.note,value=>{ref.note=value;note.textContent=value;},true));
      details.append(bindField('不继承的内容',ref.exclude,value=>ref.exclude=value,true));
      details.append(bindField('来源说明',ref.sourceLabel,value=>{ref.sourceLabel=value;source.textContent=value;}));
      details.append(bindField('来源页面',ref.sourceUrl,value=>{ref.sourceUrl=value;source.removeAttribute('href');if(/^https?:\/\//.test(value))source.href=value;}));
      details.append(bindField('使用依据 / 未核实项',ref.usage,value=>ref.usage=value,true));
      const roleLabel=node('label','','参考职责'), role=node('select');
      for(const [value,text] of [['primary','主要风格参考'],['supporting','补充结构与细节']]){const opt=node('option','',text);opt.value=value;role.append(opt);} role.value=ref.role;
      role.onchange=()=>{ref.role=role.value;changed();renderGallery();};roleLabel.append(role);details.append(roleLabel);
      const checkLabel=node('label','check'), viewed=node('input'); viewed.type='checkbox';viewed.checked=ref.viewed;
      viewed.onchange=()=>{ref.viewed=viewed.checked;changed();};checkLabel.append(viewed,document.createTextNode('已实际查看这张原图'));details.append(checkLabel);
      const controls=node('div','card-actions');
      const move=delta=>{const next=index+delta;if(next>=0&&next<board.references.length){[board.references[index],board.references[next]]=[board.references[next],board.references[index]];changed();renderGallery();}};
      controls.append(action('前移',()=>move(-1)),action('后移',()=>move(1)));
      const replace=node('label','button','替换图片'), file=node('input');file.type='file';file.accept='image/png,image/jpeg,image/webp';
      file.onchange=async()=>{try{if(!file.files[0])return;const incoming=await readImage(file.files[0]);ref.data=incoming.data;delete ref.file;delete ref.sha256;ref.sourceLabel='用户替换 · '+file.files[0].name;ref.sourceUrl='';ref.usage='来源与使用依据待补充';ref.viewed=false;changed();renderGallery();status('已替换原图；请复核借鉴点、来源和色板。');}catch(error){status(error.message,true);}};replace.append(file);controls.append(replace);
      controls.append(action('移除',()=>{$('remove-dialog').showModal();$('confirm-remove').onclick=()=>{board.references=board.references.filter(item=>item.id!==ref.id);$('remove-dialog').close();changed();renderGallery();};}));
      caption.append(title,note,source,details,controls);figure.append(open,caption);$(ref.role==='primary'?'gallery':'supporting-gallery').append(figure);
    });
    $('supporting-title').hidden=!board.references.some(r=>r.role==='supporting');$('empty').hidden=board.references.length>0;
    $('image-count').textContent=board.references.length+' REFERENCES';
  }
  function renderPalette() {
    $('palette').replaceChildren();$('color-count').textContent=board.palette.length+' COLORS';
    board.palette.forEach((color,index)=>{
      const row=node('div','color-row');row.dataset.colorId=color.id;
      const picker=node('input');picker.type='color';picker.value=color.hex;picker.setAttribute('aria-label','颜色 '+(index+1)+' 取色器');
      const fields=node('div'), name=node('input','color-name'), hex=node('input','hex'), error=node('div','color-error');
      name.value=color.name;name.maxLength=80;name.setAttribute('aria-label','颜色 '+(index+1)+' 名称');hex.value=color.hex;hex.maxLength=7;hex.setAttribute('aria-label','颜色 '+(index+1)+' HEX');hex.setAttribute('aria-invalid','false');
      const commit=value=>{color.hex=value.toUpperCase();color.origin='用户自定义';picker.value=color.hex;hex.value=color.hex;hex.setAttribute('aria-invalid','false');error.textContent='';changed();};
      picker.oninput=()=>commit(picker.value);
      hex.oninput=()=>{if(/^#[0-9a-fA-F]{6}$/.test(hex.value.trim()))commit(hex.value.trim());else{hex.setAttribute('aria-invalid','true');error.textContent='请输入 # 加六位十六进制色值；尚未更改已存颜色。';}};
      name.oninput=()=>{color.name=name.value;changed();};
      fields.append(name,hex,action('移除此色',()=>{if(board.palette.length===1)return status('至少保留一个色槽。',true);board.palette.splice(index,1);changed();renderPalette();}));
      row.append(picker,fields,error);$('palette').append(row);
    });
  }
  function render() {
    headings();$('title').value=board.title;$('intent').value=board.intent;$('selection').value=board.status;$('selection-basis').value=board.selectionBasis;
    for(const el of document.querySelectorAll('[data-direction]'))el.value=board.direction[el.dataset.direction]||'';
    $('parent-note').textContent=board.parent?'关联主题 '+board.parent.id+' / v'+board.parent.revision+'。更新主题后复核继承关系，不自动替换本板。':'当前未绑定主题板版本。';
    renderGallery();renderPalette();
  }
  function validate(d) {
    if(!d||d.schemaVersion!==2||Object.entries(originalIdentity).some(([key,value])=>d[key]!==value))throw Error('配置属于另一图板或格式版本不符；当前图板未覆盖。');
    if(typeof d.title!=='string'||!d.title.trim()||d.title.length>200||/[\r\n]/.test(d.title)||!states[d.status]||typeof d.intent!=='string'||typeof d.selectionBasis!=='string'||!d.direction||Array.isArray(d.direction)||typeof d.direction!=='object')throw Error('方向说明不完整。');
    if(Object.values(d.direction).some(v=>typeof v!=='string'||v.length>2000))throw Error('方向摘要格式无效。');
    const validId=value=>typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(value);
    if(d.parent!==null&&(!d.parent||!validId(d.parent.id)||d.parent.id===d.id||!Number.isSafeInteger(d.parent.revision)||d.parent.revision<0))throw Error('主题关联需要有效标识与版本。');
    if(d.status==='selected'&&!d.selectionBasis.trim())throw Error('请记录实际选用或委托依据。');
    if(!Array.isArray(d.palette)||d.palette.length<1||d.palette.length>12||d.palette.some(c=>!/^#[0-9a-fA-F]{6}$/.test(c.hex)||typeof c.name!=='string'))throw Error('色板配置无效。');
    if(!Array.isArray(d.references)||d.references.length>40||d.references.some(r=>!r.id||(!r.data&&!r.file)||!['primary','supporting'].includes(r.role)||typeof r.viewed!=='boolean'))throw Error('参考图配置无效。');
    for(const group of [d.references,d.palette])if(group.some(x=>!validId(x.id))||new Set(group.map(x=>x.id)).size!==group.length)throw Error('配置中存在无效或重复标识。');
    for(const ref of d.references){
      if(['title','note','exclude','sourceLabel','sourceUrl','usage'].some(k=>typeof ref[k]!=='string'||ref[k].length>2000))throw Error('参考说明字段缺失或过长。');
      if(ref.sourceUrl&&!/^https?:\/\//.test(ref.sourceUrl))throw Error('来源页面需使用 http/https 链接。');
      if(ref.data){if(!/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(ref.data))throw Error('内嵌图片格式无效。');}
      else if(typeof ref.file!=='string'||/^[\/\\]|^[a-zA-Z]+:/.test(ref.file)||ref.file.includes('\\')||ref.file.split('/').includes('..'))throw Error('原图须使用图板内的相对文件路径。');
    }
    return d;
  }
  const asData=file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('无法读取文件'));reader.readAsDataURL(file);});
  async function readImage(file) {
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>20*1024*1024)throw Error('请选择不超过 20 MB 的 PNG、JPEG 或 WebP。');
    const data=await asData(file);await window.moodboardLoadImage(data);return {data};
  }
  function download(blob,name) { const url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000); }
  async function portable(snapshot) {
    for(const ref of snapshot.references){if(!ref.data){const response=await fetch(ref.file);if(!response.ok)throw Error('无法备份原图 '+ref.id);ref.data=await asData(await response.blob());}delete ref.file;}
    return snapshot;
  }
  function freeze(value) {busy=value;for(const el of document.querySelectorAll('button,input,textarea,select'))el.disabled=value;}
  $('title').oninput=e=>{board.title=e.target.value;changed();};$('intent').oninput=e=>{board.intent=e.target.value;changed();};
  $('selection').onchange=e=>{board.status=e.target.value;changed();};$('selection-basis').oninput=e=>{board.selectionBasis=e.target.value;changed();};
  for(const el of document.querySelectorAll('[data-direction]'))el.oninput=()=>{board.direction[el.dataset.direction]=el.value;changed();};
  $('add-color').onclick=()=>{if(board.palette.length>=12)return status('工具最多提供 12 个色槽。',true);board.palette.push({id:'c-'+crypto.randomUUID(),name:'新增颜色',hex:'#808080',origin:'编辑占位'});changed();renderPalette();};
  $('close-image').onclick=()=>$('image-dialog').close();$('cancel-remove').onclick=()=>$('remove-dialog').close();
  $('image-upload').onchange=async event=>{
    const files=Array.from(event.target.files);event.target.value='';freeze(true);
    try{if(board.references.length+files.length>40)throw Error('工具最多容纳 40 张参考；可按不同方向拆板。');const incoming=[];
      for(const file of files)incoming.push({id:'r-'+crypto.randomUUID().slice(0,13),...(await readImage(file)),title:file.name,note:'借鉴点待补充',exclude:'',sourceLabel:'用户提供 · '+file.name,sourceUrl:'',usage:'外部来源与使用依据待核实',role:'primary',viewed:false});
      board.references.push(...incoming);changed();renderGallery();status('已加入 '+incoming.length+' 张图片；请实际查看并补充借鉴点。');
    }catch(error){status(error.message,true);}finally{freeze(false);}
  };
  $('config-upload').onchange=async event=>{
    const file=event.target.files[0];event.target.value='';if(!file)return;
    try{if(file.size>80*1024*1024)throw Error('编辑数据超过 80 MB。');const incoming=validate(JSON.parse(await file.text()));board=clone(incoming);board.revision=diskRevision;dirty=true;render();status('已载入编辑数据；保存时将建立新版本，不覆盖历史版本。');}catch(error){status('导入失败：'+error.message,true);}
  };
  $('backup').onclick=async()=>{freeze(true);try{validate(board);const data=await portable(clone(board));download(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),board.id+'-editable.json');status('已发起包含原图的编辑数据下载；尚未更新 Art Direction。');}catch(error){status(error.message,true);}finally{freeze(false);}};
  $('export').onclick=async()=>{
    if(document.querySelector('.hex[aria-invalid=true]'))return status('请先修正无效 HEX，再导出。',true);
    freeze(true);let sent=false;
    try{
      const snapshot=validate(clone(board));snapshot.revision=diskRevision+1;
      if(snapshot.references.some(r=>!r.viewed))throw Error('请查看各张原图，并在图注编辑中标记已实际查看。');
      status('正在整理当前参考与色板…');const png=await window.renderMoodboardPNG(snapshot);
      if(!window.MOODBOARD_SESSION){
        download(await(await fetch(png)).blob(),snapshot.id+'-v'+snapshot.revision+'.png');
        download(new Blob([JSON.stringify(await portable(snapshot),null,2)],{type:'application/json'}),snapshot.id+'-v'+snapshot.revision+'.json');
        status('已发起整图和编辑数据下载。当前为文件模式，Art Direction 尚未更新；用本地编辑命令打开后导入并保存。');return;
      }
      sent=true;
      const response=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json','X-Moodboard-Token':window.MOODBOARD_SESSION},body:JSON.stringify({board:snapshot,png,expected})});
      const result=await response.json();if(!response.ok)throw Error(result.error||'保存未完成');
      board=result.board;diskRevision=board.revision;expected=result.expected;dirty=false;render();
      $('saved-image').href=result.png;$('saved-result').hidden=false;showWarnings(result.warnings);
      status('整图和编辑数据 v'+diskRevision+' 已保存，Art Direction 已更新。选用状态保持为“'+states[board.status]+'”。');
    }catch(error){status('未完成导出：'+error.message.replace(/[。.]$/,'')+'。'+(sent?'若连接中断，请先备份当前编辑数据，再重新打开核对磁盘版本。':''),true);}finally{freeze(false);}
  };
  function showWarnings(items=[]) {$('warnings').textContent=items.join('\n');$('warnings').hidden=!items.length;}
  window.addEventListener('beforeunload',event=>{if(dirty||busy){event.preventDefault();event.returnValue='';}});
  render();
  if(window.MOODBOARD_SESSION){freeze(true);fetch('/api/board').then(async response=>{if(!response.ok)throw Error('无法读取项目图板');return response.json();}).then(result=>{board=validate(result.board);expected=result.expected;diskRevision=board.revision;render();showWarnings(result.warnings);status('已读取项目保存版本。编辑后可导出整图并更新 Art Direction。');}).catch(error=>{status(error.message+'；尚未取得保存依据。',true);}).finally(()=>freeze(false));}
  else status('文件模式：可编辑并下载整图和数据。要直接更新 Art Direction，请使用本地编辑命令打开此图板。');
})();
