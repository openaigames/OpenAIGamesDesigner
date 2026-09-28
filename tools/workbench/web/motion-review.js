import {api} from './session.js';
import {draftGuard} from './motion-guard.js';

function confirmDiscard(){
  return new Promise(resolve=>{
    const dialog=document.createElement('dialog');dialog.className='motion-discard';
    dialog.setAttribute('aria-label','未保存的动作审阅');
    const title=document.createElement('h3');title.textContent='有未保存的动作审阅';
    const text=document.createElement('p');text.textContent='放弃修改并继续切换？';
    const keep=document.createElement('button');keep.textContent='继续编辑';keep.className='button secondary';
    const discard=document.createElement('button');discard.textContent='放弃修改并继续';discard.className='button primary';
    let finished=false;const finish=value=>{if(finished)return;finished=true;dialog.close();dialog.remove();resolve(value);};
    keep.onclick=()=>finish(false);discard.onclick=()=>finish(true);dialog.oncancel=event=>{event.preventDefault();finish(false);};
    dialog.append(title,text,keep,discard);document.body.append(dialog);dialog.showModal();keep.focus();
  });
}
const guard=draftGuard(confirmDiscard);
export const allowMotionNavigation=()=>guard.allow();
window.addEventListener('beforeunload',event=>{if(guard.pending()){event.preventDefault();event.returnValue='';}});
const defaults={decision:'pending',semantic:'',mirror:false,root_motion:'unknown',note:''};
const statuses={unreviewed:'尚未审阅',current:'当前版本',stale:'旧结论已过期',unavailable:'源文件或预览不可用'};
const scopes=new Map();
const scopeKey=(asset,character)=>JSON.stringify([asset.path,character?.id||null]);
export function motionContext(asset,character){
  const saved=scopes.get(scopeKey(asset,character));
  return {character_id:character?.id||null,role:saved?.role||(character?.role==='shared'?'unassigned':character?.role)||'unassigned',use:saved?.use||'general',rig_path:asset.rig?.path||null};
}
export async function prepareMotion(asset,character){
  const request={path:asset.path,context:motionContext(asset,character)};
  const result=await api('/api/motion-context',request);
  return {request,result};
}
function element(tag,text,parent){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;parent?.append(node);return node;}

