"""Deterministic modular rooms and sampled cubic paths, in metres/Y-up.

This report describes the specification. Native navmesh queries and collision
movement remain separate evidence; no structural result claims engine reachability.
"""
import math


def generate_scene(spec):
    # Local import keeps the worker's existing parts/terrain API independent.
    from adapters.processing.procedural_worker import number, vector, identifier, box, mesh_record, color_value
    raw_agent = spec.get('agent', {})
    agent = {k: number(raw_agent.get(k, default), k, low, high) for k, default, low, high in (
        ('radius_m', .35, .05, 3), ('height_m', 1.8, .1, 10),
        ('clearance_m', .15, 0, 1), ('headroom_m', .1, 0, 1),
        ('max_slope_degrees', 35, 1, 60), ('max_step_m', .25, 0, 1))}
    if agent['height_m'] < 2 * agent['radius_m']: raise ValueError('Agent height must fit its capsule diameter')
    agent['navigation_radius_m'] = round(agent['radius_m'] + agent['clearance_m'],7)
    agent['navigation_height_m'] = round(agent['height_m'] + agent['headroom_m'],7)
    rooms = spec.get('rooms', [])
    paths = spec.get('paths', [])
    if not isinstance(rooms, list) or not 1 <= len(rooms) <= 64: raise ValueError('rooms must contain 1..64 items')
    if not isinstance(paths, list) or len(paths) > 128: raise ValueError('paths must contain 0..128 items')
    thickness = number(spec.get('wall_thickness', .2), 'wall_thickness', .05, 1)
    floor = number(spec.get('floor_thickness', .25), 'floor_thickness', .05, 1)
    meshes, ports, lookup, reports = [], {}, {}, []
    directions = {'east': (0, 1), 'west': (0, -1), 'north': (2, -1), 'south': (2, 1)}

    def add_box(name, size, position, color):
        if min(size) <= 1e-6: return
        points, faces = box(size)
        meshes.append(mesh_record(name, points, faces, position, color))

    for room in sorted(rooms, key=lambda r: r['id']):
        rid = identifier(room['id'])
        if rid in lookup: raise ValueError('Duplicate room ID: ' + rid)
        pos = vector(room['position'], 'room position')
        size = vector(room['size'], 'room interior size', 1, 100)
        color = color_value(room.get('color', [.28, .38, .48, 1]))
        lookup[rid] = {'position': pos, 'size': size}
        for other_id, other in lookup.items():
            if other_id != rid and all(abs(pos[a] - other['position'][a]) < (size[a] + other['size'][a]) / 2 + 2 * thickness for a in (0, 2)):
                raise ValueError('Room footprints overlap: ' + other_id + ', ' + rid)
        # Stop at the inner wall line, exactly where connector surfaces end.
        # Extending underneath the wall creates a raised lip at sloping entrances.
        add_box(rid + '__floor', [size[0], floor, size[2]], [pos[0], pos[1] - floor/2, pos[2]], color)
        raw_ports = room.get('ports', [])
        if not isinstance(raw_ports, list) or len(raw_ports) > 16: raise ValueError('room ports must contain 0..16 items')
        sides = {side: [] for side in directions}
        for p in raw_ports:
            pid = identifier(p['id'])
            if pid in ports: raise ValueError('Duplicate port ID: ' + pid)
            side = p['side']
            if side not in directions: raise ValueError('port side must be east/west/north/south')
            axis, sign = directions[side]; along = 2 if axis == 0 else 0
            width = number(p['width'], 'port width', .05, size[along] - .1)
            height = number(p['height'], 'port height', .1, size[1])
            offset = number(p.get('offset', 0), 'port offset')
            if abs(offset) + width/2 > size[along]/2 - .05: raise ValueError('Port crosses room corner: ' + pid)
            center = list(pos); center[axis] += sign * size[axis]/2; center[along] += offset
            normal = [0, 0, 0]; normal[axis] = sign
            ports[pid] = {'id': pid, 'room': rid, 'position': center, 'normal': normal, 'width': width, 'height': height}
            sides[side].append((offset - width/2, offset + width/2, height, pid))
        for side, openings in sides.items():
            axis, sign = directions[side]; along = 2 if axis == 0 else 0
            cursor = -size[along]/2 - thickness
            for low, high, height, pid in sorted(openings) + [(size[along]/2 + thickness, size[along]/2 + thickness, size[1], 'end')]:
                if low < cursor - 1e-7: raise ValueError('Overlapping ports in ' + rid + ' ' + side)
                wall_size = [thickness, size[1], thickness]; wall_size[along] = low - cursor
                center = list(pos); center[axis] += sign * (size[axis]/2 + thickness/2); center[along] += (low + cursor)/2; center[1] += size[1]/2
                add_box(rid + '__' + side + '__before_' + pid, wall_size, center, color)
                if pid != 'end' and height < size[1]:
                    wall_size = [thickness, size[1] - height, thickness]; wall_size[along] = high - low
                    center[along] = pos[along] + (low + high)/2; center[1] = pos[1] + (height + size[1])/2
                    add_box(rid + '__lintel_' + pid, wall_size, center, color)
                cursor = high

    used_ports, path_ids, graph = set(), set(), {rid: set() for rid in lookup}
    for path in sorted(paths, key=lambda p: p['id']):
        pid = identifier(path['id'])
        if pid in path_ids: raise ValueError('Duplicate path ID: ' + pid)
        path_ids.add(pid)
        ends = [path['from'], path['to']]
        if ends[0] == ends[1] or any(e not in ports for e in ends): raise ValueError('Path must reference two distinct existing ports: ' + pid)
        if any(e in used_ports for e in ends): raise ValueError('Port already connected: ' + pid)
        used_ports.update(ends)
        start, end = [ports[e] for e in ends]
        if start['room'] == end['room']: raise ValueError('Path must connect different rooms')
        width = number(path.get('width', 2.4), 'path width', .1, 20)
        steps = path.get('segments', 32)
        if type(steps) is not int or not 4 <= steps <= 128: raise ValueError('path segments must be 4..128')
        p0, p3 = start['position'], end['position']
        raw_controls = path.get('controls', [[p0[k] + (p3[k]-p0[k])/3 for k in range(3)], [p0[k] + 2*(p3[k]-p0[k])/3 for k in range(3)]])
        if not isinstance(raw_controls, list) or len(raw_controls) != 2: raise ValueError('controls must contain two points')
        p1, p2 = [vector(v, 'path control') for v in raw_controls]
        # Horizontal tangents must align with the door normal, avoiding side-wall intersections.
        for tangent, normal in (([p1[k]-p0[k] for k in range(3)], start['normal']), ([p2[k]-p3[k] for k in range(3)], end['normal'])):
            length = math.hypot(tangent[0], tangent[2])
            if length < 1e-5 or sum(tangent[k]*normal[k] for k in (0,2))/length < .999:
                raise ValueError('Path endpoint tangent must align with port normal: ' + pid)
        gaps = path.get('gap_segments', [])
        if not isinstance(gaps, list) or any(type(g) is not int or not 0 <= g < steps for g in gaps) or len(set(gaps)) != len(gaps): raise ValueError('gap_segments must contain unique segment indices')
        points, sides = [], []
        for i in range(steps + 1):
            t = i/steps; u = 1-t
            q = [u**3*p0[k]+3*u*u*t*p1[k]+3*u*t*t*p2[k]+t**3*p3[k] for k in range(3)]
            d = [3*u*u*(p1[k]-p0[k])+6*u*t*(p2[k]-p1[k])+3*t*t*(p3[k]-p2[k]) for k in range(3)]
            length = math.hypot(d[0], d[2])
            if length < 1e-5: raise ValueError('Path has a cusp or vertical tangent: ' + pid)
            points.append(q); sides.append([-d[2]/length*width/2, 0, d[0]/length*width/2])
        max_slope, length = 0., 0.
        color = color_value(path.get('color', [.28, .55, .48, 1]))
        for i in range(steps):
            a, b = points[i:i+2]; delta = [b[k]-a[k] for k in range(3)]
            horizontal = math.hypot(delta[0], delta[2])
            if horizontal < 1e-5: raise ValueError('Degenerate path segment: ' + pid)
            # The inner edge must advance with the centre line: reject folded ribbons.
            for sign in (-1, 1):
                edge = [delta[k] + sign*(sides[i+1][k]-sides[i][k]) for k in range(3)]
                if sum(edge[k]*delta[k] for k in (0,2)) <= 1e-7: raise ValueError('Path bends too tightly for its width: ' + pid)
                max_slope = max(max_slope, math.degrees(math.atan2(abs(edge[1]), math.hypot(edge[0],edge[2]))))
            length += math.sqrt(sum(v*v for v in delta))
            # Separate triangles keep each normal honest on a non-planar ramp quad.
            top = [[p[k]+s*side[k] for k in range(3)] for p,side,s in ((a,sides[i],-1),(a,sides[i],1),(b,sides[i+1],1),(b,sides[i+1],-1))]
            vertices = top + [[v[0],v[1]-floor,v[2]] for v in top]
            faces = [[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
            record=mesh_record('path_' + pid + '__' + str(i).zfill(3), vertices, faces, [0,0,0], color)
            for n in (record['normals'][0],record['normals'][3]):
                max_slope=max(max_slope,math.degrees(math.atan2(math.hypot(n[0],n[2]),n[1])))
            if i not in gaps: meshes.append(record)
        reasons = []
        required_width = 2*agent['navigation_radius_m']
        if min(width,start['width'],end['width']) < required_width: reasons.append('narrow_clearance')
        if min(start['height'],end['height']) < agent['navigation_height_m']: reasons.append('low_headroom')
        if max_slope > agent['max_slope_degrees'] + 1e-6: reasons.append('excessive_slope')
        if gaps: reasons.append('broken_surface')
        if not reasons: graph[start['room']].add(end['room']); graph[end['room']].add(start['room'])
        reports.append({'id':pid,'from':ends[0],'to':ends[1],'rooms':[start['room'],end['room']], 'length_m':round(length,4),
                        'max_sampled_slope_degrees':round(max_slope,4),'required_width_m':required_width,
                        'nominal_width_m':min(width,start['width'],end['width']), 'headroom_m':min(start['height'],end['height']),
                        'structural_pass':not reasons,'reasons':reasons,'centerline':points})
    # Generated geometry IDs must remain unique even when user prefixes overlap.
    if len({m['id'] for m in meshes}) != len(meshes): raise ValueError('Generated mesh ID collision')
    components, pending = [], set(graph)
    while pending:
        stack = [min(pending)]; group = set()
        while stack:
            r = stack.pop()
            if r in group: continue
            group.add(r); stack.extend(graph[r]-group)
        pending -= group; components.append(sorted(group))
    queries = []
    raw_queries=spec.get('queries', [])
    if not isinstance(raw_queries,list) or len(raw_queries)>64: raise ValueError('queries must contain 0..64 items')
    for query in raw_queries:
        qid = identifier(query['id'])
        if any(q['id']==qid for q in queries): raise ValueError('Duplicate query ID')
        a, b = query['from_room'], query['to_room']
        if a not in lookup or b not in lookup: raise ValueError('Query references missing room')
        queries.append({'id':qid,'from_room':a,'to_room':b,'start':lookup[a]['position'],'goal':lookup[b]['position'],
                        'expected_reachable':any(a in c and b in c for c in components)})
    navigation = {'agent':agent,'ports':list(ports.values()),'paths':reports,'structural_components':components,
                  'queries':queries,'native_status':'not_run',
                  'limits':['Structural graph only; overlapping paths/third-party obstacles require native bake and movement.',
                            'Sampled cubic ribbons; slopes refer to generated triangles, not an analytic continuous curve.',
                            'Open-top axis-aligned rooms; no automatic multi-floor architecture or off-mesh traversal.']}
    return sorted(meshes,key=lambda m:m['id']), navigation
