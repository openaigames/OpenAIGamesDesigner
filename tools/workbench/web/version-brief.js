export function createVersionBrief({getData,escape:esc,doc=document}){
  const $=id=>doc.getElementById(id),groups=()=>getData()?.versions?.groups||[];
  function update(){
    const native=$('brief-provider').value==='image';$('native-fields').hidden=!native;$('native-fields').disabled=!native;
    $('brief-execution-note').textContent=native?'保存请求后由助手使用可用的内置工具执行，并登记实际输出。':'保存请求后核对服务、参考文件与参数；云端生成沿用费用授权流程。';
    if(native){$('brief-prompt').maxLength=4000;$('brief-prompt').placeholder='描述需要生成或修改的图像…';}
    const g=groups().find(g=>g.id===$('brief-asset-group').value),v=g?.versions.find(v=>v.id===$('brief-parent').value);
    const reference=$('brief-extra-reference').value;
    $('brief-lineage-note').textContent=v?`将基于 ${g.title} 的 V${v.number} 制作新候选，当前选用保持不变。${reference&&['seedream','seedance'].includes($('brief-provider').value)?'当前服务只接收一张参考图；两张参考请使用内置生图或调整选择。':''}`:'新结果保留为候选，不自动选用。';
  }
  function parents(){
    const g=groups().find(g=>g.id===$('brief-asset-group').value);
    $('brief-parent').innerHTML='<option value="">独立方案</option>'+(g?.versions||[]).filter(v=>v.intact).map(v=>`<option value="${v.id}">V${v.number} · ${esc(v.note||'未填写说明')}</option>`).join('');update();
  }
  function refresh(context){
    $('lineage-options').open=!!context;
    $('brief-asset-group').innerHTML='<option value="">新资产（生成后建立版本记录）</option>'+groups().map(g=>`<option value="${g.id}">${esc(g.title)}</option>`).join('');
    $('brief-extra-reference').innerHTML='<option value="">不添加</option>'+groups().flatMap(g=>g.versions.filter(v=>v.intact).map(v=>`<option value="${g.id}/${v.id}">${esc(g.title)} · V${v.number}</option>`)).join('');
    $('native-reference').innerHTML='<option value="">不添加</option>'+(getData()?.assets||[]).filter(a=>!a.versionHidden&&/\.(png|jpe?g|webp)$/i.test(a.path)).map(a=>`<option value="${esc(a.path)}">${esc(a.title)}</option>`).join('');
    if(context)$('brief-asset-group').value=context.group;
    parents();if(context)$('brief-parent').value=context.parent;update();
  }
  $('brief-asset-group').addEventListener('change',parents);
  for(const id of ['brief-provider','brief-parent','brief-extra-reference'])$(id).addEventListener('change',update);
  return {refresh,update,request(){
    const group=$('brief-asset-group').value,extra=$('brief-extra-reference').value;
    const lineage=(group||extra||$('brief-change-note').value)?{group:group||null,parent:$('brief-parent').value||null,note:$('brief-change-note').value,references:extra?[{group:extra.split('/')[0],version:extra.split('/')[1],role:$('brief-reference-role').value}]:[]}:null;
    return {...(lineage?{lineage}:{}),...($('brief-provider').value==='image'?{inputs:$('native-reference').value?[$('native-reference').value]:[]}:{} )};
  }};
}
