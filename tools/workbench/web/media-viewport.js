/** Shared screen-space navigation for image, particle, waveform and video previews. */
export function attachMediaViewport(host,content,controls,{
  label='资产预览画布',background='#f4f6fc',checker=false,nativeVideo=false
}={}){
  const events=new AbortController(),signal=events.signal;
  const layer=document.createElement('div');layer.className='media-content';layer.append(content);host.append(layer);
  host.classList.add('pan-zoom');host.tabIndex=0;host.setAttribute('role','region');host.setAttribute('aria-label',label);
  let x=0,y=0,scale=1,drag=null,color=background,mode=checker?'checker':'color';
  const tools=document.createElement('div');tools.className='controls media-view-tools';
  tools.innerHTML='<div class="viewport-zoom-row"><label for="media-zoom">缩放</label><button class="toggle-chip" data-zoom="out" aria-label="缩小预览">−</button><input id="media-zoom" aria-label="预览缩放" type="range" min="0.25" max="8" step="0.01" value="1"><button class="toggle-chip" data-zoom="in" aria-label="放大预览">+</button><output id="media-zoom-value" for="media-zoom">100%</output></div><div class="viewport-action-row"><button class="toggle-chip" id="media-reset" type="button">复位视图</button><span>拖动平移 · 滚轮缩放</span></div><div class="viewport-background-row"><label for="background-color">背景</label><input id="background-color" type="color" aria-label="预览背景颜色"><input id="background-hex" type="text" aria-label="背景颜色十六进制值" maxlength="7" spellcheck="false" autocomplete="off" pattern="#[0-9a-fA-F]{6}" placeholder="#111d49"></div><div class="viewport-presets"><button class="toggle-chip" data-background="#111d49">深色</button><button class="toggle-chip" data-background="#f4f6fc">浅色</button><button class="toggle-chip" data-background="checker">棋盘格</button></div><p class="control-note viewport-help"></p>';
  controls.append(tools);
  const find=selector=>tools.querySelector(selector);
  const slider=find('#media-zoom'),percent=find('#media-zoom-value'),picker=find('#background-color'),hex=find('#background-hex');
  find('.viewport-action-row span').textContent=nativeVideo?'右键拖动 · 滚轮缩放':'拖动平移 · 滚轮缩放';
  find('.viewport-help').textContent='双击或按 Home 复位；画布获得焦点后，方向键平移，+ / − 缩放。';
  function render(){
    layer.style.transform='translate('+x+'px, '+y+'px) scale('+scale+')';
    slider.value=scale;percent.value=Math.round(scale*100)+'%';
  }
  function zoomTo(next,px=0,py=0){
    if(!Number.isFinite(next))return;
    const clamped=Math.min(8,Math.max(.25,next)),ratio=clamped/scale;
    // Keep the content point under the pointer fixed while zooming.
    x=px-(px-x)*ratio;y=py-(py-y)*ratio;scale=clamped;render();
  }
  function reset(){x=0;y=0;scale=1;render();}
  function finish(){
    const pointer=drag?.id;drag=null;host.classList.remove('is-dragging');
    if(pointer!==undefined&&host.hasPointerCapture(pointer))host.releasePointerCapture(pointer);
  }
  function setBackground(value){
    if(value==='checker')mode='checker';
    else if(/^#[\da-f]{6}$/i.test(value)){mode='color';color=value.toLowerCase();}
    else return;
    host.classList.toggle('checker',mode==='checker');
    host.style.background=mode==='checker'?'':color;
    picker.value=color;hex.value=color;hex.removeAttribute('aria-invalid');
    const rgb=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)/255);
    const luminance=rgb.reduce((sum,v,i)=>sum+(v<=.04045?v/12.92:((v+.055)/1.055)**2.4)*[.2126,.7152,.0722][i],0);
    host.style.setProperty('--preview-foreground',mode==='checker'||luminance>.35?'#455475':'#e6ecff');
    tools.querySelectorAll('[data-background]').forEach(b=>{
      const active=b.dataset.background===(mode==='checker'?'checker':color);
      b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));
    });
  }
  host.addEventListener('pointerdown',e=>{
    if(drag||![0,2].includes(e.button)||!e.isPrimary)return;
    // Keep native video controls usable; its image can still be panned with the right button.
    if(nativeVideo&&e.button===0&&e.target.closest('video'))return;
    if(e.target.closest('button,input,select,a'))return;
    e.preventDefault();host.focus({preventScroll:true});
    drag={id:e.pointerId,startX:e.clientX,startY:e.clientY,x,y};
    host.setPointerCapture(e.pointerId);host.classList.add('is-dragging');
  },{signal});
  host.addEventListener('pointermove',e=>{
    if(!drag||e.pointerId!==drag.id)return;
    x=drag.x+e.clientX-drag.startX;y=drag.y+e.clientY-drag.startY;render();
  },{signal});
  for(const type of ['pointerup','pointercancel','lostpointercapture'])host.addEventListener(type,e=>{if(drag?.id===e.pointerId)finish();},{signal});
  window.addEventListener('blur',finish,{signal});
  host.addEventListener('contextmenu',e=>e.preventDefault(),{signal});
  host.addEventListener('dragstart',e=>e.preventDefault(),{signal});
  host.addEventListener('wheel',e=>{
    e.preventDefault();
    if(drag)return;
    const rect=host.getBoundingClientRect(),unit=e.deltaMode===1?16:e.deltaMode===2?host.clientHeight:1;
    zoomTo(scale*Math.exp(-Math.max(-1000,Math.min(1000,e.deltaY*unit))*.0015),e.clientX-rect.left-rect.width/2,e.clientY-rect.top-rect.height/2);
  },{passive:false,signal});
  host.addEventListener('dblclick',e=>{
    if(nativeVideo&&e.target.closest('video'))return;
    e.preventDefault();reset();
  },{signal});
  host.addEventListener('keydown',e=>{
    if(e.target!==host)return;
    const step=e.shiftKey?80:20;
    if(e.key==='ArrowLeft')x-=step;
    else if(e.key==='ArrowRight')x+=step;
    else if(e.key==='ArrowUp')y-=step;
    else if(e.key==='ArrowDown')y+=step;
    else if(['+','='].includes(e.key))zoomTo(scale*1.2);
    else if(['-','_'].includes(e.key))zoomTo(scale/1.2);
    else if(['Home','0'].includes(e.key))reset();
    else return;
    e.preventDefault();e.stopPropagation();render();
  },{signal});
  slider.addEventListener('input',()=>zoomTo(Number(slider.value)),{signal});
  find('[data-zoom="in"]').addEventListener('click',()=>zoomTo(scale*1.2),{signal});
  find('[data-zoom="out"]').addEventListener('click',()=>zoomTo(scale/1.2),{signal});
  find('#media-reset').addEventListener('click',reset,{signal});
  picker.addEventListener('input',()=>setBackground(picker.value),{signal});
  hex.addEventListener('input',()=>{
    if(/^#[\da-f]{6}$/i.test(hex.value))setBackground(hex.value);
    else hex.setAttribute('aria-invalid','true');
  },{signal});
  hex.addEventListener('blur',()=>{hex.value=color;hex.removeAttribute('aria-invalid');},{signal});
  tools.querySelectorAll('[data-background]').forEach(b=>b.addEventListener('click',()=>setBackground(b.dataset.background),{signal}));
  render();setBackground(checker?'checker':background);
  return {
    dispose(){
      finish();events.abort();tools.remove();layer.style.transform='';
      host.classList.remove('pan-zoom','checker');host.removeAttribute('tabindex');host.removeAttribute('role');host.removeAttribute('aria-label');
      host.style.removeProperty('--preview-foreground');host.style.background='';
    }
  };
}
