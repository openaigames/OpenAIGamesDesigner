// Audio form parameters are validated again by the shared Python adapter.
export function audioParameters(values){
  const p={kind:values.kind};
  if(p.kind==='music')return {...p,music_length_ms:Math.round(Number(values.musicSeconds)*1000),force_instrumental:values.instrumental};
  if(p.kind==='speech')return {...p,voice_id:values.voice.trim()};
  if(values.mode==='duration')return {...p,duration_seconds:Number(values.duration),loop:values.loop};
  p.timing={event:values.event.trim(),tail_seconds:Number(values.tail),trim_start_seconds:Number(values.trim),fit:true};
  if(values.mode==='source')p.timing.source={path:values.path.trim(),pointer:values.pointer.trim()};
  else p.timing.window={start_seconds:Number(values.start),end_seconds:Number(values.end),play_rate:Number(values.rate)};
  return p;
}

export function createAudioBrief(doc=document){
  const $=id=>doc.getElementById(id);
  function values(){return {kind:$('audio-kind').value,mode:$('audio-mode').value,
    duration:$('audio-duration').value,loop:$('audio-loop').checked,musicSeconds:$('music-duration').value,
    instrumental:$('music-instrumental').checked,voice:$('audio-voice').value,event:$('audio-event').value,
    start:$('window-start').value,end:$('window-end').value,rate:$('window-rate').value,
    tail:$('window-tail').value,trim:$('window-trim').value,path:$('window-source').value,pointer:$('window-pointer').value};}
  function update(){
    const active=$('brief-provider').value==='elevenlabs',v=values();
    for(const [id,show] of [['audio-fields',active],['sfx-fields',active&&v.kind==='sound_effect'],
      ['music-fields',active&&v.kind==='music'],['speech-fields',active&&v.kind==='speech'],
      ['duration-fields',active&&v.kind==='sound_effect'&&v.mode==='duration'],
      ['window-fields',active&&v.kind==='sound_effect'&&v.mode!=='duration'],
      ['manual-window-fields',active&&v.kind==='sound_effect'&&v.mode==='manual'],
      ['source-window-fields',active&&v.kind==='sound_effect'&&v.mode==='source']]){
      $(id).hidden=!show;$(id).disabled=!show;
    }
    $('brief-prompt').maxLength=active?(v.kind==='music'?4100:2500):1200;
    $('brief-prompt').placeholder=active?(v.kind==='speech'?'输入要说出的台词…':'描述声音的质感、节奏、力度和用途…'):'描述形状、材质、风格和用途…';
    const body=(Number(v.end)-Number(v.start))/Number(v.rate),target=body+Number(v.tail);
    $('window-summary').textContent=v.mode==='source'?'保存时从项目配置读取窗口，并记录版本；配置改变后需重新准备任务。':
      Number.isFinite(target)&&body>0?`主体 ${body.toFixed(3)} 秒 + 尾音 ${Number(v.tail).toFixed(3)} 秒；生成请求 ${Math.max(.5,target).toFixed(3)} 秒，另存 ${target.toFixed(3)} 秒的校准副本。`:'请填写有效的起止时间和播放倍率。';
  }
  $('audio-fields').addEventListener('input',update);$('brief-provider').addEventListener('change',update);
  return {update,parameters:()=>audioParameters(values())};
}

export function audioReview(audio,esc){
  if(!audio)return '';
  const p=audio.plan,o=audio.observations,fit=o?.timing_fit,m=fit?.measurement||o?.measurement;
  const source={current:'游戏配置版本一致',manual_unverified:'手动窗口，尚未核对引擎',changed_or_missing:'游戏配置已变化或缺失，请重新校准'}[audio.source_status];
  return '<section class="audio-review"><h3>音频与游戏时序</h3>'+
    (p?`<p><strong>${esc(p.event)}</strong> · 主体 ${p.body_seconds.toFixed(3)} 秒 · 尾音 ${p.tail_seconds.toFixed(3)} 秒</p><p>请求生成 ${p.generation_seconds.toFixed(3)} 秒${p.fit?`，另存 ${p.target_seconds.toFixed(3)} 秒的校准副本`:''}。${esc(source||'')}</p>`:'')+
    (m?`<p>实测 ${Number(m.duration_seconds).toFixed(3)} 秒 · ${esc(m.sample_rate)} Hz · ${esc(m.channels)} 声道${m.silent?' · 未检测到高于阈值的信号':''}${m.clipped_samples?' · 检测到满幅样本':''}${fit?.padded_frames?' · 原声不足，末尾补了静音':''}</p>`:'')+
    `<p>${audio.kind==='music'?'音乐用于商业游戏前需核对账户适用授权。':''}原件保留；起音、峰值、尾音与实际游戏播放效果需试听验收。</p></section>`;
}
