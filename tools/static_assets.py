"""Freeze a bounded static-asset replacement plan; never edit an existing scene."""
import argparse,hashlib,json,math,struct,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from adapters.processing.procedural_worker import identifier,vector,number

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fingerprint(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def local(root,name):
    if not isinstance(name,str) or not name or Path(name).is_absolute():raise ValueError('Use a project-relative asset path')
    p=(root/name).resolve()
    if not p.is_relative_to(root) or not p.is_file():raise ValueError('Asset missing or outside project: '+name)
    return p
def inspect_glb(path):
    data=path.read_bytes()
    if len(data)<28 or struct.unpack('<4sII',data[:12])!=(b'glTF',2,len(data)):raise ValueError('Expected a complete GLB 2 file')
    length,kind=struct.unpack('<I4s',data[12:20])
    if kind!=b'JSON' or length%4 or 20+length+8>len(data):raise ValueError('GLB needs a complete JSON chunk and binary data')
    d=json.loads(data[20:20+length])
    offset=20+length;binary_length,binary_kind=struct.unpack('<I4s',data[offset:offset+8])
    if binary_kind!=b'BIN\0' or offset+8+binary_length!=len(data):raise ValueError('GLB binary chunk is incomplete')
    if len(d.get('buffers',[]))!=1 or not 0<=binary_length-d['buffers'][0]['byteLength']<=3:raise ValueError('GLB buffer length differs')
    if d.get('skins') or d.get('animations') or d.get('extensionsUsed') or d.get('textures') or d.get('images'):raise ValueError('First static release supports unskinned opaque scalar PBR GLB without textures/extensions')
    if len(d.get('meshes',[]))!=1 or len(d.get('nodes',[]))!=1 or d['nodes'][0].get('mesh')!=0:raise ValueError('Use one flattened static mesh and one node')
    node=d['nodes'][0]
    for k,v in [('translation',[0,0,0]),('rotation',[0,0,0,1]),('scale',[1,1,1]),('matrix',[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])]:
        if k in node and node[k]!=v:raise ValueError('Apply source node transforms before export')
    if any('uri' in b for b in d.get('buffers',[])):raise ValueError('GLB must be self-contained')
    materials=[]
    for m in d.get('materials',[]):
        if m.get('alphaMode','OPAQUE')!='OPAQUE' or m.get('doubleSided',False) or m.get('emissiveFactor',[0,0,0])!=[0,0,0]:raise ValueError('Only opaque single-sided non-emissive PBR materials supported')
        p=m.get('pbrMetallicRoughness',{});color=p.get('baseColorFactor',[1,1,1,1])
        if len(color)!=4 or color[3]!=1:raise ValueError('Opaque RGBA material required')
        materials.append({'name':identifier(m['name']),'base_color':[number(v,'base color',0,1) for v in color],
                          'roughness':number(p.get('roughnessFactor',1),'roughness',0,1),'metallic':number(p.get('metallicFactor',1),'metallic',0,1)})
    if not materials or len(materials)>8 or len({m['name'] for m in materials})!=len(materials):raise ValueError('Use 1..8 unique named materials')
    lower=[math.inf]*3;upper=[-math.inf]*3;triangles=0
    for p in d['meshes'][0]['primitives']:
        if p.get('mode',4)!=4 or p.get('targets') or not 0<=p.get('material',-1)<len(materials):raise ValueError('Static triangles with an explicit material required')
        pos=d['accessors'][p['attributes']['POSITION']]
        for k in range(3):lower[k]=min(lower[k],number(pos['min'][k],'bounds'));upper[k]=max(upper[k],number(pos['max'][k],'bounds'))
        count=d['accessors'][p['indices']]['count']
        if type(count)!=int or count<=0 or count%3:raise ValueError('Triangle index count must be positive and divisible by three')
        triangles+=count//3
    if not 1<=triangles<=1000000 or any(b<=a for a,b in zip(lower,upper)):raise ValueError('Invalid 3D mesh bounds or triangle budget')
    return {'bounds':[lower,upper],'triangles':triangles,'materials':materials}

def read_plan(folder):
    root=Path(folder).resolve();plan=json.loads((root/'plan.json').read_text(encoding='utf-8-sig'))
    payload={k:v for k,v in plan.items() if k!='plan_id'}
    if plan.get('schema')!='oagd.static-plan/1' or fingerprint(payload)!=plan.get('plan_id'):raise ValueError('Frozen plan changed; prepare a new version')
    baseline=local(root,plan['scene'])
    if sha(baseline)!=plan['scene_sha256']:raise ValueError('Frozen baseline changed')
    for asset in plan['assets']:
        if sha(local(root,asset['source']))!=asset['source_sha256']:raise ValueError('Frozen source changed')
    return plan

def prepare(project,scene_path,manifest_path,output):
    root=Path(project).resolve();scene_file=local(root,scene_path);manifest_file=local(root,manifest_path);out=Path(output).resolve()
    if out.exists():raise ValueError('Output must be a new version directory')
    scene=json.loads(scene_file.read_text(encoding='utf-8-sig'));manifest=json.loads(manifest_file.read_text(encoding='utf-8-sig'))
    if manifest.get('schema')!='oagd.static-assets/1' or set(manifest)-{'schema','scene_sha256','assets','replacements'}:raise ValueError('Unsupported replacement manifest')
    if scene.get('coordinates')!='RH_Y_UP_METRES_CCW' or manifest.get('scene_sha256')!=sha(scene_file):raise ValueError('Scene baseline changed; rebase mapping explicitly')
    meshes={m['id']:m for m in scene['meshes']}
    if len(meshes)!=len(scene['meshes']):raise ValueError('Duplicate scene IDs')
    assets={};inputs={}
    raw_assets=manifest.get('assets',[])
    if not isinstance(raw_assets,list) or not 1<=len(raw_assets)<=64:raise ValueError('Use 1..64 assets')
    for item in raw_assets:
        if set(item)!={'id','source','sha256'}:raise ValueError('Asset needs id, source and sha256')
        aid=identifier(item['id']);source=local(root,item['source'])
        if aid in assets or source.suffix.lower()!='.glb' or sha(source)!=item['sha256']:raise ValueError('Duplicate asset, unsupported source or source hash changed')
        info=inspect_glb(source);assets[aid]={'id':aid,'source':'sources/'+aid+'.glb','source_sha256':item['sha256'],**info};inputs[aid]=source
    replacements=[];used=set();ids=set();raw=manifest.get('replacements',[])
    if not isinstance(raw,list) or not 1<=len(raw)<=256:raise ValueError('Use 1..256 replacements')
    for row in raw:
        if set(row)!={'id','targets','asset','position','yaw_degrees','scale','collision'}:raise ValueError('Replacement fields must be explicit')
        rid=identifier(row['id']);targets=row['targets']
        if rid in ids or rid in meshes or row['asset'] not in assets:raise ValueError('Unknown asset or duplicate replacement ID')
        ids.add(rid)
        if not isinstance(targets,list) or not targets or len(targets)!=len(set(targets)) or any(t not in meshes or t in used for t in targets):raise ValueError('Missing or multiply replaced stable target ID')
        used.update(targets)
        if row['collision'] not in ('source_mesh','retain_graybox'):raise ValueError('Collision must be source_mesh or retain_graybox')
        replacements.append({**row,'position':vector(row['position'],'position'),'yaw_degrees':number(row['yaw_degrees'],'yaw',-180,180),'scale':number(row['scale'],'uniform scale',.01,100),
                             'target_fingerprints':{t:fingerprint(meshes[t]) for t in targets}})
    plan={'schema':'oagd.static-plan/1','scene_sha256':sha(scene_file),'scene':'baseline.json','assets':list(assets.values()),'replacements':replacements,
          'coordinates':'RH_Y_UP_METRES_CCW','material_policy':'opaque scalar PBR; native resources recreated by material slot name',
          'godot_lod':'native ImporterMesh automatic','unreal_lods':[{'percent_triangles':1,'screen_size':1},{'percent_triangles':.5,'screen_size':.35},{'percent_triangles':.2,'screen_size':.12}],
          'source_manifest_sha256':sha(manifest_file)}
    plan['plan_id']=fingerprint(plan)
    # Full validation precedes output creation. Inputs remain unchanged.
    out.mkdir(parents=True);(out/'sources').mkdir()
    shutil.copy2(scene_file,out/'baseline.json');shutil.copy2(manifest_file,out/'source-manifest.json')
    for aid,source in inputs.items():shutil.copy2(source,out/'sources'/f'{aid}.glb')
    (out/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    return plan
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',required=True,type=Path);p.add_argument('--scene',required=True);p.add_argument('--manifest',required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    try:
        plan=prepare(a.project,a.scene,a.manifest,a.output);print(json.dumps({'plan_id':plan['plan_id'],'output':str(a.output.resolve()),'assets':len(plan['assets']),'replacements':len(plan['replacements'])}));return 0
    except (ValueError,KeyError,TypeError,OSError) as e:print(json.dumps({'error':str(e)}));return 1
if __name__=='__main__':raise SystemExit(main())
