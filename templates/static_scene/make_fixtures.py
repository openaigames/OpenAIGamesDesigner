"""Author box/hinged-door calibration geometry; copy user-supplied textures.
No commercial assets are bundled. mr.png is a numeric channel test (G=.4 B=.8).
"""
import json
import math
from pathlib import Path
import shutil
import struct
import zlib


def pixel_png(rgb):
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))+chunk(b'IDAT', zlib.compress(b'\0'+bytes(rgb)))+chunk(b'IEND', b'')


def create(output, color=None, normal=None):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    textures = root/'textures'
    textures.mkdir()
    for name, source, rgb in [('color', color, [180, 120, 60]), ('normal', normal, [128, 128, 255])]:
        suffix = Path(source).suffix if source else '.png'
        if source:
            shutil.copy2(source, textures/(name+suffix))
        else:
            (textures/(name+suffix)).write_bytes(pixel_png(rgb))
    (textures/'mr.png').write_bytes(pixel_png([0, 102, 204]))
    binary = bytearray()
    views, accessors, meshes = [], [], []
    def accessor(data, typ, fmt):
        binary.extend(b'\0'*(-len(binary)%4))
        packed = b''.join(struct.pack('<'+fmt*len(row), *row) for row in data)
        views.append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(packed)})
        binary.extend(packed)
        a = {'bufferView':len(views)-1,'count':len(data),'type':typ,'componentType':5126 if fmt=='f' else 5123}
        if typ == 'VEC3':
            a.update(min=[min(v[i] for v in data) for i in range(3)],max=[max(v[i] for v in data) for i in range(3)])
        accessors.append(a)
        return len(accessors)-1
    def cube(size, center=(0,0,0), material=0):
        vertices, normals, uv, indices = [], [], [], []
        for n, u, v in [((1,0,0),(0,0,-1),(0,1,0)),((-1,0,0),(0,0,1),(0,1,0)),((0,1,0),(1,0,0),(0,0,-1)),((0,-1,0),(1,0,0),(0,0,1)),((0,0,1),(1,0,0),(0,1,0)),((0,0,-1),(-1,0,0),(0,1,0))]:
            start = len(vertices)
            for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]:
                vertices.append(tuple(center[j]+(n[j]+a*u[j]+b*v[j])*size[j]/2 for j in range(3)))
                normals.append(n);uv.append(((a+1)/2,(1-b)/2))
            indices.extend((start+k,) for k in [0,1,2,0,2,3])
        meshes.append({'primitives':[{'attributes':{'POSITION':accessor(vertices,'VEC3','f'),'NORMAL':accessor(normals,'VEC3','f'),'TEXCOORD_0':accessor(uv,'VEC2','f')},'indices':accessor(indices,'SCALAR','H'),'material':material}]})
        return len(meshes)-1
    box = cube((1.2,.8,.6))
    post = cube((.12,2.2,.18), (0,1.1,0))
    top = cube((1.32,.12,.18))
    leaf = cube((1.1,2.05,.08),(.55,1.025,0))
    handle = cube((.15,.06,.12),material=1)
    source = {'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],
              'buffers':[{'uri':'geometry.bin','byteLength':len(binary)}],'bufferViews':views,'accessors':accessors,'meshes':meshes,
              'images':[{'uri':'textures/color'+(Path(color).suffix if color else '.png')},{'uri':'textures/normal'+(Path(normal).suffix if normal else '.png')},{'uri':'textures/mr.png'}],
              'textures':[{'source':0},{'source':1},{'source':2}],
              'materials':[{'name':'Metal','pbrMetallicRoughness':{'baseColorTexture':{'index':0},'metallicRoughnessTexture':{'index':2},'metallicFactor':.75,'roughnessFactor':.5},'normalTexture':{'index':1,'scale':.65}},
                           {'name':'Indicator','doubleSided':True,'pbrMetallicRoughness':{'baseColorFactor':[.04,.1,.2,1],'metallicFactor':0,'roughnessFactor':.8},'emissiveFactor':[.04,.2,.6],'extensions':{'KHR_materials_emissive_strength':{'emissiveStrength':2}}}],
              'extensionsUsed':['KHR_materials_emissive_strength']}
    (root/'geometry.bin').write_bytes(binary)
    source['nodes']=[{'name':'Box','mesh':box,'translation':[0,.5,0],'rotation':[0,math.sin(.2),0,math.cos(.2)]}]
    (root/'box.gltf').write_text(json.dumps(source,indent=2),encoding='utf8')
    source['nodes']=[{'name':'DoorAssembly','translation':[2,0,0],'rotation':[0,math.sin(.15),0,math.cos(.15)],'children':[1,2,3,4]},
                     {'name':'Frame','mesh':post}, {'name':'Frame','mesh':post,'translation':[1.2,0,0]},
                     {'name':'Lintel','mesh':top,'translation':[.6,2.2,0]},
                     {'name':'Hinge','translation':[.06,.05,0],'children':[5]},
                     {'name':'Leaf','mesh':leaf,'children':[6]},
                     {'name':'Handle','mesh':handle,'translation':[.95,1.05,.09]}]
    (root/'door.gltf').write_text(json.dumps(source,indent=2),encoding='utf8')
    return root
