"""Small, explicit geometry vocabulary; coordinates are glTF metres, Y up, CCW.

Parts support boxes, ramps, cylinders, parent translations and mirror instances.
Terrain uses a seeded height field, roads/pads and bounded obstacle scattering.
This is a static greybox generator, not a CAD solid kernel or navigation solver.
"""
import hashlib
from bisect import bisect_right
import json
import math
from pathlib import Path
import random
import re
import struct
import sys

VERSION = '0.2.0'


def number(value, label, low=-10000, high=10000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be finite in [{low}, {high}]')
    return float(value)


def vector(value, label, low=-10000, high=10000):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(label + ' must have three numbers')
    return [number(x, label, low, high) for x in value]


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', value):
        raise ValueError('IDs must be stable ASCII identifiers, up to 64 characters')
    return value


def box(size, ramp=False):
    x, y, z = [v / 2 for v in size]
    points = [[-x,-y,-z],[x,-y,-z],[x,-y,z],[-x,-y,z],
              [-x,y,-z],[x,y,-z],[x,y,z],[-x,y,z]]
    if ramp:
        # Rising towards -Z. A triangular prism, no zero-area faces.
        points = points[:6]
        faces = [[0,3,2,1],[0,1,5,4],[0,4,3],[1,2,5],[3,4,5,2]]
    else:
        faces = [[0,3,2,1],[4,5,6,7],[0,1,5,4],[3,7,6,2],[0,4,7,3],[1,2,6,5]]
    return points, [list(reversed(face)) for face in faces]


def cylinder(size, segments):
    x, y, z = [v / 2 for v in size]
    points = [[x*math.cos(i*math.tau/segments), h, z*math.sin(i*math.tau/segments)]
              for h in (-y,y) for i in range(segments)]
    faces = [list(range(segments)), list(range(2*segments-1,segments-1,-1))]
    for i in range(segments):
        j = (i+1) % segments
        faces.append([i, i+segments, j+segments, j])
    return points, faces


def mesh_record(name, points, faces, position, color, collision=True):
    positions, normals, indices = [], [], []
    for face in faces:
        a, b, c = [points[i] for i in face[:3]]
        ab, ac = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
        n = [ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
        length = math.sqrt(sum(v*v for v in n))
        if length < 1e-10:
            raise ValueError(name + ': degenerate face')
        start = len(positions)
        for index in face:
            positions.append([round(points[index][j]+position[j],7) for j in range(3)])
            normals.append([round(v/length,7) for v in n])
        for i in range(1,len(face)-1):
            indices.extend([start,start+i,start+i+1])
    return {'id':name, 'positions':positions, 'normals':normals, 'indices':indices,
            'color':color, 'collision':collision,
            'bounds':[[min(p[i] for p in positions) for i in range(3)],
                      [max(p[i] for p in positions) for i in range(3)]]}


def color_value(raw):
    if not isinstance(raw,list) or len(raw) != 4:
        raise ValueError('color must be RGBA')
    return [number(v,'color',0,1) for v in raw]


def parts(spec):
    raw = spec.get('parts',[])
    if not isinstance(raw,list) or not 1 <= len(raw) <= 512:
        raise ValueError('parts must contain 1..512 parts')
    lookup = {}
    for part in raw:
        name = identifier(part['id'])
        if name in lookup: raise ValueError('Duplicate part ID: '+name)
        lookup[name] = part
    positions, visiting = {}, set()
    def resolve(name):
        if name in positions: return positions[name]
        if name in visiting: raise ValueError('Parent cycle at '+name)
        if name not in lookup: raise ValueError('Missing parent: '+name)
        visiting.add(name)
        part = lookup[name]
        pos = vector(part.get('position',[0,0,0]),'position')
        if part.get('parent'):
            parent = resolve(part['parent'])
            pos = [a+b for a,b in zip(parent,pos)]
            face=part.get('attach')
            if face:
                if face not in ('+x','-x','+y','-y','+z','-z'):
                    raise ValueError('attach must be +x/-x/+y/-y/+z/-z')
                axis='xyz'.index(face[1]);sign=1 if face[0]=='+' else -1
                parent_size=vector(lookup[part['parent']]['size'],'parent size',.001,1000)
                child_size=vector(part['size'],'child size',.001,1000)
                pos[axis]+=sign*(parent_size[axis]+child_size[axis])/2
        elif part.get('attach'):
            raise ValueError('attach requires a parent')
        visiting.remove(name)
        positions[name] = pos
        return pos
    result = []
    minimum = number(spec.get('minimum_thickness',0.01),'minimum_thickness',0.001,100)
    for name, part in lookup.items():
        size = vector(part['size'],'size',minimum,1000)
        shape = part.get('shape','box')
        if shape in ('box','ramp'): points, faces = box(size,shape=='ramp')
        elif shape == 'cylinder':
            segments = part.get('segments',16)
            if type(segments) != int or not 3 <= segments <= 128: raise ValueError('segments must be 3..128')
            points,faces = cylinder(size,segments)
        else: raise ValueError('Unsupported primitive: '+str(shape))
        pos = resolve(name)
        color = color_value(part.get('color',[0.45,0.55,0.65,1]))
        if type(part.get('collision',True)) is not bool: raise ValueError('collision must be boolean')
        result.append(mesh_record(name,points,faces,pos,color,part.get('collision',True)))
        mirror = part.get('mirror')
        if mirror:
            if mirror not in ('x','y','z'): raise ValueError('mirror must be x, y or z')
            axis = 'xyz'.index(mirror)
            reflected = [[(-v if i==axis else v) for i,v in enumerate(p)] for p in points]
            mirrored_pos = [(-v if i==axis else v) for i,v in enumerate(pos)]
            # A reflection changes handedness: reverse every face to preserve outward normals.
            result.append(mesh_record(name+'_mirror',reflected,[list(reversed(f)) for f in faces],mirrored_pos,color,part.get('collision',True)))
    if len({p['id'] for p in result}) != len(result): raise ValueError('Mirrored ID collides with a part ID')
    return result


def terrain(spec):
    width = number(spec.get('width',24),'width',2,1000)
    depth = number(spec.get('depth',24),'depth',2,1000)
    cells = spec.get('cells',32)
    if type(cells) != int or not 2 <= cells <= 128: raise ValueError('cells must be 2..128')
    amplitude = number(spec.get('amplitude',2),'amplitude',0,100)
    seed = spec.get('seed',0)
    if type(seed) != int: raise ValueError('seed must be an integer')
    rng = random.Random(seed)
    phase = rng.random()*math.tau
    mode = spec.get('profile','hills')
    if mode not in ('flat','hills','basin','canyon'): raise ValueError('Unknown terrain profile')
    zones=[]
    for item in spec.get('clearances',[]):
        center=vector(item['center'],'clearance center')
        size=vector(item['size'],'clearance size',0.01,2000)
        zones.append((center,size))
    road=spec.get('road')
    if road:
        road_width=number(road.get('width',3),'road width',0.1,width)
        road_height=number(road.get('height',0),'road height')
        zones.append(([0,road_height,0],[road_width,1,depth]))
    def height(x,z):
        r=(x/(width/2))**2+(z/(depth/2))**2
        h={'flat':0,'hills':amplitude*(math.sin(x*.25+phase)*math.cos(z*.2+phase)+1)/2,
           'basin':amplitude*min(1,r), 'canyon':amplitude*(1-math.exp(-(x/(width*.15))**2))}[mode]
        for center,size in zones:
            # One grid-cell shoulder transitions to flat road/pad without vertical cliffs.
            d=max(abs(x-center[0])-size[0]/2,abs(z-center[2])-size[2]/2)
            blend=max(0,min(1,d/max(width/cells,depth/cells)))
            h=center[1]*(1-blend)+h*blend
        # A different zone's shoulder must not deform a flat interior. In actual
        # overlapping interiors the last specification (road last) takes priority.
        for center,size in zones:
            if abs(x-center[0])<=size[0]/2+1e-7 and abs(z-center[2])<=size[2]/2+1e-7:
                h=center[1]
        return h
    # Include pad/road boundaries: a coarse regular grid can otherwise miss them.
    # Rounded vertices match the serialized mesh used by both native engines.
    def axis_grid(axis, extent):
        coordinates={round(-extent/2+i*extent/cells,7) for i in range(cells+1)}
        for center,size in zones:
            for edge in (center[axis]-size[axis]/2,center[axis]+size[axis]/2):
                if -extent/2 < edge < extent/2: coordinates.add(round(edge,7))
        return sorted(coordinates)
    xs,zs=axis_grid(0,width),axis_grid(2,depth)
    nx,nz=len(xs),len(zs)
    if 2*(nx-1)*(nz-1)>200000: raise ValueError('Terrain grid exceeds maximum triangle budget')
    points=[[x,round(height(x,z),7),z] for z in zs for x in xs]
    faces=[]
    for j in range(nz-1):
        for i in range(nx-1):
            a=j*nx+i; b=a+nx
            faces.extend([[a,b,a+1],[a+1,b,b+1]])
    meshes=[mesh_record('terrain',points,faces,[0,0,0],[.22,.38,.30,1])]
    def surface(x,z):
        i=min(nx-2,max(0,bisect_right(xs,x)-1));j=min(nz-2,max(0,bisect_right(zs,z)-1))
        dx,dz=xs[i+1]-xs[i],zs[j+1]-zs[j]
        u,v=(x-xs[i])/dx,(z-zs[j])/dz
        h00,h10,h01,h11=[points[k][1] for k in (j*nx+i,j*nx+i+1,(j+1)*nx+i,(j+1)*nx+i+1)]
        if u+v<=1:
            h=h00+(h10-h00)*u+(h01-h00)*v
            gx,gz=(h10-h00)/dx,(h01-h00)/dz
        else:
            h=h11+(h01-h11)*(1-u)+(h10-h11)*(1-v)
            gx,gz=(h11-h01)/dx,(h11-h10)/dz
        return h,math.hypot(gx,gz)
    scatter=spec.get('scatter',{})
    count=scatter.get('count',0)
    if type(count)!=int or not 0<=count<=256: raise ValueError('scatter count must be 0..256')
    size=vector(scatter.get('size',[1,1,1]),'scatter size',.01,100)
    gap=number(scatter.get('gap',.5),'scatter gap',0,100)
    max_slope=number(scatter.get('max_slope',.5),'max_slope',0,10)
    placed=[]
    for attempt in range(max(1,count)*200):
        if len(placed)==count: break
        x,z=rng.uniform(-width/2,width/2),rng.uniform(-depth/2,depth/2)
        if abs(x)+size[0]/2>width/2 or abs(z)+size[2]/2>depth/2: continue
        if any(abs(x-c[0])<(s[0]+size[0])/2+gap and abs(z-c[2])<(s[2]+size[2])/2+gap for c,s in zones): continue
        if any(abs(x-p[0])<size[0]+gap and abs(z-p[2])<size[2]+gap for p in placed): continue
        h,slope=surface(x,z)
        if slope>max_slope: continue
        p=[x,h+size[1]/2,z]; placed.append(p)
        vertices,polygons=box(size)
        meshes.append(mesh_record('scatter_'+str(len(placed)),vertices,polygons,p,[.6,.48,.3,1]))
    if len(placed)!=count: raise ValueError(f'Clearance/slope rules allow only {len(placed)} of {count} requested objects')
    return meshes


def generate(spec):
    if spec.get('schema_version') != 1: raise ValueError('schema_version must be 1')
    kind=spec.get('kind')
    navigation=None
    if kind=='parts': meshes=parts(spec)
    elif kind=='terrain': meshes=terrain(spec)
    elif kind=='scene':
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from adapters.processing.procedural_scene import generate_scene
        meshes,navigation=generate_scene(spec)
    else: raise ValueError('kind must be parts, terrain or scene')
    budget=spec.get('triangle_budget',100000)
    if type(budget)!=int or not 1<=budget<=200000: raise ValueError('triangle_budget must be 1..200000')
    triangles=sum(len(m['indices'])//3 for m in meshes)
    if triangles>budget: raise ValueError(f'Triangle budget exceeded: {triangles}>{budget}')
    digest=hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    result={'schema_version':1,'generator_version':VERSION,'coordinates':'RH_Y_UP_METRES_CCW',
            'spec_sha256':digest,'meshes':meshes,
            'validation':{'triangles':triangles,'objects':len(meshes),'minimum_thickness':spec.get('minimum_thickness',.01),
                          'checks':['finite_coordinates','nondegenerate_faces','triangle_budget','unique_ids'],
                          'limits':['Static geometry; no rigging or boolean CSG.','Clearances are XZ rectangles, not navmesh reachability.']}}
    if navigation:
        result['navigation']=navigation
        result['validation']['navigation']=navigation
        result['validation']['limits']=navigation['limits']
    return result


def glb(scene):
    data=bytearray(); views=[]; accessors=[]; meshes=[]; nodes=[]; materials=[]
    def accessor(values,fmt,kind,component,minimum=None,maximum=None):
        while len(data)%4: data.append(0)
        offset=len(data)
        flat=[v for item in values for v in item] if kind=='VEC3' else values
        data.extend(struct.pack('<'+fmt*len(flat),*flat))
        views.append({'buffer':0,'byteOffset':offset,'byteLength':len(data)-offset})
        record={'bufferView':len(views)-1,'componentType':component,'count':len(values),'type':kind}
        if minimum is not None: record.update(min=minimum,max=maximum)
        accessors.append(record)
        return len(accessors)-1
    for m in scene['meshes']:
        p=accessor(m['positions'],'f','VEC3',5126,*m['bounds'])
        n=accessor(m['normals'],'f','VEC3',5126)
        idx=accessor(m['indices'],'I','SCALAR',5125)
        materials.append({'pbrMetallicRoughness':{'baseColorFactor':m['color'],'metallicFactor':0,'roughnessFactor':.8}})
        meshes.append({'name':m['id'],'primitives':[{'attributes':{'POSITION':p,'NORMAL':n},'indices':idx,'material':len(materials)-1}]})
        nodes.append({'name':m['id'],'mesh':len(meshes)-1,'extras':{'collision':m['collision']}})
    doc={'asset':{'version':'2.0','generator':'OAGD procedural '+VERSION},'scene':0,
         'scenes':[{'nodes':list(range(len(nodes)))}],'nodes':nodes,'meshes':meshes,'materials':materials,
         'buffers':[{'byteLength':len(data)}],'bufferViews':views,'accessors':accessors}
    js=json.dumps(doc,separators=(',',':')).encode(); js+=b' '*((-len(js))%4)
    data+=b'\0'*((-len(data))%4)
    return struct.pack('<4sII',b'glTF',2,28+len(js)+len(data))+struct.pack('<I4s',len(js),b'JSON')+js+struct.pack('<I4s',len(data),b'BIN\0')+data


def write(spec, output):
    scene=generate(spec)  # validate before creating any deliverable
    output=Path(output)
    if output.exists() and any(output.iterdir()): raise ValueError('Output directory must be empty; create a new version')
    output.mkdir(parents=True,exist_ok=True)
    (output/'scene.glb').write_bytes(glb(scene))
    (output/'scene.json').write_text(json.dumps(scene,separators=(',',':')),encoding='utf-8')
    (output/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
    (output/'validation.json').write_text(json.dumps(scene['validation'],indent=2),encoding='utf-8')
    return scene


if __name__=='__main__':
    request,output,result=map(Path,sys.argv[1:])
    try:
        req=json.loads(request.read_text(encoding='utf-8-sig'))
        spec=req['parameters']['spec']
        write(spec,output)
        result.write_text(json.dumps({'artifacts':[{'path':name} for name in ('scene.glb','scene.json','spec.json','validation.json')]}),encoding='utf-8')
    except (ValueError,KeyError,TypeError,OSError) as error:
        print(str(error),file=sys.stderr); sys.exit(1)
