"""Use the existing planar checker with measured furnishing bounds and door sweeps."""
import copy
import importlib.util
import math
from pathlib import Path
from .common import issue, issues_report, number, unique


def spatial_module():
    root = Path(__file__).resolve().parents[2]
    for skills in (root/'skills', root.parent.parent):
        path = skills/'game-level-design/scripts/spatial_drawings.py'
        if path.is_file():
            spec = importlib.util.spec_from_file_location('environment_spatial', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ValueError('The installed game-level-design spatial checker is required')


def polygon_distance(a, b, s):
    if s.inside(a[0], b) or s.inside(b[0], a):
        return 0
    return min(s.segment_distance(x, y, v, w) for x, y in s.edges(a) for v, w in s.edges(b))


def measured_input(spec, measurement):
    """Join semantic roles to actual Blender bounds, using explicit object identities."""
    if measurement.get('schema') != 'environment-surface-report/1':
        raise ValueError('Expected actual surface measurement')
    data = copy.deepcopy(spec)
    base = data['spatial']
    if base['unit'] != 'm' or base['coordinate'] != measurement['coordinate']:
        raise ValueError('Placement and measured coordinates must agree in meters')
    measured = unique(measurement['objects'])
    existing = set(unique(base['objects']))
    for role in data.get('measured_objects', []):
        names = role.get('objects', [])
        if not names:
            raise ValueError('Measured role needs explicit object names')
        for name in names:
            if name not in measured or name in existing:
                raise ValueError('Missing or repeated measured object: '+name)
            obj = measured[name]
            bounds = obj['bounds_m']
            if any(b[1]-b[0] <= 1e-8 for b in bounds):
                raise ValueError('Flat geometry needs an explicit collision thickness: '+name)
            base['objects'].append({'id':name, 'footprint':obj['footprint_m'],
                'z_min':bounds[2][0], 'z_max':bounds[2][1], 'kind':role['purpose'],
                'blocks_routes':role['blocks_routes'], 'measurement_source':measurement['source_sha256']})
            existing.add(name)
    base['source'] = measurement['source']
    return data


def analyze(data):
    if data.get('schema') != 'environment-placement/1':
        raise ValueError('Expected environment-placement/1')
    s = spatial_module()
    base = copy.deepcopy(data['spatial'])
    objects = unique(base['objects'])
    report = s.analyze(base)
    issues = [issue(item['kind'], **{k:v for k,v in item.items() if k != 'kind'}) for item in report['issues']]
    checks = []
    doors = unique(data.get('doors', []))
    clearance_ids = unique(data.get('clearances', []))
    for cid, zone in clearance_ids.items():
        s.validate_polygon(zone['footprint'])
        if zone['z_max'] <= zone['z_min']:
            raise ValueError('Invalid clearance height')
        if not zone.get('purpose'):
            raise ValueError('Clearance needs purpose: ' + cid)
        unknown = set(zone.get('ignore', []))-set(objects)
        if unknown:
            raise ValueError('Unknown ignored object: ' + str(unknown))
        for oid, obj in objects.items():
            if oid in zone.get('ignore', []) or not obj.get('blocks_routes', True):
                continue
            if max(zone['z_min'], obj['z_min']) >= min(zone['z_max'], obj['z_max']):
                continue
            if polygon_distance(zone['footprint'], obj['footprint'], s) < 1e-8:
                issues.append(issue('clearance_occupied', zone=cid, object=oid, purpose=zone['purpose']))
    for did, door in doors.items():
        if door.get('purpose') not in ('entrance', 'sealed', 'decoration'):
            raise ValueError('Door purpose must be entrance, sealed, or decoration')
        angle = number(door['angle_deg'], 'door angle', -360, 360)
        if door['purpose'] == 'sealed' and abs(angle) > 1e-5:
            issues.append(issue('sealed_door_visually_open', door=did))
        if door['purpose'] == 'entrance' and not door.get('clearance_id'):
            issues.append(issue('entrance_clearance_missing', door=did))
        if door.get('clearance_id') and door['clearance_id'] not in clearance_ids:
            raise ValueError('Unknown door clearance')
        if door['purpose'] == 'entrance' and not door.get('connection'):
            issues.append(issue('entrance_connection_unrecorded', 'warning', door=did))
        width = number(door['width'], 'leaf width', 1e-9)
        thickness = number(door['thickness'], 'leaf thickness', 1e-9)
        closed = number(door['closed_yaw_deg'], 'closed yaw')
        hinge = door['hinge']
        if len(hinge) != 2:
            raise ValueError('Door hinge needs XY coordinates')
        for v in hinge:
            number(v, 'hinge')
        if door['z_max'] <= door['z_min']:
            raise ValueError('Invalid door height')
        ignored = set(door.get('ignore', []))
        if ignored-set(objects):
            raise ValueError('Unknown door ignored object')
        travel = door.get('check_travel', False)
        steps = max(1, math.ceil(abs(angle)/5)) if travel else 1
        angles = [angle*i/steps for i in range(steps+1)] if travel else [angle]
        # Conservative expansion covers motion between samples, including thin obstructions.
        padding = math.hypot(width, thickness/2)*math.radians(abs(angle)/steps)/2 if travel else 0
        hit = set()
        for degrees in angles:
            radians = math.radians(closed+degrees)
            c, t = math.cos(radians), math.sin(radians)
            poly = [[hinge[0]+x*c-y*t, hinge[1]+x*t+y*c]
                    for x,y in ((0,-thickness/2),(width,-thickness/2),(width,thickness/2),(0,thickness/2))]
            for oid, obj in objects.items():
                if oid in ignored or oid in hit or not obj.get('blocks_routes', True):
                    continue
                if max(door['z_min'],obj['z_min']) >= min(door['z_max'],obj['z_max']):
                    continue
                if polygon_distance(poly, obj['footprint'], s) <= padding+1e-8:
                    hit.add(oid)
                    issues.append(issue('door_sweep_candidate' if travel else 'door_pose_candidate',
                                        door=did, object=oid, angle_deg=degrees, conservative_padding=padding))
        checks.append({'door':did, 'travel_checked':travel, 'samples':len(angles)})
    return issues_report('environment-placement-report', issues, measurements=report['measurements'],
                         doors=checks, engine_collision_test='not_performed',
                         note='Extruded footprints are conservative proxies. Keep door holes as separate solids; confirm flagged contacts and traversability in the engine.')
