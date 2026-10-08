export const viewLabels={front:'正面',left:'人物左侧',right:'人物右侧',back:'背面',top:'顶视',bottom:'底视',left_front:'左前 45°',right_front:'右前 45°'};

export function hunyuanRequest(mode,parameters,prompt,inputs){
  if(!['text','image','sketch'].includes(mode))throw new Error('请选择混元生成方式');
  if(mode==='text'&&inputs.length)throw new Error('文生模式不能同时上传图片');
  if(mode==='image'&&!inputs.some(x=>x.view==='front'))throw new Error('图生模式需要正面图');
  if(new Set(inputs.map(x=>x.path)).size!==inputs.length)throw new Error('不同视角不能选择同一张图片');
  if(mode==='sketch'&&(inputs.length!==1||inputs[0].view!=='front'||!prompt.trim()||parameters.Model!=='3.0'||parameters.GenerateType!=='Sketch'))throw new Error('Sketch 需要 3.0、一张正面草图和实际发送的 Prompt');
  return {hunyuan:{mode,parameters},inputs:mode!=='text'?inputs:[],prompt};
}

export function transmissionReview(job,esc){
  const t=job.transmission,p=job.promptPolicy,e=job.promptEvidence,c=job.capability;
  if(!t&&!p)return '';
  const mode={image_to_multiview:'单张正面图 → 多视图图片',multiview:'多视图生成',image:'单图生成',text:'文字生成'}[t?.mode]||'3D 生成';
  const submitted=e?.status==='accepted';
  const actual=submitted?e.prompt_recorded:!!(p?.present??t?.prompt_sent);
  const state=submitted?(actual?'提交记录中包含 Prompt（请求已获接受，效果仍待检查）':'提交记录中不包含 Prompt'):
    e&&e.status!=='not_submitted'?'提交状态待核对':actual?'准备发送 Prompt（尚无获接受记录）':'不发送 Prompt';
  const prompt=submitted?e.prompt:p?.prompt;
  const requirement=p?.required?`<p><strong>新生成要求：必须实际发送约束 Prompt</strong></p>${p.blocked?`<p class="reference-note">${esc(p.reason)}</p>`:''}`:'';
  return `<section class="job-lineage"><h3>实际发送的图片与文字</h3>${c?`<p>生成方式：${esc(c.label)} · 模型版本：${esc(c.model)} · 输出：${c.output==='images'?'多视图图片':'三维模型'}</p>`:''}<p>${esc(mode)} · ${t?.images?.length??job.inputs?.length??0} 张图片</p>${requirement}<p>文字 Prompt：${esc(state)}</p>${prompt?`<details open><summary>约束 Prompt 原文</summary><p style="white-space:pre-wrap">${esc(prompt)}</p></details>`:''}<p>${(t?.images||job.inputs||[]).map(x=>esc(viewLabels[x.view]||x.view||'参考图')).join(' / ')}</p>${job.brief?`<details><summary>本地制作说明 · 不传给云端</summary><p style="white-space:pre-wrap">${esc(job.brief)}</p></details>`:''}<p class="reference-note">本地说明不计作已发送的 Prompt。历史任务保留原始记录；接口接受参数不代表生成结果遵守了全部约束。</p></section>`;
}


