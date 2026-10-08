export function effectiveCategory(asset) {
  if(!asset.classification?.manual && asset.kind==='model' && asset.meshes===0 && asset.animations?.length)return 'animation';
  return asset.classification?.category||'unclassified';
}
export function matchesCategory(asset, category) {
  if(category==='all')return true;
  if(effectiveCategory(asset)===category)return true;
  return category==='animation' && !!asset.animations?.length;
}
export function matchesFilters(asset,{format='',audio='',topic=''}={}) {
  return (!format||asset.kind===format)&&(!audio||asset.classification?.audioKind===audio)
    &&(!topic||asset.classification?.topics?.includes(topic));
}
export function categoryLabel(asset,taxonomy) {
  return taxonomy?.categories?.find(c=>c.id===effectiveCategory(asset))?.label||'未分类';
}
export function classificationLabels(asset,taxonomy) {
  const value=asset.classification||{},result=[{label:categoryLabel(asset,taxonomy),type:'category',title:value.basis||'资产主分类'}];
  if(effectiveCategory(asset)==='audio' && taxonomy?.audioKinds?.[value.audioKind])result.push({label:taxonomy.audioKinds[value.audioKind],type:'detail'});
  if(asset.animations?.length && effectiveCategory(asset)!=='animation')result.push({label:'含动画',type:'capability'});
  if(value.needsReview)result.push({label:'分类待核对',type:'review',title:value.reviewReason});
  return result;
}
export function classificationChips(asset,taxonomy,esc) {
  return classificationLabels(asset,taxonomy).map(t=>`<span class="classification-${t.type}" title="${esc(t.title||t.label)}">${esc(t.label)}</span>`).join('');
}
export function createCategoryEditor({getData,getSelected,getFiltered,api,refresh,escape:esc,toast,canLeave}) {
  const editor=document.getElementById('asset-category-editor');
  const dialog=document.createElement('dialog');dialog.id='category-dialog';dialog.className='category-dialog';document.body.append(dialog);
  let busy=false;
  const controls=(value,bulk=false)=>`<label>资产主分类<select name="category" required aria-label="${bulk?'批量资产主分类':'资产主分类'}">${bulk?'<option value="">请选择分类</option>':''}${(getData()?.taxonomy?.categories||[]).map(c=>`<option value="${esc(c.id)}" ${value?.category===c.id?'selected':''}>${esc(c.label)}</option>`).join('')}</select></label>
    <label data-audio-row ${value?.category==='audio'?'':'hidden'}>音频用途<select name="audioKind" aria-label="音频用途"><option value="">未细分</option>${Object.entries(getData()?.taxonomy?.audioKinds||{}).map(([id,label])=>`<option value="${esc(id)}" ${value?.audioKind===id?'selected':''}>${esc(label)}</option>`).join('')}</select></label>`;
  function bind(form,paths) {
    const records=paths.map(path=>getData().assets.find(a=>a.path===path));
    const versions=Object.fromEntries(records.map(a=>[a.path,a.classification?.version]));
    const previousPath=records.length===1?records[0].classification?.previousPath:undefined;
    const select=form.querySelector('[name=category]');
    select.onchange=()=>{form.querySelector('[data-audio-row]').hidden=select.value!=='audio';if(select.value!=='audio')form.querySelector('[name=audioKind]').value='';};
    async function save(action){
      if(busy||!await canLeave())return;
      if(action==='set'&&!form.reportValidity())return;
      const revision=getData()?.taxonomy?.revision;
      if(!revision){toast('分类记录不可用，请修复后刷新');return;}
      busy=true;form.querySelectorAll('button').forEach(b=>b.disabled=true);
      try {
        await api('/api/asset-classification',{project:'current',revision,paths,action,versions,previousPath,
          classification:{category:select.value,audioKind:select.value==='audio'?form.querySelector('[name=audioKind]').value:''}});
        if(dialog.open)dialog.close();await refresh();toast(action==='reset'?'已恢复自动分类':`已保存 ${paths.length} 个资产的分类`);
      }catch(error){form.querySelector('[role=alert]').textContent=error.message;}
      finally{busy=false;form.querySelectorAll('button').forEach(b=>b.disabled=false);}
    }
    form.onsubmit=e=>{e.preventDefault();save('set');};
    form.querySelector('[data-reset]')?.addEventListener('click',()=>save('reset'));
  }
  function render(){
    const asset=getSelected(),taxonomy=getData()?.taxonomy;
    if(!asset){editor.innerHTML='';return;}
    const value=asset.classification,choice=value?.needsReview?{category:value.previousCategory,audioKind:value.previousAudioKind}:{...value,category:effectiveCategory(asset)};
    const oldLabel=taxonomy?.categories?.find(c=>c.id===value?.previousCategory)?.label||'未分类';
    editor.innerHTML=`<div class="classification-heading">分类标签</div><div class="classification-tags">${classificationChips(asset,taxonomy,esc)}</div>${value?.needsReview?`<p class="classification-warning">${esc(value.reviewReason)}。原分类：${esc(oldLabel)}${value.previousPath?' · '+esc(value.previousPath):''}。</p>`:''}<details><summary>修改分类</summary><form>${controls(choice)}<p class="category-note">${esc(value?.basis||'待分类')}。仅设置当前文件的分类。</p>${taxonomy?.error?`<p role="alert">${esc(taxonomy.error)}</p>`:'<p role="alert"></p>'}<div class="category-actions"><button class="button secondary" ${taxonomy?.error||!value?.version?'disabled':''}>${value?.needsReview?'核对并保存分类':'保存分类'}</button>${value?.saved?'<button class="button secondary" type="button" data-reset>恢复自动</button>':''}</div></form></details>`;
    bind(editor.querySelector('form'),[asset.path]);
  }
  document.getElementById('bulk-categories').onclick=()=>{
    const assets=getFiltered();
    if(!assets.length||assets.length>500){toast('请筛选出 1–500 个资产后批量分类');return;}
    if(getData()?.taxonomy?.error){toast(getData().taxonomy.error);return;}
    dialog.innerHTML=`<div class="dialog-heading"><h2>批量分类</h2><button class="icon-button" type="button" data-close aria-label="关闭批量分类">×</button></div><p>将修改当前筛选结果中的 ${assets.length} 个资产，包含其他分页中的结果。文件位置保持不变。</p><form>${controls(null,true)}<p role="alert"></p><button class="button primary">保存这 ${assets.length} 个资产的分类</button></form>`;
    dialog.querySelector('[data-close]').onclick=()=>dialog.close();
    bind(dialog.querySelector('form'),assets.map(a=>a.path));dialog.showModal();
  };
  return {render};
}
