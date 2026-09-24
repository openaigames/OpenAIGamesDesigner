"""Local asset browser with Art Direction as the sole tag and registration source."""
import argparse, hashlib, json, mimetypes, os, struct, time, threading, uuid
from . import art_registry, model_previews
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, quote, parse_qs

HERE=Path(__file__).resolve().parent
WEB=HERE/'web'
SKIP={'.git','.svn','.asset-browser','.openaigame','node_modules','Intermediate','Binaries','DerivedDataCache','Saved','.idea','.vscode','dist','Library','Temp','obj','builds','Licenses'}
KINDS={'.glb':'model','.gltf':'model','.obj':'model','.fbx':'model','.stl':'model','.png':'image','.jpg':'image','.jpeg':'image','.webp':'image','.gif':'image','.svg':'image','.wav':'audio','.ogg':'audio','.mp3':'audio','.flac':'audio','.m4a':'audio','.mp4':'video','.webm':'video','.uasset':'engine','.umap':'engine','.tscn':'engine','.tres':'engine','.prefab':'engine','.vfx':'engine','.efkefc':'engine','.blend':'engine','.dds':'texture','.tga':'texture','.exr':'texture','.hdr':'texture','.ktx2':'texture','.ttf':'other','.otf':'other'}
MIME={'.glb':'model/gltf-binary','.gltf':'model/gltf+json','.js':'text/javascript','.ogg':'audio/ogg','.json':'application/json','.bin':'application/octet-stream'}
TAG_LOCK=threading.Lock()

def metadata_path(root, name):
    path=root/'.asset-browser'/name
    if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Invalid metadata directory')
    return path

def game_name(project):
    try:return art_registry.load(project['root'])['game']
    except (OSError,ValueError):pass
    try:
        name=json.loads(metadata_path(project['root'],'project.json').read_text(encoding='utf-8')).get('gameName')
        if isinstance(name,str) and name.strip():return name.strip()[:80]
    except (OSError,ValueError,AttributeError):pass
    return project['name']

def within(root,relative):
    if '\\' in relative or ':' in relative or '\x00' in relative: raise ValueError('Invalid path')
    parts=Path(relative).parts
    if any(x.startswith('.') for x in parts): raise ValueError('Hidden path')
    p=(root/relative).resolve()
    if not p.is_relative_to(root.resolve()): raise ValueError('Outside project')
    return p

def gltf_info(path):
    try:
        if path.suffix.lower()=='.glb':
            with path.open('rb') as f:
                magic,version,length=struct.unpack('<4sII',f.read(12))
                size,kind=struct.unpack('<II',f.read(8))
                if magic!=b'glTF' or version!=2 or kind!=0x4E4F534A or size>4*1024*1024:return {}
                data=json.loads(f.read(size))
        else:
            if path.stat().st_size>4*1024*1024:return {}
            data=json.loads(path.read_text(encoding='utf-8'))
        accessors=data.get('accessors',[])
        triangles=0
        for mesh in data.get('meshes',[]):
            for p in mesh.get('primitives',[]):
                if p.get('mode',4)==4:
                    i=p.get('indices',p.get('attributes',{}).get('POSITION'))
                    if isinstance(i,int) and i<len(accessors):triangles+=accessors[i].get('count',0)//3
        return {'animations':[a.get('name',f'Animation {i+1}') for i,a in enumerate(data.get('animations',[]))],
                'meshes':len(data.get('meshes',[])),'materials':len(data.get('materials',[])),
                'bones':len({j for s in data.get('skins',[]) for j in s.get('joints',[])}),'triangles':triangles}
    except (OSError,ValueError,KeyError,struct.error,TypeError):return {'parseError':True}

def library_metadata(root):
    """Read only registered output paths, never expose hidden job/configuration files."""
    rows={}
    for pattern,field in [('.openaigame/asset-library/*/record.json','files'),('.openaigame/asset-jobs/*/job.json','artifacts')]:
        for record in root.glob(pattern):
            try:
                if record.is_symlink() or not record.resolve().is_relative_to(root.resolve()) or record.stat().st_size>4*1024*1024:continue
                data=json.loads(record.read_text(encoding='utf-8-sig'))
                for entry in data.get(field,[]):
                    relative=entry.get('path','');target=art_registry.asset_path(root,relative)
                    if not target.is_file():continue
                    info={}
                    if field=='files':
                        for original,key in [('title','title'),('author','author'),('source_url','source')]:
                            if isinstance(data.get(original),str):info[key]=data[original]
                        license=data.get('license',{})
                        if isinstance(license,dict) and isinstance(license.get('name'),str):info['license']=license['name']
                    rows[relative]=info
            except (OSError,ValueError,TypeError,AttributeError):continue
    return rows