export function attachMotionReview(container,asset,character,clips,clipSelect,prepared,reopen){
  const panel=element('section',undefined,container);panel.className='motion-review';panel.setAttribute('aria-label','动作审阅');
  element('h3','动作取舍',panel);
  const notice=element('p','正在读取当前片段…',panel);notice.setAttribute('role','status');
  if(!prepared||prepared.error){notice.textContent=prepared?.error||'当前预览无法校验，请刷新资产后再观看。';return;}
  let request={...prepared.request,observation:{fingerprint:prepared.result.source.fingerprint,clips:clips.map(c=>({name:c.name,duration:c.duration}))}};
  let data,locked=true,dirty=false,busy=false,loadId=0,lastIndex=Number(clipSelect.value);
  const currentContext=request.context;
  element('p',`${character?.title||'资源级判断'} · ${asset.path}`,panel);
  element('p','仅记录选材判断；保留不移动素材，不代表引擎品质通过。',panel).className='control-note';
  const scope=element('div',undefined,panel);scope.className='motion-scope';
  const roleLabel=element('label','角色用途',scope),role=element('select',undefined,roleLabel);role.setAttribute('aria-label','动作审阅角色用途');
  for(const [value,title] of [['unassigned','尚未分配'],['player','主角'],['boss','Boss'],['other','其他']]){const option=element('option',title,role);option.value=value;}
  role.value=currentContext.role;
  const useLabel=element('label','用途 ID（相同用途沿用同一 ID）',scope),use=element('input',undefined,useLabel);use.value=currentContext.use;use.maxLength=80;use.setAttribute('aria-label','动作审阅用途 ID');
  const applyScope=element('button','切换用途',scope);applyScope.type='button';applyScope.className='button secondary';
  async function switchScope(){
    if(!use.value.trim()){notice.textContent='请填写用途 ID';return;}
    const next={role:role.value,use:use.value.trim()};
    if(!await guard.allow()){role.value=currentContext.role;use.value=currentContext.use;return;}
    scopes.set(scopeKey(asset,character),next);await reopen();
  }
  role.onchange=switchScope;applyScope.onclick=switchScope;
  const form=element('form',undefined,panel),fields={};
  function field(name,label,options){
    const wrapper=element('label',label,form),control=element(options?'select':name==='note'?'textarea':'input',undefined,wrapper);control.name=name;fields[name]=control;
    if(options)for(const [value,title] of options){const option=element('option',title,control);option.value=value;}
    else if(name==='mirror')control.type='checkbox';
    else{control.maxLength=name==='note'?2000:80;if(name==='note')control.rows=3;}
  }
  field('decision','结论',[['pending','待定'],['keep','保留'],['reject','不采用']]);
  field('semantic','动作语义');fields.semantic.placeholder='例如：前戳、怒吼、站立击退';
  field('root_motion','根运动要求',[['unknown','待核对'],['in_place','需要原地动作'],['root_motion','需要根位移']]);
  field('mirror','需要制作左右镜像');field('note','审阅备注');
  const actions=element('div',undefined,form);actions.className='motion-actions';
  const save=element('button','保存动作取舍',actions);save.type='submit';save.className='button primary';
  const refresh=element('button','重新加载记录',actions);refresh.type='button';refresh.className='button secondary';
  const exportButton=element('button',character?'导出此角色动作':'导出当前动作选择',actions);exportButton.type='button';exportButton.className='button secondary';
  const history=element('details',undefined,panel);element('summary','当前上下文的上一条记录',history);const previous=element('pre','暂无记录',history);
  element('p','镜像与根运动选项只记录制作要求；不会变换当前预览或修改游戏动画。',panel).className='control-note';
  const session={pending:()=>panel.isConnected&&(dirty||busy),busy:()=>panel.isConnected&&busy,discard:()=>{dirty=false;if(data)render();}};
  guard.attach(session);
  function lock(value){locked=value;for(const control of Object.values(fields))control.disabled=value;save.disabled=value;}
  function entry(){return data?.entries.find(e=>e.clip_index===Number(clipSelect.value));}
  function render(){
    const current=entry();lock(!current||current.source.fingerprint!==request.observation.fingerprint);
    notice.textContent=locked?'预览版本已变化，请刷新资产并重新观看。':`${statuses[current.state]} · #${current.clip_index+1} ${current.clip_name} · ${data.provenance==='browser_fbx_observation'?'浏览器 FBX 观测':'本地 glTF 片段'}`;
    const choice=current?.state==='current'?current.review.choice:defaults;
    for(const [name,control] of Object.entries(fields)){if(name==='mirror')control.checked=choice[name];else control.value=choice[name];}
    previous.textContent=current?.review?JSON.stringify(current.review,null,2):'暂无记录';history.open=current?.state==='stale';dirty=false;lastIndex=Number(clipSelect.value);
  }
  async function reload(){
    const id=++loadId;lock(true);notice.textContent='正在核对片段与依赖版本…';
    try{const result=await api('/api/motion-context',request);if(id!==loadId||!panel.isConnected)return;data=result;render();}
    catch(error){if(id===loadId&&panel.isConnected)notice.textContent=error.message;}
  }
  form.oninput=form.onchange=()=>{dirty=true;};
  refresh.onclick=async()=>{if(await guard.allow())reload();};
  // Capture runs before the player's onchange. A refused switch changes neither time nor playback.
  clipSelect.addEventListener('change',async event=>{
    const next=clipSelect.value;event.stopImmediatePropagation();clipSelect.value=String(lastIndex);
    if(!await guard.allow())return;
    clipSelect.value=next;if(data)render();clipSelect.onchange?.({target:clipSelect});
  },true);
  form.onsubmit=async event=>{
    event.preventDefault();if(locked||busy||!entry())return;
    const choice={role:currentContext.role,...Object.fromEntries(Object.entries(fields).map(([name,c])=>[name,name==='mirror'?c.checked:c.value]))};
    if(choice.decision==='keep'&&(choice.role==='unassigned'||!choice.semantic.trim())){notice.textContent='保留前请选角色用途并填写动作语义。';return;}
    busy=true;lock(true);refresh.disabled=role.disabled=use.disabled=applyScope.disabled=clipSelect.disabled=true;
    try{
      const result=await api('/api/motion-review',{revision:data.revision,preview:request,clip_index:Number(clipSelect.value),fingerprint:request.observation.fingerprint,choice});
      if(!panel.isConnected)return;data=result;render();notice.textContent=`已保存 · #${entry().clip_index+1} ${entry().clip_name}`;
    }catch(error){if(panel.isConnected){notice.textContent=error.message;if(error.status!==409)lock(false);}}
    finally{busy=false;refresh.disabled=role.disabled=use.disabled=applyScope.disabled=clipSelect.disabled=false;}
  };
  exportButton.onclick=async()=>{
    if(!await guard.allow())return;exportButton.disabled=true;
    try{
      const report=await api('/api/motion-handoff'+(character?'?character='+encodeURIComponent(character.id):''));
      const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
      const link=element('a');link.href=url;link.download='motion-candidate-handoff.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      notice.textContent=`已导出 ${report.candidates.length} 个当前保留动作；另列 ${report.excluded.length} 个过期或未采用记录。`;
    }catch(error){notice.textContent=error.message;}finally{exportButton.disabled=false;}
  };
  lock(true);reload();
}
