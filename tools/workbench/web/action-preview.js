// Native scene frames are separate from historical video and draft audio audition.
export function createActionPreview({root,api,esc,getData,onTime,onMode,onSaved}) {
  const client=crypto.randomUUID().replaceAll('-','');
  const $=id=>root.querySelector('#'+id);
  let timer,debounce,enabled=false,connected=false,connection=null,request=null,lastFrame='',epoch=0,busy=false,edited=false,editVersion=0,savedRun='';
  const labels={idle:'就绪',playing:'正在重放',paused:'已暂停',complete:'本次动作已完成',stopped:'已停止',disconnected:'页面连接已断开',error:'应用失败',offline:'引擎已离线'};
  function message(text){if($('ap-status'))$('ap-status').textContent=text;}
  function clearFrame(text){lastFrame='';if($('ap-frame')){$('ap-frame').hidden=true;$('ap-frame').removeAttribute('src');}if($('ap-placeholder')){$('ap-placeholder').hidden=false;$('ap-placeholder').textContent=text;}}
  function controls(state){
    const available=connection?.online&&connected&&!busy;
    for(const op of ['pause','resume','step','stop','view','speed'])if($('ap-'+op))$('ap-'+op).disabled=!available||!connection.controls?.includes(op);
    if($('ap-pause'))$('ap-pause').disabled=!available||state?.state!=='playing';
    if($('ap-resume'))$('ap-resume').disabled=!available||state?.state!=='paused';
    if($('ap-step'))$('ap-step').disabled=!available||!['playing','paused'].includes(state?.state);
    if($('ap-record')){$('ap-record').disabled=!available||edited||!state?.record_ready||savedRun===state?.run;$('ap-record').textContent=savedRun&&savedRun===state?.run?'本次记录已保存':'保留本次实机记录';}
    if($('ap-connect'))$('ap-connect').disabled=!connection?.online||busy;
  }
  async function refresh(){
    const mark=epoch,id=getData()?.sequence?.id;
    if(!enabled||!id)return;
    try{
      const response=await api('/api/action-preview-status?id='+encodeURIComponent(id));
      if(mark!==epoch||!enabled)return;
      const previous=connection;connection=response;
      if($('ap-view')&&response.online&&previous?.instance!==response.instance){$('ap-view').innerHTML=(response.views||[]).map(v=>`<option value="${esc(v.id)}">${esc(v.label)}</option>`).join('');}
      if(!response.online||connected&&previous?.instance!==response.instance){connected=false;request=null;onMode(false);clearFrame(response.message);message(response.message);controls();return;}
      if(!connected){message(response.message);controls();return;}
      await api('/api/action-preview-heartbeat',{id,instance:response.instance,client});
      if(mark!==epoch||!enabled)return;
      const state=response.state;
      if(!state||state.client!==client||state.run!==request?.run||state.sequence_sha256!==request?.sequence_sha256){clearFrame('草案已发送，等待引擎应用并回传新画面…');controls();return;}
      if(state.error){message('引擎应用失败：'+state.error);clearFrame('此次草案尚未得到实机画面');controls(state);return;}
      // Object key order may differ across engines. The acknowledged request hash is authoritative;
      // edited tracks remain visibly pending until a new replay has been acknowledged.
      message(`${labels[state.state]||state.state} · 引擎生效版本 ${state.sequence_sha256.slice(0,10)}${edited?' · 当前草案有新修改':''}${savedRun===state.run?' · 实机记录已保存':''}`);
      if(state.request===request.request){if($('ap-view')&&state.view)$('ap-view').value=state.view;if($('ap-speed'))$('ap-speed').value=String(state.speed);}
      if($('ap-readout'))$('ap-readout').textContent=`${Number(state.actual?.elapsed_s||0).toFixed(3)} / ${Number(state.actual?.duration_s||0).toFixed(3)} 秒 · 测试速度 ${state.speed}× · ${response.engine} ${response.engine_version}`;
      if($('ap-events'))$('ap-events').textContent=(state.events||[]).map(e=>`${e.id} @ ${Number(e.t_s).toFixed(3)}s`).join(' · ');
      if(state.applied&&!edited)onTime(Number(state.actual?.elapsed_s||0));
      if(state.applied&&state.frame>0&&!edited){
        const frameKey=state.run+':'+state.frame;
        if(frameKey!==lastFrame){
          lastFrame=frameKey;const expectedRun=state.run,img=$('ap-frame');
          img.onload=()=>{if(enabled&&connected&&!edited&&request?.run===expectedRun){img.hidden=false;$('ap-placeholder').hidden=true;}};
          img.onerror=()=>{if(enabled&&request?.run===expectedRun)clearFrame('等待下一帧原生画面…');};
          img.src=`/api/action-preview-frame?id=${encodeURIComponent(id)}&run=${state.run}&frame=${state.frame}`;
        }
      }
      controls(state);
    }catch(error){if(mark===epoch){connected=false;onMode(false);clearFrame('连接中断；当前没有实时画面');message(error.message);controls();}}
    finally{if(enabled&&mark===epoch)timer=setTimeout(refresh,400);}
  }
  async function send(operation,extra={}){
    if(busy)throw Error('引擎请求正在发送，请稍后再试');
    const snapshot=getData();
    if(!snapshot?.sequence||!connection?.online)throw Error('请先启动此动作的原生测试场景');
    busy=true;controls();const mark=epoch,sentVersion=editVersion;
    try{
      const result=await api('/api/action-preview-command',{id:snapshot.sequence.id,instance:connection.instance,client,operation,run:request?.run,
        ...(operation==='replay'?{base_hash:snapshot.hash,sequence:snapshot.sequence}:{}),...extra});
      if(mark!==epoch)return;
      request=result;connected=true;onMode(true);if($('ap-connect'))$('ap-connect').textContent='重放当前草案';
      if(operation==='replay'){edited=editVersion!==sentVersion;savedRun='';clearFrame('草案已发送，等待引擎应用并回传新画面…');message('草案已发送 · 正式工程配置未改变');}
      if(operation==='stop')message('停止请求已发送');
    }finally{busy=false;controls();}
  }
  const attempt=fn=>()=>Promise.resolve().then(fn).catch(e=>message(e.message));
  function mount(){
    clearTimeout(timer);epoch++;enabled=true;connected=false;request=null;connection=null;edited=false;lastFrame='';editVersion=0;savedRun='';
    $('ae-native').hidden=!getData()?.preview;
    if($('ae-native').hidden){enabled=false;return;}
    $('ae-native').innerHTML=`<div class="ap-heading"><strong>原生测试场景</strong><button id="ap-connect" class="button secondary">连接并预览草案</button></div>
      <p id="ap-status" role="status">正在检查测试场景…</p><div class="ap-screen"><img id="ap-frame" alt="原生引擎实时回传画面" hidden><div id="ap-placeholder">启动已接入的测试场景后，在这里检查实际效果。</div></div>
      <div class="ap-controls"><button id="ap-pause" class="button secondary">暂停</button><button id="ap-resume" class="button secondary">继续</button><button id="ap-step" class="button secondary">下一帧 · 1/30秒</button><button id="ap-stop" class="button secondary">停止预览</button>
      <label>机位<select id="ap-view" aria-label="原生预览机位"></select></label><label>测试速度<select id="ap-speed" aria-label="原生预览速度"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></label></div>
      <label class="ap-auto"><input id="ap-auto" type="checkbox" checked>连接后，修改参数自动重放草案</label><div id="ap-readout"></div><div id="ap-events"></div>
      <button id="ap-record" class="button secondary">保留本次实机记录</button><p class="ae-footnote">画面由原生测试场景回传，声音由该引擎窗口播放。预览不覆盖工程配置；完成检查后使用“保存到工程”。骨骼姿态、蒙皮与 IK 在源工具或引擎中修改。</p>`;
    $('ap-connect').onclick=attempt(()=>send('replay'));
    for(const op of ['pause','resume','step','stop'])$('ap-'+op).onclick=attempt(()=>send(op));
    $('ap-view').onchange=attempt(()=>send('view',{view:$('ap-view').value}));
    $('ap-speed').onchange=attempt(()=>send('speed',{speed:Number($('ap-speed').value)}));
    $('ap-record').onclick=attempt(async()=>{const run=request.run;const saved=await api('/api/action-preview-record',{id:getData().sequence.id,run});savedRun=run;message('本次结果已保存到“实机记录” · '+saved.id.slice(0,8));onSaved?.(saved.id);});
    controls();refresh();
  }
  async function disconnect(){
    clearTimeout(timer);clearTimeout(debounce);epoch++;enabled=false;
    if(connected&&connection?.instance){try{await api('/api/action-preview-heartbeat',{id:getData().sequence.id,instance:connection.instance,client,release:true});}catch{}}
    connected=false;request=null;onMode(false);
  }
  return {mount,disconnect,isConnected:()=>connected,
    edited(){if(!connected)return;editVersion++;edited=true;clearFrame('草案已修改，等待重新播放当前版本');message('当前草案有新修改 · 尚未得到对应实机结果');clearTimeout(debounce);if($('ap-auto')?.checked)debounce=setTimeout(()=>send('replay').catch(e=>message(e.message)),400);},
    replay:()=>send('replay'),
    active(value){if(!value)disconnect();else if($('ae-native')&&!enabled){mount();}}
  };
}
