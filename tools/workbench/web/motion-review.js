import {api} from './session.js';

const statuses={unreviewed:'待审阅',current:'当前版本',stale:'旧结论已过期',unavailable:'源文件或预览不可用'};
const defaults={decision:'pending',role:'unassigned',semantic:'',mirror:false,root_motion:'unknown',note:''};
let hasDraft=()=>false;
export function allowMotionNavigation(){return !hasDraft()||window.confirm('有未保存的动作审阅，放弃这些修改？');}
window.addEventListener('beforeunload',event=>{if(hasDraft()){event.preventDefault();event.returnValue='';}});

function element(tag,text,parent){
  const node=document.createElement(tag);
  if(text!==undefined)node.textContent=text;
  parent?.append(node);
  return node;
}

export function attachMotionReview(container,asset,clipSelect){
  const panel=element('section',undefined,container);
  panel.className='motion-review';panel.setAttribute('aria-label','动作审阅');
  element('h3','动作审阅',panel);
  const notice=element('p','正在读取审阅记录…',panel);notice.setAttribute('role','status');
  if(!asset.art?.id||!asset.motionFingerprint){
    notice.textContent=!asset.art?.id?'先在资产标签区域登记此资产，再保存动作审阅。':'源文件或预览无法校验，请重新扫描或更新关联预览。';
    return;
  }
  const form=element('form',undefined,panel);
  const fields={};
  function field(name,label,options){
    const wrapper=element('label',label,form);
    const control=element(options?'select':name==='note'?'textarea':'input',undefined,wrapper);
    control.name=name;fields[name]=control;
    if(options)for(const [value,title] of options){const opt=element('option',title,control);opt.value=value;}
    else if(name==='mirror')control.type='checkbox';
    else{control.maxLength=name==='note'?2000:80;if(name==='note')control.rows=3;}
    return control;
  }
  field('decision','结论',[['pending','待定'],['keep','保留'],['reject','移除']]);
  field('role','角色用途',[['unassigned','尚未分配'],['player','玩家'],['boss','Boss'],['other','其他']]);
  field('semantic','动作语义');fields.semantic.placeholder='例如：前戳、怒吼、站立击退';
  field('root_motion','根运动',[['unknown','尚未核对'],['in_place','原地动作'],['root_motion','含根位移']]);
  field('mirror','需要左右镜像');
  field('note','审阅备注');
  const actions=element('div',undefined,form);actions.className='motion-actions';
  const save=element('button','保存动作审阅',actions);save.type='submit';save.className='button primary';
  const refresh=element('button','重新加载审阅',actions);refresh.type='button';refresh.className='button secondary';
  const history=element('details',undefined,panel);
  element('summary','上一条审阅记录',history);const previous=element('pre','暂无记录',history);
  element('p','镜像与根运动是交接要求，保存不会修改模型或游戏。',panel).className='control-note';
  let data,locked=true,dirty=false,loadId=0,lastIndex=Number(clipSelect.value);
  hasDraft=()=>panel.isConnected&&dirty;
  function lock(value){locked=value;for(const control of Object.values(fields))control.disabled=value;save.disabled=value;}
  function entry(){return data?.entries.find(e=>e.asset_id===asset.art.id&&e.clip_index===Number(clipSelect.value));}
  function render(){
    for(const option of clipSelect.options){
      const item=data.entries.find(e=>e.asset_id===asset.art.id&&e.clip_index===Number(option.value));
      if(item){const label=item.state==='current'?{keep:'保留',reject:'移除',pending:'待定'}[item.review.choice.decision]:statuses[item.state];
        option.textContent=`[${label}] ${item.clip_index+1} · ${item.clip_name}`;}
    }
    const current=entry();
    const valid=current?.source?.fingerprint===asset.motionFingerprint;
    lock(!valid);
    notice.textContent=valid?`${statuses[current.state]} · ${current.clip_name}`:'预览版本已变化。请重新扫描资产并观看新版本后审阅。';
    const choice=current?.state==='current'?current.review.choice:defaults;
    for(const [name,control] of Object.entries(fields)){
      if(name==='mirror')control.checked=choice[name];else control.value=choice[name];
    }
    previous.textContent=current?.review?JSON.stringify(current.review,null,2):'暂无记录';
    history.open=current?.state==='stale';dirty=false;lastIndex=Number(clipSelect.value);
  }
  async function reload(){
    const id=++loadId;lock(true);notice.textContent='正在读取审阅记录…';
    try{const result=await api('/api/motion-review');if(id!==loadId||!panel.isConnected)return;data=result;render();}
    catch(error){if(id===loadId&&panel.isConnected)notice.textContent=error.message;}
  }
  function confirmDiscard(){return !dirty||window.confirm('有未保存的动作审阅，放弃这些修改？');}
  form.oninput=()=>{dirty=true;};form.onchange=()=>{dirty=true;};
  refresh.onclick=()=>{if(confirmDiscard())reload();};
  clipSelect.addEventListener('change',()=>{
    if(!confirmDiscard()){clipSelect.value=String(lastIndex);clipSelect.onchange?.({target:clipSelect});return;}
    if(data)render();
  });
  form.onsubmit=async event=>{
    event.preventDefault();if(locked||!entry())return;
    const choice=Object.fromEntries(Object.entries(fields).map(([name,control])=>[name,name==='mirror'?control.checked:control.value]));
    if(choice.decision==='keep'&&(choice.role==='unassigned'||!choice.semantic.trim())){
      notice.textContent='保留动作前请填写角色用途和动作语义。';return;
    }
    const index=Number(clipSelect.value);const requestId=++loadId;
    lock(true);clipSelect.disabled=true;refresh.disabled=true;
    try{
      const result=await api('/api/motion-review',{revision:data.revision,asset_id:asset.art.id,clip_index:index,
        fingerprint:asset.motionFingerprint,choice});
      if(!panel.isConnected||requestId!==loadId)return;
      data=result;render();notice.textContent=`已保存 · ${entry().clip_name}`;
    }catch(error){
      if(!panel.isConnected||requestId!==loadId)return;
      notice.textContent=error.message;
      // Keep the user's text; conflicts require an explicit reload and review.
      if(error.status!==409)lock(false);
    }finally{clipSelect.disabled=false;refresh.disabled=false;}
  };
  lock(true);reload();
}

export function installMotionExport(parent,toast){
  const button=element('button','导出动作交接',parent);button.className='button secondary';
  button.onclick=async()=>{
    button.disabled=true;
    try{
      const report=await api('/api/motion-handoff');
      const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
      const link=element('a');link.href=url;link.download='motion-candidate-handoff.json';link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      toast(`已导出 ${report.candidates.length} 个保留动作，另列 ${report.excluded.length} 个待定／移除／过期项`);
    }catch(error){toast(error.message);}finally{button.disabled=false;}
  };
}
