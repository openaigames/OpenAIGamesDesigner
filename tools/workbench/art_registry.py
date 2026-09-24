"""Art Direction is the single editable source for objects, tags and asset records."""
import hashlib, html, re, uuid, os, json
from pathlib import Path
from functools import lru_cache

OBJECT_COLUMNS=['对象 ID','对象/用途','标签']
ASSET_COLUMNS=['资产 ID','对象 ID','类型','名称','文件路径','SHA-256','制作/导入状态','来源与许可']

class RegistryError(ValueError):pass
class RevisionConflict(RegistryError):pass

def document_path(root):
    config=root/'.openaigame/workbench.json'
    relative='Art Direction.md'
    if config.exists():
        if not config.resolve().is_relative_to(root.resolve()):raise RegistryError('看板配置路径不在项目内')
        settings=json.loads(config.read_text(encoding='utf-8-sig'))
        relative=settings.get('art_document',relative)
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute() or ':' in relative or '..' in Path(relative).parts:raise RegistryError('美术文档路径无效')
    path=(root/relative).resolve()
    if path.suffix.lower()!='.md' or not path.is_relative_to(root.resolve()):raise RegistryError('美术文档须是项目内 Markdown')
    return path


def asset_path(root,relative):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute() or '\\' in relative or ':' in relative or any(ord(c)<32 for c in relative):raise RegistryError('资产路径无效')
    parts=Path(relative).parts
    if any(p.startswith('.') for p in parts):
        if len(parts)<5 or parts[:2] not in (('.openaigame','asset-library'),('.openaigame','asset-jobs')) or any(p.startswith('.') for p in parts[1:]):raise RegistryError('资产路径无效')
        if parts[1]=='asset-library' and parts[3]!='files':raise RegistryError('资产路径无效')
        if parts[1]=='asset-jobs' and (len(parts)<6 or not parts[3].startswith('attempt-') or parts[4]!='output'):raise RegistryError('资产路径无效')
    target=root/relative
    for parent in [target,*target.parents]:
        if parent==root.parent:break
        if parent.is_symlink() or (hasattr(parent,'is_junction') and parent.is_junction()):raise RegistryError('不读取链接目录中的资产')
    target=target.resolve()
    if not target.is_relative_to(root.resolve()):raise RegistryError('资产路径不在项目内')
    return target


def can_initialize(root):
    try:
        path=document_path(root)
        text=path.read_text(encoding='utf-8-sig') if path.exists() else ''
        return '<!-- art-objects:' not in text and '<!-- art-assets:' not in text
    except (OSError,ValueError):return False


def initialize(root):
    """Explicit opt-in: append empty tables, preserving legacy narrative and records."""
    path=document_path(root)
    if not can_initialize(root):
        load(root)  # Already valid is idempotent; partial/damaged markers are errors.
        return False
    original=path.read_bytes() if path.exists() else None
    text=(original.decode('utf-8-sig') if original is not None else '# '+root.name+' · 美术方向\n')
    text+='\n\n## 看板对象与标签\n\n标签由本美术入口统一维护；现有清单的对象与稳定 ID 沿用原记录，未知用途保留待补齐。\n\n<!-- art-objects:start -->\n'+table(OBJECT_COLUMNS,[])+'\n<!-- art-objects:end -->\n\n## 本地资产文件映射\n\n登记不代表已采用、已导入或已验收；计划项继续保留在原有规格中。\n\n<!-- art-assets:start -->\n'+table(ASSET_COLUMNS,[])+'\n<!-- art-assets:end -->\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    if original is None:
        with path.open('xb') as stream:stream.write(text.encode('utf-8'))
    else:
        temp=path.with_name('.art-direction-'+uuid.uuid4().hex+'.tmp')
        try:
            temp.write_bytes(text.encode('utf-8'))
            if path.read_bytes()!=original:raise RevisionConflict('文档已被修改，请重试')
            os.replace(temp,path)
        finally:temp.unlink(missing_ok=True)
    return True


def block(text,name):
    pattern=rf'<!-- {name}:start -->\s*\n(.*?)\n<!-- {name}:end -->'
    matches=list(re.finditer(pattern,text,re.S))
    if len(matches)!=1:raise RegistryError('Art Direction 记录区缺失或重复，请先修复文档')
    return matches[0]

def parse_table(content,columns):
    lines=[x.strip() for x in content.splitlines() if x.strip()]
    if len(lines)<2:raise RegistryError('美术记录表不完整')
    def cells(line):
        if not line.startswith('|') or not line.endswith('|'):raise RegistryError('美术记录表格式不完整')
        return [html.unescape(x.strip()) for x in line[1:-1].split('|')]
    if cells(lines[0])!=columns:raise RegistryError('美术记录表列名不匹配')
    if not all(re.fullmatch(r':?-+:?',x) for x in cells(lines[1])):raise RegistryError('美术记录表分隔行无效')
    result=[]
    for line in lines[2:]:
        values=cells(line)
        if len(values)!=len(columns):raise RegistryError('美术记录表列数不匹配')
        result.append(dict(zip(columns,['' if v=='—' else v for v in values])))
    return result

def validate_tags(tags):
    if not isinstance(tags,list) or len(tags)>20 or any(not isinstance(t,str) or not 1<=len(t.strip())<=24 or t.strip()=='—' or any(ord(c)<32 or c in '|、' for c in t) for t in tags):
        raise RegistryError('标签最多 20 个，每个 1–24 字，不含换行、竖线或顿号')
    return list(dict.fromkeys(t.strip() for t in tags))