export function createHunyuanBrief({getLibraryData,doc=document}){
  const $=id=>doc.getElementById(id);
  const fields=$('hunyuan-views');
  for(const [view,label] of Object.entries(viewLabels)){
    const box=doc.createElement('div');box.dataset.view=view;
    const lab=doc.createElement('label');lab.htmlFor='hunyuan-view-'+view;lab.textContent=label+(view==='front'?'（图生必选）':'（可选）');
    const select=doc.createElement('select');select.id=lab.htmlFor;
    const preview=doc.createElement('img');preview.className='brief-reference-preview';preview.hidden=true;preview.alt=label+'输入图';
    select.addEventListener('change',()=>{const asset=(getLibraryData()?.assets||[]).find(x=>x.path===select.value);preview.hidden=!asset;if(asset)preview.src=asset.url;else preview.removeAttribute('src');});
    box.append(lab,select,preview);fields.append(box);
  }
  function update(){
    const active=$('brief-provider').value==='hunyuan3d';$('hunyuan-fields').hidden=!active;$('hunyuan-fields').disabled=!active;
    if(!active){$('brief-prompt').required=true;doc.querySelector('label[for="brief-prompt"]').textContent='制作需求 / 台词';return;}
    const sketch=$('hunyuan-mode').value==='sketch';
    const image=$('hunyuan-mode').value!=='text';fields.hidden=!image;fields.disabled=!image;
    const strict=!!getLibraryData()?.generationPolicy?.require_3d_prompt;
    $('brief-prompt').required=!image||sketch||strict;$('brief-prompt').maxLength=sketch?1024:image?1200:1024;
    doc.querySelector('label[for="brief-prompt"]').textContent=image?'本地制作说明（可选，不传给云端）':'文字 Prompt（发送给混元）';
    $('hunyuan-prompt-note').textContent=image?'混元 Normal 图生模式只发送选定图片和生成参数。这里的文字留作本地制作说明；风格、服装和比例要求应体现在参考图中。':'文生模式发送文字 Prompt，不上传图片。尺寸描述不等于生成后的精确尺寸。';
    if(sketch){
      doc.querySelector('label[for="brief-prompt"]').textContent='约束 Prompt（与单张草图一起发送给混元）';
      $('hunyuan-prompt-note').textContent='Sketch 使用 3.0 和一张草图，不是普通多视图。请明确选择模型版本 3.0；不会自动切换。';
    }else if(image&&strict){
      doc.querySelector('label[for="brief-prompt"]').textContent='约束 Prompt（当前 Normal 图生接口不支持联合输入）';
      $('hunyuan-prompt-note').textContent='已启用每次 3D 生成必须实际发送 Prompt。当前图生模式不满足要求，任务不会提交；可保留多视图等待合适接口，或明确改选 Sketch 单图模式。';
    }
    for(const view of Object.keys(viewLabels)){
      const allowed=sketch?view==='front':$('hunyuan-model').value==='3.1'||['front','left','right','back'].includes(view);
      const box=fields.querySelector(`[data-view="${view}"]`);box.hidden=!allowed;$('hunyuan-view-'+view).disabled=!allowed;
      $('hunyuan-view-'+view).required=image&&view==='front';
    }
  }
  function refresh(){
    const assets=(getLibraryData()?.assets||[]).filter(a=>/\.(png|jpe?g)$/i.test(a.path));
    for(const view of Object.keys(viewLabels)){
      const select=$('hunyuan-view-'+view);select.replaceChildren();
      const empty=doc.createElement('option');empty.value='';empty.textContent='不使用';select.append(empty);
      for(const asset of assets){const option=doc.createElement('option');option.value=asset.path;option.textContent=(asset.displayName||asset.title||asset.name||asset.path)+' · '+asset.path;select.append(option);}
      select.parentElement.querySelector('img').hidden=true;
    }update();
  }
  for(const id of ['brief-provider','hunyuan-mode','hunyuan-model'])$(id).addEventListener('change',update);
  return {refresh,update,request:()=>hunyuanRequest($('hunyuan-mode').value,
    {Model:$('hunyuan-model').value,GenerateType:$('hunyuan-mode').value==='sketch'?'Sketch':'Normal',EnablePBR:$('hunyuan-pbr').checked,FaceCount:Number($('hunyuan-faces').value)},$('brief-prompt').value,
    $('hunyuan-mode').value!=='text'?Object.keys(viewLabels).filter(v=>!$('hunyuan-view-'+v).disabled&&$('hunyuan-view-'+v).value).map(v=>({view:v,path:$('hunyuan-view-'+v).value})):[])};
}