def asset_files(root,registered):
    seen=set()
    for folder,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d not in SKIP and not d.startswith('.') and not (Path(folder)/d).is_symlink() and not (hasattr(Path(folder)/d,'is_junction') and (Path(folder)/d).is_junction())]
        for name in sorted(files):
            p=Path(folder)/name
            if p.is_symlink() or name.startswith('.') or not p.resolve().is_relative_to(root.resolve()):continue
            seen.add(p.relative_to(root).as_posix());yield p
    for relative in registered:
        if relative not in seen:
            try:
                p=art_registry.asset_path(root,relative)
                if p.is_file():yield p
            except (OSError,ValueError):continue


def scan(root):
    preview_records,preview_error=model_previews.read(root)
    registry=None;registry_error=None
    try:registry=art_registry.load(root)
    except (OSError,ValueError) as error:registry_error=str(error)
    ledger=root/'.asset-browser/catalog.json'
    try:catalog=json.loads(ledger.read_text(encoding='utf-8')) if ledger.exists() else {}
    except (OSError,ValueError):catalog={}
    if not isinstance(catalog,dict):catalog={}
    library=library_metadata(root)
    catalog={**library,**catalog}
    items=[]
    for p in asset_files(root,library):
        name=p.name
        if p.is_symlink() or name.startswith('.'):continue
        ext=p.suffix.lower(); kind='vfx' if name.endswith('.vfx.json') else KINDS.get(ext)
        if not kind:continue
        try:
            rel=p.relative_to(root).as_posix(); stat=p.stat()
            row={'id':hashlib.sha256(rel.encode()).hexdigest()[:16],'path':rel,'name':name,'title':p.stem,'kind':kind,
                 'ext':('VFX' if kind=='vfx' else ext[1:]).upper(),'bytes':stat.st_size,'modified':stat.st_mtime,
                 'url':'/asset/'+quote(rel,safe='/'),'folder':p.parent.relative_to(root).as_posix(),'tags':[],
                 'source':None,'author':'未登记','license':'未登记'}
            row.update({k:v for k,v in (catalog.get(rel,{}) if isinstance(catalog.get(rel,{}),dict) else {}).items() if k in {'title','source','author','license','note','texture','color','rank'}})
            row['art']=art_registry.classify(root,row,registry) if registry else None
            row['tags']=row['art']['tags'] if row['art'] else []
            row['preview']='native' if ext in {'.glb','.gltf','.obj','.png','.jpg','.jpeg','.webp','.gif','.svg','.wav','.ogg','.mp3','.mp4','.webm','.m4a'} or kind=='vfx' else 'unavailable'
            row['assetRoot']='/asset/'
            if rel in preview_records:
                row.update(model_previews.resolve(root,rel,preview_records[rel],gltf_info))
                if row.get('previewPath'):row['previewUrl']='/asset/'+quote(row['previewPath'],safe='/')
            if ext in {'.glb','.gltf'}:row.update(gltf_info(p))
            if ext=='.png':
                with p.open('rb') as f:header=f.read(24)
                if header[:8]==b'\x89PNG\r\n\x1a\n':row['width'],row['height']=struct.unpack('>II',header[16:24])
            items.append(row)
        except (OSError,ValueError,struct.error):continue
    items.sort(key=lambda a:(a.get('rank',100),0 if a.get('animations') else 1 if a['kind']=='model' else 2 if a['kind']=='vfx' else 3,a['path']))
    return {'project':game_name({'root':root,'name':root.name}),'root':str(root),'projectId':hashlib.sha256(str(root).encode()).hexdigest()[:16],'previewMappingError':preview_error,
            'assets':items,'artAudit':{**art_registry.audit(items,registry,registry_error),'canInitialize':art_registry.can_initialize(root)},'artObjects':list(registry['objects'].values()) if registry else [],'artRevision':registry['revision'] if registry else None,'scannedAt':time.time(),'totalBytes':sum(x['bytes'] for x in items),'demo':False}