def load(root):
    path=document_path(root)
    if not path.exists():raise RegistryError('项目尚未建立 Art Direction 资产记录')
    raw=path.read_bytes()
    if len(raw)>2*1024*1024:raise RegistryError('美术记录文件过大')
    text=raw.decode('utf-8-sig')
    objects={};assets={};ids=set()
    for row in parse_table(block(text,'art-objects').group(1),OBJECT_COLUMNS):
        key=row['对象 ID']
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key) or key in objects:raise RegistryError('对象 ID 无效或重复')
        objects[key]={'id':key,'label':row['对象/用途'],'tags':validate_tags(row['标签'].split('、') if row['标签'] else [])}
    for row in parse_table(block(text,'art-assets').group(1),ASSET_COLUMNS):
        key=row['资产 ID'];relative=row['文件路径'];object_id=row['对象 ID']
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key) or key in ids or relative in assets:raise RegistryError('资产 ID 或路径重复/无效')
        asset_path(root,relative)
        if object_id and object_id not in objects:raise RegistryError('资产引用了不存在的对象 ID')
        if not re.fullmatch(r'[a-f0-9]{64}',row['SHA-256']):raise RegistryError('资产版本哈希无效')
        ids.add(key);assets[relative]={'id':key,'objectId':object_id,'kind':row['类型'],'title':row['名称'],'path':relative,'sha256':row['SHA-256'],'stage':row['制作/导入状态'],'source':row['来源与许可']}
    title=next((line[2:].strip() for line in text.splitlines() if line.startswith('# ')),root.name)
    title=re.sub(r'\s*·\s*(美术方向|Art Direction)\s*$','',title)
    return {'text':text,'revision':hashlib.sha256(raw).hexdigest(),'objects':objects,'assets':assets,'game':title}

def cell(value):return html.escape(str(value),quote=False).replace('|','&#124;').replace('\r',' ').replace('\n',' ') or '—'
def table(columns,rows):
    return '\n'.join(['| '+' | '.join(columns)+' |','| '+' | '.join('---' for _ in columns)+' |']+['| '+' | '.join(cell(v) for v in row)+' |' for row in rows])

def write(root,data,revision):
    current=load(root)
    if current['revision']!=revision:raise RevisionConflict('Art Direction 已被修改，请刷新后再保存')
    text=current['text']
    content={
        'art-objects':table(OBJECT_COLUMNS,[[o['id'],o['label'],'、'.join(o['tags'])] for o in data['objects'].values()]),
        'art-assets':table(ASSET_COLUMNS,[[a['id'],a['objectId'],a['kind'],a['title'],a['path'],a['sha256'],a['stage'],a['source']] for a in data['assets'].values()])
    }
    for name,value in content.items():
        match=block(text,name);text=text[:match.start(1)]+value+text[match.end(1):]
    path=document_path(root);temporary=path.with_name('.art-direction-'+uuid.uuid4().hex+'.tmp')
    if len(text.encode('utf-8'))>2*1024*1024:raise RegistryError('美术记录超过 2 MB，请整理记录后再保存')
    try:
        temporary.write_bytes(text.encode('utf-8'))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=revision:raise RevisionConflict('Art Direction 已被修改，请刷新后再保存')
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()

@lru_cache(maxsize=256)
def _digest(path,size,mtime):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def digest(path):
    stat=path.stat();return _digest(str(path),stat.st_size,stat.st_mtime_ns)

def classify(root,asset,data):
    record=data['assets'].get(asset['path'])
    if not record:return None
    obj=data['objects'].get(record['objectId']);missing=[]
    if not obj or not obj['label']:missing.append('对象/用途')
    if not obj or not obj['tags']:missing.append('标签')
    changed=digest(root/asset['path'])!=record['sha256']
    return {'id':record['id'],'objectId':record['objectId'],'object':obj['label'] if obj else '',
            'tags':obj['tags'] if obj and not changed else [],'stage':record['stage'],
            'state':'version-changed' if changed else 'incomplete' if missing else 'linked','missingFields':missing}

def audit(assets,data,error=None):
    missing=[];incomplete=[];changed=[]
    for a in assets:
        brief={'path':a['path'],'title':a['title'],'kind':a['kind']}
        if not a.get('art'):missing.append(brief)
        elif a['art']['state']=='version-changed':changed.append({**brief,'id':a['art']['id']})
        elif a['art']['missingFields']:incomplete.append({**brief,'id':a['art']['id'],'missingFields':a['art']['missingFields']})
    paths={a['path'] for a in assets}
    absent=[{'path':a['path'],'id':a['id'],'title':a['title']} for a in data['assets'].values() if a['path'] not in paths] if data else []
    return {'document':'Art Direction.md','revision':data['revision'] if data else None,'error':error,
            'totalFiles':len(assets),'unregistered':missing,'incomplete':incomplete,'missingFiles':absent,'changedFiles':changed,
            'counts':{'unregistered':len(missing),'incomplete':len(incomplete),'missingFiles':len(absent),'changedFiles':len(changed)}}

def register(root,data,assets,paths):
    lookup={a['path']:a for a in assets}
    if any(path not in lookup for path in paths):raise RegistryError('部分资产已不存在，请刷新目录')
    added=[]
    for path in dict.fromkeys(paths):
        if path in data['assets']:continue
        a=lookup[path];key='A'+uuid.uuid4().hex[:16]
        license=a.get('license') or '未登记';author=a.get('author') or '未登记'
        data['assets'][path]={'id':key,'objectId':'','kind':a['kind'],'title':a['title'],'path':path,'sha256':digest(root/path),
                              'stage':'文件已发现；采用/导入/验证待确认','source':author+'；'+license+('；'+a['source'] if a.get('source') else '')}
        added.append(path)
    return added
