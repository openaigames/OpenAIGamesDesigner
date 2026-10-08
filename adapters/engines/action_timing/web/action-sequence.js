// Shared by Three.js, Phaser and other browser games. Pass elapsed game time,
// not frame count. The host owns animation/audio objects and game rules.
export class ActionSequence {
  constructor(sequence, onSignal) {
    this.sequence=sequence; this.onSignal=onSignal; this.signals=[]; this.active=new Set();this.windows=new Set();this.running=false;this.time=0;this.cursor=0;
    const finite=(x,min=0,max=120)=>typeof x==='number'&&Number.isFinite(x)&&x>=min&&x<=max;
    if(sequence.schema!=='action-sequence/1'||!finite(sequence.duration_s,.01))throw Error('Invalid action sequence');
    const ids=new Set(),assets=new Map(sequence.assets.map(a=>[a.id,a]));
    const add=(time,kind,id,clip=null,order=0)=>this.signals.push({time,kind,id,clip,order});
    for(const c of sequence.clips){const a=assets.get(c.asset);if(ids.has(c.id)||!a||!finite(c.start_s)||!finite(c.source_in_s)||!finite(c.source_out_s)||!finite(c.rate,.1,4)||!finite(c.volume,0,2)||!finite(c.blend_in_s)||!finite(c.blend_out_s)||c.source_out_s<=c.source_in_s||c.source_out_s>a.duration_s+.0001)throw Error('Invalid clip');ids.add(c.id);const end=c.start_s+(c.source_out_s-c.source_in_s)/c.rate;if(end>sequence.duration_s+.0001||c.blend_in_s+c.blend_out_s>end-c.start_s+.0001)throw Error('Clip exceeds sequence');
      const clip={...c,binding:a.binding,kind:a.kind,end_s:end};add(c.start_s,'clip_start',c.id,clip,3);if(c.blend_out_s)add(end-c.blend_out_s,'clip_exit',c.id,clip,4);add(end,'clip_end',c.id,clip,0);
    }
    for(const e of sequence.events){if(ids.has(e.id)||!finite(e.time_s,0,sequence.duration_s))throw Error('Invalid event');ids.add(e.id);add(e.time_s,'event',e.id,null,2);}
    for(const w of sequence.windows){if(ids.has(w.id)||!finite(w.start_s)||!finite(w.end_s,0,sequence.duration_s)||w.end_s<=w.start_s)throw Error('Invalid window');ids.add(w.id);add(w.start_s,'window_open',w.id,null,1);add(w.end_s,'window_close',w.id,null,0);}
    this.signals.sort((a,b)=>a.time-b.time||a.order-b.order);
  }
  start(){this.stop();this.time=0;this.cursor=0;this.running=true;this.advance(0);}
  advance(elapsed){if(!this.running||!Number.isFinite(elapsed)||elapsed<this.time)return;this.time=elapsed;while(this.running&&this.cursor<this.signals.length&&this.signals[this.cursor].time<=elapsed+1e-7){const s=this.signals[this.cursor++];if(s.kind==='window_open')this.windows.add(s.id);if(s.kind==='window_close')this.windows.delete(s.id);if(s.kind==='clip_start')this.active.add(s.clip);if(s.kind==='clip_end')this.active.delete(s.clip);this.onSignal(s);}if(elapsed>=this.sequence.duration_s)this.running=false;}
  stop(){this.running=false;for(const id of [...this.windows])this.onSignal({time:this.time,kind:'window_cancel',id,clip:null});this.windows.clear();for(const clip of [...this.active])this.onSignal({time:this.time,kind:'clip_cancel',id:clip.id,clip});this.active.clear();this.running=false;}
}

// Ports keep existing engine animation controllers intact. Each project maps
// binding strings to real assets; missing handlers are errors, not silent no-ops.
export function bindSequence(sequence, ports) {
  for(const asset of sequence.assets)if(typeof ports[asset.kind]?.start!=='function'||typeof ports[asset.kind]?.stop!=='function')throw Error(`Missing ${asset.kind} consumer`);
  if(sequence.events.length&&typeof ports.event!=='function')throw Error('Missing gameplay event consumer');
  if(sequence.windows.length&&typeof ports.window!=='function')throw Error('Missing gameplay window consumer');
  return new ActionSequence(sequence,s=>{
    if(s.clip){const p=ports[s.clip.kind];if(s.kind==='clip_start')p.start(s.clip);else if(s.kind==='clip_exit'){if(!p.exit)throw Error('Missing fade/crossfade consumer');p.exit(s.clip);}else p.stop(s.clip,s.kind==='clip_cancel');}
    else if(s.kind==='event')ports.event(s.id);else ports.window(s.id,s.kind==='window_open');
  });
}
