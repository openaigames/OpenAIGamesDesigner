/* Deterministic composition only; original images are never recolored or cropped. */
window.moodboardLoadImage = src => new Promise((resolve,reject)=>{
  const image=new Image(),timer=setTimeout(()=>reject(Error('图片加载超时')),15000);
  image.onload=()=>{clearTimeout(timer);if(image.naturalWidth*image.naturalHeight>50000000)reject(Error('单张参考超过 5000 万像素，请提供显示用副本并保留原件'));else resolve(image);};
  image.onerror=()=>{clearTimeout(timer);reject(Error('参考图片无法解码或读取'));};image.src=src;
});
window.renderMoodboardPNG=async board=>{
  if(!board.references.some(r=>r.role==='primary'))throw Error('至少需要一张主要参考图');
  const images=await Promise.all(board.references.map(async ref=>({ref,image:await window.moodboardLoadImage(ref.data||ref.file)})));
  await document.fonts.ready;
  const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
  if(!ctx)throw Error('浏览器不支持画布导出');
  const font='"Microsoft YaHei","Segoe UI",sans-serif',W=2000,M=52,S=350,G=24,grid=W-M*2-S-38;
  function lines(text,width,size){ctx.font='400 '+size+'px '+font;const result=[];for(const paragraph of String(text||'').split('\n')){let line='';for(const char of paragraph){if(ctx.measureText(line+char).width>width&&line){result.push(line);line=char;}else line+=char;}result.push(line);}return result;}
  function write(text,x,y,size=22,color='#263E37',weight=400){ctx.font=weight+' '+size+'px '+font;ctx.fillStyle=color;ctx.fillText(text,x,y);}
  function paragraph(text,x,y,width,size=20,color='#68766E'){const list=lines(text,width,size);list.forEach((line,i)=>write(line,x,y+i*size*1.5,size,color));return list.length*size*1.5;}
  const titleLines=lines(board.title,grid,42),intentLines=lines(board.intent,grid,22);
  const top=Math.ceil(105+titleLines.length*60+intentLines.length*33+45);
  const cards=[];let y=top;
  function height(item,width,hero){const ih=hero?560:340;return ih+28+lines(item.ref.id+' · '+item.ref.title,width-32,24).length*36+lines(item.ref.note,width-32,20).length*30+lines(item.ref.sourceLabel||'来源待补充',width-32,17).length*26+22;}
  for(const role of ['primary','supporting']){
    const group=images.filter(item=>item.ref.role===role);if(!group.length)continue;
    cards.push({label:role==='primary'?'主要风格参考':'补充结构与细节',y});y+=40;
    if(role==='primary'){const first=group.shift(),h=height(first,grid,true);cards.push({...first,x:M,y,w:grid,h,ih:560});y+=h+G;}
    for(let i=0;i<group.length;i+=2){const pair=group.slice(i,i+2),width=(grid-G)/2,h=Math.max(...pair.map(item=>height(item,width,false)));
      pair.forEach((item,j)=>cards.push({...item,x:M+j*(width+G),y,w:width,h,ih:340}));y+=h+G;}
  }
  const paletteHeight=90+board.palette.reduce((sum,c)=>sum+Math.max(116,lines(c.name,S-116,22).length*33+62)+18,0);
  const H=Math.ceil(Math.max(y,top+paletteHeight+140)+65);
  if(H>16000)throw Error('当前内容超过单张画布容量，请按方向拆板或缩短图注；没有省略图片');
  canvas.width=W;canvas.height=H;ctx.fillStyle='#F3F1EA';ctx.fillRect(0,0,W,H);
  write('ART DIRECTION / MOODBOARD',M,43,17,'#68766E');
  titleLines.forEach((line,i)=>write(line,M,106+i*60,42,'#263E37',600));
  intentLines.forEach((line,i)=>write(line,M,106+titleLines.length*60+i*33,22,'#68766E'));
  const sx=W-M-S,state={candidate:'候选方向',selected:'已选用方向',deferred:'暂缓'}[board.status];
  write((board.scope==='asset'?'单项资产':'游戏主题')+' · '+state,sx,53,20);
  write('v'+board.revision,sx,87,23);
  if(board.parent)paragraph('关联主题 '+board.parent.id+' / v'+board.parent.revision,sx,125,S,18);
  for(const card of cards){
    if(card.label){write(card.label,M,card.y+24,24,'#263E37',600);continue;}
    const {x,y,w,h,ih,image,ref}=card;ctx.fillStyle='#FFFEFA';ctx.fillRect(x,y,w,h);ctx.fillStyle='#E3E6DF';ctx.fillRect(x,y,w,ih);
    const scale=Math.min(w/image.naturalWidth,ih/image.naturalHeight),iw=image.naturalWidth*scale,hh=image.naturalHeight*scale;
    ctx.drawImage(image,x+(w-iw)/2,y+(ih-hh)/2,iw,hh);
    let cy=y+ih+32;cy+=paragraph(ref.id+' · '+ref.title,x+16,cy,w-32,24,'#263E37');cy+=paragraph(ref.note,x+16,cy+3,w-32,20);paragraph(ref.sourceLabel||'来源待补充',x+16,cy+10,w-32,17);
  }
  write('主要颜色',sx,top+24,24,'#263E37',600);write(board.palette.length+' 色 · 原图保留原貌',sx,top+57,18,'#68766E');
  let sy=top+83;
  for(const color of board.palette){const h=Math.max(116,lines(color.name,S-116,22).length*33+62);ctx.fillStyle='#FFFEFA';ctx.fillRect(sx,sy,S,h);ctx.fillStyle=color.hex;ctx.fillRect(sx+14,sy+14,76,h-28);const used=paragraph(color.name,sx+108,sy+35,S-116,22,'#263E37');write(color.hex.toUpperCase(),sx+108,sy+used+43,23);sy+=h+18;}
  paragraph('色值为当前方向依据。详细来源、继承关系和选用依据见同版本编辑数据。',sx,sy+18,S,18);
  write(board.id+' / v'+board.revision+' · '+board.references.length+' 张参考 · Art Direction',M,H-28,17,'#68766E');
  const result=canvas.toDataURL('image/png');if(!result.startsWith('data:image/png;base64,'))throw Error('浏览器无法导出当前画布');return result;
};
