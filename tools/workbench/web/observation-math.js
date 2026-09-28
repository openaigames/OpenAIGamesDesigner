// Pure observation math shared by the viewer and behavioral regression tests.
export function seconds(data,clock,time){
 const definition=data.clocks.find(c=>c.id===clock);
 if(!definition)throw Error('Unknown source clock');
 return time*(definition.unit==='milliseconds'?.001:1);
}
export function rawTime(data,clock,value){return value/seconds(data,clock,1);}
export function duration(data,clock){
 let max=.001;
 for(const e of data.events)if(e.clock===clock)max=Math.max(max,seconds(data,clock,e.time));
 for(const c of [...(data.curves||[]),...(data.space?.routes||[])])
  if(c.clock===clock&&c.samples.length)max=Math.max(max,seconds(data,clock,c.samples.at(-1)[0]));
 for(const m of data.media||[])if(m.clock===clock&&m.anchors.length)max=Math.max(max,seconds(data,clock,m.anchors.at(-1)[0]));
 return max;
}
export function mediaTime(anchors,time){
 for(const [source,media] of anchors)if(time===source)return media;
 for(let i=1;i<anchors.length;i++){
  const [a,b]=anchors[i-1],[c,d]=anchors[i];
  if(time>a&&time<c&&c>a&&d>b)return b+(time-a)/(c-a)*(d-b);
 }
 return null; // No extrapolation across missing, paused or mismatched segments.
}
export function alignedOffset(left,leftId,right,rightId){
 const a=left.events.find(e=>e.id===leftId),b=right.events.find(e=>e.id===rightId);
 if(!a||!b)throw Error('Both measured anchors are required');
 return {seconds:seconds(right,b.clock,b.time)-seconds(left,a.clock,a.time),leftClock:a.clock,rightClock:b.clock};
}
export function extrema(values){
 let low=Infinity,high=-Infinity;
 for(const value of values){if(!Number.isFinite(value))throw Error('Non-finite observation');low=Math.min(low,value);high=Math.max(high,value);}
 return [low===Infinity?0:low,high===-Infinity?0:high];
}

export function camera2DCorners(projection){
 const [cx,cy]=projection.screen_center,[vw,vh]=projection.viewport_size,[zx,zy]=projection.zoom;
 const angle=projection.rotation_radians||0,c=Math.cos(angle),s=Math.sin(angle);
 return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([a,b])=>{const x=a*vw/zx/2,y=b*vh/zy/2;return [cx+c*x-s*y,cy+s*x+c*y];});
}
