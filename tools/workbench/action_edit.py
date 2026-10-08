"""Editable action sequences with explicit project consumers and immutable history."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import uuid
import wave
import struct
from .action_review import contained, read_json, digest, finite, label, ENGINES

MANIFEST = '.openaigame/action-editor.json'
PREFIX = '.openaigame/action-edits'
SCHEMA = 'action-sequence/1'

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value):
        raise ValueError('动作或片段编号无效')
    return value

def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
        tmp.replace(path)
    finally:tmp.unlink(missing_ok=True)

def entries(root):
    path=contained(root,MANIFEST)
    if not path.exists():return []
    doc,_=read_json(path)
    if doc.get('schema')!='action-editor/1':raise ValueError('动作编辑目录版本不支持')
    seen=set()
    for item in doc['actions']:
        key=identifier(item['id'])
        if key in seen:raise ValueError('动作编号重复')
        seen.add(key)
        label(item['title'],'动作名称')
        if item['engine'] not in ENGINES:raise ValueError('引擎类型无效')
        target=contained(root,item['file'])
        if target.suffix!='.json' or item['file'].startswith('.openaigame/'):
            raise ValueError('引擎配置必须是项目中的独立 JSON 文件')
    return doc['actions']

def entry(root,key):
    identifier(key)
    for item in entries(root):
        if item['id']==key:return item
    raise ValueError('动作未登记')

def end(item):return item['start_s']+(item['source_out_s']-item['source_in_s'])/item['rate']

def validate(seq, current=None):
    if seq.get('schema')!=SCHEMA:raise ValueError('动作片段格式不支持')
    identifier(seq.get('id'));label(seq.get('title'),'动作名称')
    duration=finite(seq.get('duration_s'),'总时长',.01)
    if duration>120:raise ValueError('单个动作不能超过 120 秒')
    if set(seq)!={'schema','id','title','duration_s','tracks','assets','clips','events','windows'}:
        raise ValueError('动作包含不支持的字段')
    tracks={};assets={};ids=set()
    for t in seq['tracks']:
        k=identifier(t['id']);label(t['label'],'轨道名称')
        if k in tracks or t['kind'] not in ('animation','audio','logic'):raise ValueError('轨道重复或类型无效')
        tracks[k]=t
    for a in seq['assets']:
        k=identifier(a['id']);label(a['label'],'素材名称');label(a['binding'],'引擎素材绑定')
        if k in assets or a['kind'] not in ('animation','audio'):raise ValueError('素材重复或类型无效')
        if finite(a['duration_s'],'素材长度',.001)>120:raise ValueError('素材过长')
        assets[k]=a
    if len(seq['clips'])+len(seq['events'])+len(seq['windows'])>256:raise ValueError('请把动作拆成较短的段落')
    for c in seq['clips']:
        if set(c)!={'id','label','track','asset','start_s','source_in_s','source_out_s','rate','blend_in_s','blend_out_s','volume'}:raise ValueError('片段字段无效')
        k=identifier(c['id']);label(c['label'],'片段名称')
        if k in ids:raise ValueError('片段或事件编号重复')
        ids.add(k);a=assets.get(c['asset']);t=tracks.get(c['track'])
        if not a or not t or a['kind']!=t['kind']:raise ValueError('片段与轨道类型不符')
        finite(c['start_s'],'开始时刻');finite(c['source_in_s'],'素材入点');finite(c['source_out_s'],'素材出点')
        rate=finite(c['rate'],'播放速度',.1)
        if rate>4:raise ValueError('播放速度范围为 0.1–4')
        if not c['source_in_s']<c['source_out_s']<=a['duration_s']+.0001:raise ValueError('裁剪范围超出素材')
        if end(c)>duration+.0001:raise ValueError('片段超出动作总时长')
        length=end(c)-c['start_s']
        if finite(c['blend_in_s'],'进入过渡')+finite(c['blend_out_s'],'退出过渡')>length+.0001:raise ValueError('过渡时间超过片段长度')
        if finite(c['volume'],'音量')>2:raise ValueError('音量范围为 0–2')
    for collection in ('events','windows'):
        for e in seq[collection]:
            allowed={'id','label','track','time_s'} if collection=='events' else {'id','label','track','start_s','end_s'}
            if set(e)!=allowed:raise ValueError('事件或窗口字段无效')
            k=identifier(e['id']);label(e['label'],'事件名称')
            if k in ids or e['track'] not in tracks or tracks[e['track']]['kind']!='logic':raise ValueError('事件重复或轨道无效')
            ids.add(k)
            if collection=='events':
                if finite(e['time_s'],'事件时刻')>duration:raise ValueError('事件超出动作时长')
            else:
                if not 0<=finite(e['start_s'],'窗口开始')<finite(e['end_s'],'窗口结束')<=duration:raise ValueError('窗口范围无效')
    # This editor changes timings, not skeleton, assets, event names or project bindings.
    if current:
        for k in ('id','title','tracks','assets'):
            if seq[k]!=current[k]:raise ValueError('素材和轨道绑定已改变，请重新登记动作')
        for kind in ('clips','events','windows'):
            if [x['id'] for x in seq[kind]]!=[x['id'] for x in current[kind]]:raise ValueError('动作结构已改变，请重新登记动作')
            for a,b in zip(seq[kind],current[kind]):
                for k in ('label','track','asset'):
                    if a.get(k)!=b.get(k):raise ValueError('不能通过时间调整更换素材绑定')
    return seq

def current(root,key):
    e=entry(root,key);seq,sha=read_json(contained(root,e['file']));validate(seq)
    if seq['id']!=key:raise ValueError('动作编号与配置不一致')
    return e,seq,sha

def changes(before,after):
    rows=[]
    if before['duration_s']!=after['duration_s']:rows.append({'id':'duration','label':'总时长','field':'duration_s','before':before['duration_s'],'after':after['duration_s']})
    for kind in ('clips','events','windows'):
        for a,b in zip(before[kind],after[kind]):
            for k in a:
                if a[k]!=b[k]:rows.append({'id':a['id'],'label':a['label'],'field':k,'before':a[k],'after':b[k]})
    return rows

def snapshot(root):
    result=[]
    for e in entries(root):
        _,s,h=current(root,e['id'])
        result.append({'id':e['id'],'title':e['title'],'engine':e['engine'],'duration_s':s['duration_s'],'hash':h})
    return {'actions':result}

def detail(root,key):
    e,s,h=current(root,key);base=contained(root,PREFIX+'/'+key)
    draft=None
    if (base/'draft.json').exists():
        draft,_=read_json(base/'draft.json');validate(draft['sequence'],s)
        draft['stale']=draft['base_hash']!=h
    history=[]
    for p in sorted(base.glob('history/*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
        row,_=read_json(p);history.append({'id':p.stem,'changes':row['changes'],'after_hash':row['after_hash']})
    return {'entry':e,'sequence':s,'hash':h,'draft':draft,'history':history}

def save(root,data):
    e,s,h=current(root,data['id'])
    if data.get('base_hash')!=h:raise ValueError('引擎配置已变化，请重新载入后核对')
    candidate=validate(copy.deepcopy(data['sequence']),s)
    # Projects can further restrict fields that their engine consumer supports.
    for row in changes(s,candidate):
        fields=e.get('editable',{}).get(row['id'],[])
        if row['field'] not in fields:raise ValueError(row['label']+' 的这个参数尚未接入当前引擎')
    draft={'schema':'action-draft/1','base_hash':h,'sequence':candidate,'changes':changes(s,candidate)}
    draft['draft_hash']=hashlib.sha256(json.dumps(draft,sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest()
    write(contained(root,PREFIX+'/'+e['id']+'/draft.json'),draft)
    return draft

def apply(root,data):
    e,s,h=current(root,data['id']);path=contained(root,PREFIX+'/'+e['id']+'/draft.json')
    draft,_=read_json(path)
    if data.get('draft_hash')!=draft.get('draft_hash'):raise ValueError('草案已在另一个页面改变，请重新保存并核对')
    if h!=draft['base_hash'] or h!=data.get('base_hash'):raise ValueError('配置已变化，草案不能覆盖新版本')
    validated=save(root,{'id':e['id'],'base_hash':h,'sequence':draft['sequence']})
    if not validated['changes']:raise ValueError('草案没有修改')
    target=contained(root,e['file']);previous=target.read_bytes()
    if hashlib.sha256(previous).hexdigest()!=h:raise ValueError('配置已被另一个程序修改')
    token=uuid.uuid4().hex;folder=contained(root,PREFIX+'/'+e['id']+'/history')
    folder.mkdir(parents=True,exist_ok=True);(folder/(token+'.before')).write_bytes(previous)
    write(target,draft['sequence']);after=digest(target)
    write(folder/(token+'.json'),{'before_hash':h,'after_hash':after,'changes':draft['changes']})
    path.unlink()
    return {'id':token,'hash':after,'message':'已写入项目配置。重新运行引擎后才会得到新画面和新记录。'}

def restore(root,data):
    e,s,h=current(root,data['id']);token=identifier(data['history_id'])
    folder=contained(root,PREFIX+'/'+e['id']+'/history');record,_=read_json(folder/(token+'.json'))
    if h!=data.get('base_hash') or h!=record['after_hash']:raise ValueError('配置已继续变化，不能直接恢复这一版')
    raw=(folder/(token+'.before')).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=record['before_hash']:raise ValueError('保存的旧版本已变化')
    old=json.loads(raw.decode('utf-8-sig'));draft=save(root,{'id':e['id'],'base_hash':h,'sequence':old})
    return apply(root,{'id':e['id'],'base_hash':h,'draft_hash':draft['draft_hash']})

def audio_path(root,key,asset_id):
    e,s,h=current(root,key)
    for a in s['assets']:
        if a['id']==asset_id and a['kind']=='audio':
            path=contained(root,a['preview'])
            if path.suffix.lower()!='.wav' or path.stat().st_size>64*1024**2 or digest(path)!=a['sha256']:raise ValueError('声音文件已变化或格式不支持')
            return path
    raise ValueError('没有登记该声音素材')

def waveform(root,key,asset_id):
    path=audio_path(root,key,asset_id)
    with wave.open(str(path),'rb') as w:
        width=w.getsampwidth();channels=w.getnchannels();count=w.getnframes();rate=w.getframerate()
        if width not in (1,2,3,4) or count==0:raise ValueError('波形需要 PCM WAV')
        raw=w.readframes(count)
    bins=600;peaks=[];step=max(1,math.ceil(count/bins));stride=width*channels
    for start in range(0,count,step):
        value=0
        for at in range(start*stride,min(count,start+step)*stride,width):
            v=int.from_bytes(raw[at:at+width],'little',signed=width!=1)
            if width==1:v-=128
            value=max(value,abs(v)/(2**(width*8-1)))
        peaks.append(round(value,5))
    return {'duration_s':count/rate,'peaks':peaks,'sha256':digest(path),'source':'PCM samples from registered audio file'}
