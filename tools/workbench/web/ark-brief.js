// Form limits mirror the supported Ark model families; Python validates again.
export function imageSizes(model){
  if(/-5-0-(pro|flash)-/.test(model))return ['1K','1.5K','2K'];
  if(model.includes('-5-0-lite-'))return ['2K','3K','4K'];
  return model.includes('-4-5-')?['2K','4K']:['1K','2K','4K'];
}
export function videoLimits(model){return {max:model.includes('-2-5-')?30:15,resolutions:/-(fast|mini)-/.test(model)?['480p','720p']:['480p','720p','1080p']};}
export function arkParameters(provider,values){
  const common={model:values.model.trim(),watermark:values.watermark};
  return provider==='seedream'?{...common,size:values.size}:{...common,duration:Number(values.duration),resolution:values.resolution,ratio:values.ratio,generate_audio:values.audio};
}
export function createArkBrief({getLibraryData,doc=document}){
  const $=id=>doc.getElementById(id),defaults={seedream:'doubao-seedream-5-0-pro-260628',seedance:'doubao-seedance-2-5-260628'};
  let previous='';
  function options(id,values){const el=$(id),old=el.value;el.replaceChildren(...values.map(value=>{const option=doc.createElement('option');option.value=value;option.textContent=value;return option;}));if(values.includes(old))el.value=old;}
  function update(){
    const provider=$('brief-provider').value,active=provider in defaults,isImage=provider==='seedream';
    $('ark-fields').hidden=!active;$('ark-fields').disabled=!active;
    for(const [id,show] of [['ark-image-fields',active&&isImage],['ark-video-fields',active&&!isImage]]){$(id).hidden=!show;$(id).disabled=!show;}
    if(!active){previous=provider;return;}
    if(provider!==previous){$('ark-model').value=defaults[provider];previous=provider;}
    const model=$('ark-model').value;
    options('ark-size',imageSizes(model));
    const limits=videoLimits(model);options('ark-resolution',limits.resolutions);$('ark-duration').max=limits.max;
    const fixedRatio=!isImage&&model.includes('-2-5-')&&!!$('ark-reference').value;
    const reference=(getLibraryData().assets||[]).find(asset=>asset.path===$('ark-reference').value);
    const preview=$('ark-reference-preview');preview.hidden=!reference;
    if(reference)preview.src=reference.url;else preview.removeAttribute('src');
    $('ark-ratio').disabled=fixedRatio;if(fixedRatio)$('ark-ratio').value='adaptive';
    $('ark-reference-note').textContent=isImage?'可选一张项目内参考图进行改绘；源文件会保存为本次任务的快照。':'可选一张项目内图片作为首帧；Seedance 2.5 会保持首帧比例。';
    $('brief-prompt').maxLength=4000;$('brief-prompt').placeholder=isImage?'描述图像内容、风格、构图和宽高比例…':'描述画面、动作、镜头、节奏及声音需求…';
  }
  function refresh(){
    previous='';const select=$('ark-reference');select.replaceChildren();
    const empty=doc.createElement('option');empty.value='';empty.textContent='不使用参考图（文本生成）';select.append(empty);
    for(const asset of getLibraryData().assets||[]){if(!/\.(png|jpe?g|webp)$/i.test(asset.path))continue;const option=doc.createElement('option');option.value=asset.path;option.textContent=(asset.displayName||asset.name||asset.path)+' · '+asset.path;select.append(option);}
    update();
  }
  $('brief-provider').addEventListener('change',update);$('ark-model').addEventListener('input',update);$('ark-reference').addEventListener('change',update);
  return {refresh,update,request:()=>({media:arkParameters($('brief-provider').value,{model:$('ark-model').value,size:$('ark-size').value,
    duration:$('ark-duration').value,resolution:$('ark-resolution').value,ratio:$('ark-ratio').value,audio:$('ark-audio').checked,watermark:$('ark-watermark').checked}),
    inputs:$('ark-reference').value?[$('ark-reference').value]:[]})};
}
