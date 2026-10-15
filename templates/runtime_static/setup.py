"""Original, bounded replacement fixture. Not an automatic arbitrary-scene mapper."""
import hashlib,json,shutil
from pathlib import Path
def setup(root,content,engine,toolkit):
    from tools.static_assets import prepare
    inputs=content/'generated/static-input';inputs.mkdir(parents=True)
    shutil.copy2(toolkit/'templates/runtime_static/assets/portal.glb',inputs/'portal.glb')
    scene=content/'generated/scene/scene.json'
    rows=[]
    for room,side,pos,yaw,mode in [('curve_a','east',[-5,0,0],0,'source_mesh'),('ramp_b','west',[5,3,14],180,'source_mesh'),('curve_b','west',[5,0,-5],180,'retain_graybox')]:
        rows.append({'id':room+'_portal','targets':[room+'__'+side+'__before_'+room+'_door',room+'__'+side+'__before_end',room+'__lintel_'+room+'_door'],'asset':'portal','position':pos,'yaw_degrees':yaw,'scale':1,'collision':mode})
    manifest={'schema':'oagd.static-assets/1','scene_sha256':hashlib.sha256(scene.read_bytes()).hexdigest(),'assets':[{'id':'portal','source':'generated/static-input/portal.glb','sha256':hashlib.sha256((inputs/'portal.glb').read_bytes()).hexdigest()}],'replacements':rows}
    (inputs/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    prepare(content,'generated/scene/scene.json','generated/static-input/manifest.json',content/'generated/static')
    if engine=='unreal':
        for name in ('static_replacement.py','static_meshes.py','mesh_contract.py'):
            shutil.copy2(toolkit/'adapters/engines/unreal'/name,root/name)
