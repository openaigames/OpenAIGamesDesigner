"""Freeze static glTF scenes for opt-in native Godot / UE 5.8 import.

Does not replace scene objects or infer collisions. Sources are never modified.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import urllib.parse

VERSION = '0.1.0'
SCHEMA = 'oagd.static-scene/1'
EXTENSIONS = {'KHR_materials_emissive_strength'}
IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vec(value, length):
    if not isinstance(value, list) or len(value) != length or any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError('Expected finite numeric vector')
    return value


def index(value, values):
    if type(value) is not int or not 0 <= value < len(values):
        raise ValueError('Out-of-range resource index')
    return value


def multiply(a, b):
    return [sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4)) for col in range(4) for row in range(4)]


def transform(node):
    if 'matrix' in node:
        if any(k in node for k in ('translation', 'rotation', 'scale')):
            raise ValueError('Matrix and TRS cannot coexist')
        m = vec(node['matrix'], 16)
        if any(abs(m[i] - v) > 1e-6 for i, v in ((3, 0), (7, 0), (11, 0), (15, 1))):
            raise ValueError('Non-affine transform')
    else:
        x, y, z, w = vec(node.get('rotation', [0, 0, 0, 1]), 4)
        if abs(x*x+y*y+z*z+w*w-1) > 1e-4:
            raise ValueError('Quaternion must be normalized')
        s = vec(node.get('scale', [1, 1, 1]), 3)
        t = vec(node.get('translation', [0, 0, 0]), 3)
        m = [1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w), 0,
             2*(x*y-z*w), 1-2*(x*x+z*z), 2*(y*z+x*w), 0,
             2*(x*z+y*w), 2*(y*z-x*w), 1-2*(x*x+y*y), 0, *t, 1]
        for col in range(3):
            for row in range(3):
                m[col*4+row] *= s[col]
    # Positive, uniform scale is deliberate: UE FTransform cannot preserve shear.
    cols = [[m[c*4+r] for r in range(3)] for c in range(3)]
    scales = [math.sqrt(sum(x*x for x in col)) for col in cols]
    determinant = sum(cols[0][r] * (cols[1][(r+1)%3]*cols[2][(r+2)%3]-cols[1][(r+2)%3]*cols[2][(r+1)%3]) for r in range(3))
    if min(scales) < 1e-5 or max(scales)-min(scales) > 1e-5*max(scales) or determinant <= 0:
        raise ValueError('Use positive uniform node scale; bake nonuniform/mirrored scale explicitly')
    if any(abs(sum(cols[a][r]*cols[b][r] for r in range(3))) > 1e-5*scales[a]*scales[b] for a, b in ((0, 1), (0, 2), (1, 2))):
        raise ValueError('Sheared transform is unsupported')
    return list(m)


def read_source(source):
    path = Path(source).resolve()
    raw = path.read_bytes()
    binary = None
    if path.suffix.lower() == '.glb':
        if len(raw) < 20 or struct.unpack_from('<4sII', raw) != (b'glTF', 2, len(raw)):
            raise ValueError('Incomplete GLB 2 header')
        chunks = []
        off = 12
        while off < len(raw):
            if off+8 > len(raw):
                raise ValueError('Truncated GLB chunk')
            size, kind = struct.unpack_from('<I4s', raw, off)
            if size % 4 or off+8+size > len(raw):
                raise ValueError('Invalid GLB chunk length')
            chunks.append((kind, raw[off+8:off+8+size]))
            off += 8+size
        if not chunks or chunks[0][0] != b'JSON' or len(chunks) > 2 or len(chunks) == 2 and chunks[1][0] != b'BIN\0':
            raise ValueError('Expected JSON and optional BIN chunks')
        doc = json.loads(chunks[0][1])
        binary = chunks[1][1] if len(chunks) == 2 else None
    elif path.suffix.lower() == '.gltf':
        doc = json.loads(raw.decode('utf-8-sig'))
    else:
        raise ValueError('Use .glb or .gltf')
    dependencies = {path.name: hashlib.sha256(raw).hexdigest()}

    def external(uri):
        if not isinstance(uri, str):
            raise ValueError('Dependency URI must be local')
        parsed = urllib.parse.urlsplit(uri)
        name = urllib.parse.unquote(uri)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or '\\' in name or ':' in name:
            raise ValueError('Remote, data or ambiguous URI unsupported')
        p = (path.parent/name).resolve()
        if not p.is_relative_to(path.parent) or p == path or not p.is_file():
            raise ValueError('Dependency missing or escapes asset directory: '+name)
        data = p.read_bytes()
        dependencies[p.relative_to(path.parent).as_posix()] = hashlib.sha256(data).hexdigest()
        return data

    buffers = []
    for i, b in enumerate(doc.get('buffers', [])):
        data = external(b['uri']) if 'uri' in b else binary if i == 0 else None
        n = b.get('byteLength')
        if type(n) is not int or n <= 0 or data is None or not 0 <= len(data)-n <= (3 if 'uri' not in b else 0):
            raise ValueError('Missing or inconsistent buffer')
        buffers.append(data[:n])
    views = []
    for v in doc.get('bufferViews', []):
        buf = buffers[index(v.get('buffer'), buffers)]
        start, size = v.get('byteOffset', 0), v.get('byteLength')
        if type(start) is not int or type(size) is not int or start < 0 or size <= 0 or start+size > len(buf):
            raise ValueError('Buffer view exceeds buffer')
        views.append(buf[start:start+size])
    images = []
    for im in doc.get('images', []):
        if ('uri' in im) == ('bufferView' in im):
            raise ValueError('Image needs exactly one source')
        data = external(im['uri']) if 'uri' in im else views[index(im['bufferView'], views)]
        mime = 'image/png' if data.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if data.startswith(b'\xff\xd8\xff') else None
        if mime is None or im.get('mimeType', mime) != mime:
            raise ValueError('Only PNG/JPEG images supported; MIME must match')
        images.append((mime, data))
    return doc, views, images, dependencies


def inspect(source, selected=None):
    d, views, images, deps = read_source(source)
    if d.get('asset', {}).get('version') != '2.0' or d.get('skins') or d.get('animations') or d.get('cameras'):
        raise ValueError('Static glTF 2 scene required; skins, animation and cameras are unsupported')
    if set(d.get('extensionsUsed', [])) - EXTENSIONS or set(d.get('extensionsRequired', [])) - EXTENSIONS:
        raise ValueError('Unsupported glTF extension')
    def extensions(value, context='root'):
        if isinstance(value, dict):
            if 'extensions' in value and (context != 'material' or set(value['extensions'])-EXTENSIONS):
                raise ValueError('Unsupported extension location or semantics')
            for k, v in value.items():
                if k not in ('extras', 'extensions'):
                    extensions(v, 'materials' if k == 'materials' else 'other')
        elif isinstance(value, list):
            for v in value:
                extensions(v, 'material' if context == 'materials' else 'other')
    extensions(d)
    nodes = d.get('nodes', [])
    meshes = d.get('meshes', [])
    accessors = d.get('accessors', [])
    materials = d.get('materials', [])
    if not 1 <= len(nodes) <= 1024 or not meshes:
        raise ValueError('Expected 1..1024 nodes and static meshes')
    parents = {}
    matrices = []
    for i, n in enumerate(nodes):
        if set(n) - {'name', 'extras', 'children', 'mesh', 'matrix', 'translation', 'rotation', 'scale'}:
            raise ValueError('Unsupported node semantics')
        matrices.append(transform(n))
        if 'mesh' in n:
            index(n['mesh'], meshes)
        for child in n.get('children', []):
            index(child, nodes)
            if child in parents or child == i:
                raise ValueError('Duplicate parent or cycle')
            parents[child] = i
    scene = d.get('scene', 0)
    roots = d.get('scenes', [])[index(scene, d.get('scenes', []))].get('nodes', [])
    order, active = [], set()
    def visit(i):
        index(i, nodes)
        if i in active or i in order:
            raise ValueError('Cycle or repeated scene node')
        active.add(i)
        order.append(i)
        for c in nodes[i].get('children', []):
            visit(c)
        active.remove(i)
    for i in roots:
        if i in parents:
            raise ValueError('Scene root also has a parent')
        visit(i)
    # Reject malformed disconnected graphs too; selection cannot conceal bad input.
    for i in range(len(nodes)):
        seen = set()
        p = i
        while p in parents:
            if p in seen:
                raise ValueError('Disconnected cycle')
            seen.add(p)
            p = parents[p]
    keep = set(order)
    if selected is not None:
        if not selected or len(set(selected)) != len(selected) or any(type(i) is not int or i not in keep for i in selected):
            raise ValueError('Selection must use distinct indices from the active scene')
        keep = set()
        def descend(i):
            keep.add(i)
            for c in nodes[i].get('children', []):
                descend(c)
        for i in selected:
            descend(i)
            while i in parents:
                i = parents[i]
                keep.add(i)
    order = [i for i in order if i in keep]
    used_meshes = sorted({nodes[i]['mesh'] for i in order if 'mesh' in nodes[i]})
    if not used_meshes:
        raise ValueError('Selected scene contains no meshes')
    decoded = {}
    def values(aid, typ, components):
        a = accessors[index(aid, accessors)]
        if a.get('sparse') or a.get('normalized', False) or a.get('type') != typ or a.get('componentType') not in components:
            raise ValueError('Unsupported accessor encoding')
        vi = index(a.get('bufferView'), views)
        count, offset = a.get('count'), a.get('byteOffset', 0)
        fmt, width = {5126: ('f', 4), 5125: ('I', 4), 5123: ('H', 2), 5121: ('B', 1)}[a['componentType']]
        lanes = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[typ]
        stride = d['bufferViews'][vi].get('byteStride', width*lanes)
        if type(count) is not int or not 1 <= count <= 6000000 or type(offset) is not int or offset < 0 or type(stride) is not int or stride < lanes*width or stride % width or offset % width or offset+(count-1)*stride+lanes*width > len(views[vi]):
            raise ValueError('Accessor exceeds view or has invalid alignment/count')
        if aid not in decoded:
            decoded[aid] = [struct.unpack_from('<'+fmt*lanes, views[vi], offset+i*stride) for i in range(count)]
        out = decoded[aid]
        if any(not math.isfinite(v) for row in out for v in row):
            raise ValueError('Non-finite vertex data')
        return out
    mesh_info = {}
    used_materials = set()
    for mi in used_meshes:
        mesh = meshes[mi]
        if set(mesh)-{'name', 'primitives', 'extras'} or not mesh.get('primitives'):
            raise ValueError('Unsupported mesh semantics')
        lo, hi, triangles = [math.inf]*3, [-math.inf]*3, 0
        for p in mesh['primitives']:
            if set(p)-{'attributes', 'indices', 'material', 'mode', 'extras'} or p.get('mode', 4) != 4:
                raise ValueError('Indexed static triangles required')
            attrs = p['attributes']
            if set(attrs)-{'POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT'} or 'NORMAL' not in attrs:
                raise ValueError('Use POSITION/NORMAL and optional TEXCOORD_0/TANGENT')
            pos = values(attrs['POSITION'], 'VEC3', {5126})
            for name, typ in (('NORMAL', 'VEC3'), ('TEXCOORD_0', 'VEC2'), ('TANGENT', 'VEC4')):
                if name in attrs and len(values(attrs[name], typ, {5126})) != len(pos):
                    raise ValueError('Vertex attribute counts differ')
            inds = values(p.get('indices'), 'SCALAR', {5121, 5123, 5125})
            if len(inds) % 3 or any(v[0] >= len(pos) for v in inds):
                raise ValueError('Invalid triangle indices')
            triangles += len(inds)//3
            for j in range(3):
                lo[j] = min(lo[j], min(v[j] for v in pos))
                hi[j] = max(hi[j], max(v[j] for v in pos))
            mid = index(p.get('material'), materials)
            used_materials.add(mid)
            m = materials[mid]
            if any(k.endswith('Texture') for k in m) or any(k.endswith('Texture') for k in m.get('pbrMetallicRoughness', {})):
                if 'TEXCOORD_0' not in attrs:
                    raise ValueError('Textured primitive has no UV0')
        if triangles > 2000000:
            raise ValueError('Mesh triangle budget exceeded')
        mesh_info[mi] = {'id': mi, 'triangles': triangles, 'bounds': [lo, hi]}
    for mid in used_materials:
        m = materials[mid]
        if set(m)-{'name', 'pbrMetallicRoughness', 'normalTexture', 'emissiveTexture', 'emissiveFactor', 'doubleSided', 'alphaMode', 'extensions', 'extras'} or m.get('alphaMode', 'OPAQUE') != 'OPAQUE':
            raise ValueError('Only opaque standard PBR, normal and emissive materials supported; AO/transparency require explicit conversion')
        pbr = m.get('pbrMetallicRoughness', {})
        if set(pbr)-{'baseColorFactor', 'metallicFactor', 'roughnessFactor', 'baseColorTexture', 'metallicRoughnessTexture'}:
            raise ValueError('Unsupported PBR property')
        rgba = vec(pbr.get('baseColorFactor', [1]*4), 4)
        factors = [*rgba, pbr.get('metallicFactor', 1), pbr.get('roughnessFactor', 1)]
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in factors) or rgba[3] != 1:
            raise ValueError('Invalid PBR factors')
        if any(v < 0 for v in vec(m.get('emissiveFactor', [0]*3), 3)):
            raise ValueError('Invalid emission')
        strength = m.get('extensions', {}).get('KHR_materials_emissive_strength', {}).get('emissiveStrength', 1)
        if type(strength) not in (int, float) or not math.isfinite(strength) or strength < 0:
            raise ValueError('Invalid emissive strength')
        for name, item in list(pbr.items()) + list(m.items()):
            if not name.endswith('Texture'):
                continue
            if set(item)-{'index', 'texCoord', 'scale'} or item.get('texCoord', 0) != 0:
                raise ValueError('Only UV0 without texture transforms supported')
            if 'scale' in item and (name != 'normalTexture' or type(item['scale']) not in (int, float) or not math.isfinite(item['scale']) or item['scale'] < 0):
                raise ValueError('Invalid texture scale')
            tex = d.get('textures', [])[index(item.get('index'), d.get('textures', []))]
            if set(tex)-{'source', 'sampler', 'name', 'extras'}:
                raise ValueError('Unsupported texture encoding')
            index(tex.get('source'), images)
            if 'sampler' in tex:
                sam = d.get('samplers', [])[index(tex['sampler'], d.get('samplers', []))]
                if sam.get('wrapS', 10497) != 10497 or sam.get('wrapT', 10497) != 10497 or sam.get('magFilter', 9729) != 9729 or sam.get('minFilter', 9987) not in (9729, 9987):
                    raise ValueError('This release uses repeat/linear texture sampling')
    world = {}
    records = []
    for i in order:
        world[i] = multiply(world[parents[i]], matrices[i]) if i in parents else matrices[i]
        records.append({'id': i, 'name': nodes[i].get('name', ''), 'parent': parents.get(i), 'mesh': nodes[i].get('mesh'), 'local_matrix': matrices[i], 'world_matrix': world[i]})
    return d, views, images, {'nodes': records, 'roots': [i for i in roots if i in keep], 'meshes': list(mesh_info.values()), 'dependencies': deps}


def compact(d, views, images, nodes, roots):
    """Copy only reachable native glTF resources; geometry/UV/image bytes unchanged."""
    out = {'asset': {'version': '2.0', 'generator': 'OAGD static_scene '+VERSION}, 'scene': 0, 'scenes': [{'nodes': roots}], 'nodes': copy.deepcopy(nodes)}
    binary = bytearray()
    maps = {k: {} for k in ('meshes', 'materials', 'textures', 'images', 'samplers', 'accessors', 'bufferViews')}
    def view(data, extra=None):
        binary.extend(b'\0' * (-len(binary) % 4))
        item = {**(extra or {}), 'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(data)}
        out.setdefault('bufferViews', []).append(item)
        binary.extend(data)
        return len(out['bufferViews'])-1
    def take(kind, old):
        if old in maps[kind]:
            return maps[kind][old]
        item = copy.deepcopy(d[kind][old])
        if kind == 'bufferViews':
            new = view(views[old], {k: v for k, v in item.items() if k in ('byteStride', 'target')})
            maps[kind][old] = new
            return new
        if kind == 'images':
            mime, data = images[old]
            item = {'name': 'Image_'+str(old), 'bufferView': view(data), 'mimeType': mime}
        elif kind == 'accessors':
            item['bufferView'] = take('bufferViews', item['bufferView'])
        elif kind == 'textures':
            item['source'] = take('images', item['source'])
            if 'sampler' in item:
                item['sampler'] = take('samplers', item['sampler'])
        elif kind == 'materials':
            item['name'] = 'Material_'+str(old)
            for key, value in list(item.items()) + list(item.get('pbrMetallicRoughness', {}).items()):
                if key.endswith('Texture'):
                    value['index'] = take('textures', value['index'])
            if item.get('extensions'):
                out['extensionsUsed'] = sorted(set(out.get('extensionsUsed', [])) | set(item['extensions']))
        elif kind == 'meshes':
            item['name'] = 'Mesh_'+str(old)
            for p in item['primitives']:
                p['attributes'] = {k: take('accessors', v) for k, v in p['attributes'].items()}
                p['indices'] = take('accessors', p['indices'])
                p['material'] = take('materials', p['material'])
        out.setdefault(kind, []).append(item)
        new = len(out[kind])-1
        maps[kind][old] = new
        return new
    for n in out['nodes']:
        if 'mesh' in n:
            n['mesh'] = take('meshes', n['mesh'])
    out['buffers'] = [{'byteLength': len(binary)}]
    js = json.dumps(out, separators=(',', ':'), allow_nan=False).encode()
    js += b' ' * (-len(js) % 4)
    binary.extend(b'\0' * (-len(binary) % 4))
    return struct.pack('<4sII', b'glTF', 2, 28+len(js)+len(binary)) + struct.pack('<I4s', len(js), b'JSON') + js + struct.pack('<I4s', len(binary), b'BIN\0') + binary


def prepare(source, output, selected=None):
    out = Path(output).resolve()
    if out.exists():
        raise ValueError('Use a new revision directory')
    d, views, images, info = inspect(source, selected)
    ids = {n['id']: i for i, n in enumerate(info['nodes'])}
    nodes = []
    for row in info['nodes']:
        old = d['nodes'][row['id']]
        n = {'name': 'Node_'+str(row['id']), 'matrix': row['local_matrix'], 'extras': {'source_index': row['id'], 'source_name': row['name'], 'source_extras': old.get('extras', {})}}
        if row['mesh'] is not None:
            n['mesh'] = row['mesh']
        children = [ids[c] for c in old.get('children', []) if c in ids]
        if children:
            n['children'] = children
        nodes.append(n)
    files = {'scene.glb': compact(d, views, images, nodes, [ids[i] for i in info['roots']])}
    for mesh in info['meshes']:
        mesh['file'] = 'meshes/mesh_'+str(mesh['id'])+'.glb'
        files[mesh['file']] = compact(d, views, images, [{'name': 'Mesh_'+str(mesh['id']), 'mesh': mesh['id']}], [0])
    # Re-read dependency hashes before publishing a frozen snapshot.
    for name, expected in info['dependencies'].items():
        if sha(Path(source).resolve().parent/name) != expected:
            raise ValueError('Source/dependency changed while preparing')
    plan = {'schema': SCHEMA, 'version': VERSION, 'source': str(Path(source).resolve()), 'selection': selected,
            'coordinates': 'RH_Y_UP_METRES; UE mesh basis (X,Z,Y)*100, wrapper yaw +90 => (-Z,X,Y)*100',
            'collision': 'none; configure collision when integrating the scene', **info,
            'files': {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
    plan['plan_id'] = fingerprint(plan)
    out.mkdir(parents=True)
    for name, data in files.items():
        p = out/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (out/'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return plan


def read_plan(folder):
    root = Path(folder).resolve()
    p = json.loads((root/'plan.json').read_text(encoding='utf-8'))
    if p.get('schema') != SCHEMA or fingerprint({k: v for k, v in p.items() if k != 'plan_id'}) != p.get('plan_id'):
        raise ValueError('Frozen scene plan changed')
    for name, expected in p['files'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or path == root or sha(path) != expected:
            raise ValueError('Frozen dependency changed or escaped revision')
    return p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--source', required=True, type=Path)
    prep.add_argument('--output', required=True, type=Path)
    prep.add_argument('--nodes', nargs='+', type=int)
    check = sub.add_parser('check')
    check.add_argument('revision', type=Path)
    args = parser.parse_args()
    try:
        p = prepare(args.source, args.output, args.nodes) if args.command == 'prepare' else read_plan(args.revision)
        print(json.dumps({'ok': True, 'plan_id': p['plan_id'], 'nodes': len(p['nodes']), 'meshes': len(p['meshes'])}))
        return 0
    except (ValueError, KeyError, IndexError, TypeError, OSError, struct.error) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
