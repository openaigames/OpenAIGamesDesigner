"""Versioned, project-owned humanoid profiles. No inferred map is auto-approved."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path

ROLES = ('root', 'hips', 'spine', 'head') + tuple(
    bone + '_' + side for side in ('L', 'R')
    for bone in ('thigh', 'shin', 'foot', 'upperarm', 'forearm', 'hand'))
AXES = {'+X': (1, 0, 0), '-X': (-1, 0, 0), '+Y': (0, 1, 0), '-Y': (0, -1, 0)}


def finite(value, label, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(label + ': finite number in ' + str((low, high)) + ' required')
    return value


def bone_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]+', value):
        raise ValueError('Profile bone name is not portable to the playback adapters: ' + str(value))
    return value


def validate(profile):
    p = copy.deepcopy(profile)
    if p.get('schema') != 'oagd.character-profile/1':
        raise ValueError('Expected oagd.character-profile/1')
    required={'schema','id','revision','source','target','roles','coordinates','reference_pose','unmapped_bones','root_motion','repair_budget','clip_policies'}
    if set(p)!=required:
        raise ValueError('Character profile fields differ: missing='+str(sorted(required-set(p)))+' unknown='+str(sorted(set(p)-required)))
    if not isinstance(p.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]+', p['id']):
        raise ValueError('Safe profile id required')
    if type(p.get('revision')) is not int or p['revision'] < 1:
        raise ValueError('Positive integer profile revision required')
    if set(p['roles']) != set(ROLES):
        raise ValueError('Profile requires the explicit 16 humanoid roles; non-humanoids use oagd.motion/1')
    for field in ('coordinates','reference_pose','unmapped_bones'):
        if not isinstance(p[field],dict) or set(p[field])!={'source','target'}:
            raise ValueError(field+': explicit source and target settings required')
    for role, pair in p['roles'].items():
        if set(pair) != {'source', 'target'}:
            raise ValueError('Each role needs source and target bone: ' + role)
    for side in ('source', 'target'):
        if not isinstance(p[side],dict) or set(p[side])!={'file','sha256','armature'}:
            raise ValueError(side+': explicit file, sha256 and armature required')
        names = [bone_name(pair[side]) for pair in p['roles'].values()]
        if len({n.casefold() for n in names}) != len(names):
            raise ValueError(side + ': duplicate role bone (including case-only duplicates)')
        c = p['coordinates'][side]
        if set(c) != {'up', 'forward', 'unit'} or c['up'] != '+Z' or c['unit'] != 'metre' or c['forward'] not in AXES:
            raise ValueError(side + ': normalize an export copy to metre / +Z up; declare horizontal anatomical forward')
        ref = p['reference_pose'][side]
        if set(ref) != {'local_rotations_xyzw', 'basis'} or not isinstance(ref['basis'], str) or not ref['basis'].strip():
            raise ValueError(side + ': reference pose needs calibration basis and local rotations')
        if not isinstance(ref['local_rotations_xyzw'], dict):
            raise ValueError('Reference rotations must be an explicit bone dictionary')
        for name, q in ref['local_rotations_xyzw'].items():
            bone_name(name)
            if not isinstance(q, list) or len(q) != 4 or abs(sum(finite(v, 'reference quaternion', -1, 1)**2 for v in q)-1) > 1e-4:
                raise ValueError('Reference quaternion must be normalized: ' + name)
        extras = p['unmapped_bones'][side]
        policy = 'ignore' if side == 'source' else 'inherit_rest'
        if not isinstance(extras, dict) or any(value != policy for value in extras.values()):
            raise ValueError(side + ': unmapped bones require explicit ' + policy + '; twist redistribution is unsupported')
        for name in extras:
            bone_name(name)
            if name in names:
                raise ValueError('Mapped bone also declared unmapped: ' + name)
    if set(p['unmapped_bones']) != {'source', 'target'}:
        raise ValueError('Unknown extra-bone policy')
    budget = p['repair_budget']
    if set(budget) != {'max_position_m', 'max_rotation_deg', 'max_edited_fraction'}:
        raise ValueError('Explicit position, rotation and edited-frame repair budgets required')
    finite(budget['max_position_m'], 'repair position budget', 0, 1)
    finite(budget['max_rotation_deg'], 'repair rotation budget', 0, 180)
    finite(budget['max_edited_fraction'], 'repair edited fraction', 0, 1)
    if not isinstance(p['clip_policies'], dict):
        raise ValueError('Explicit clip policies required')
    motion = p['root_motion']
    if set(motion) != {'owner', 'translation', 'scale', 'translation_roles'}:
        raise ValueError('Explicit root ownership, scale and translated roles required')
    if not isinstance(motion['translation_roles'],list) or any(r not in ROLES or r == 'root' for r in motion['translation_roles']) or len(set(motion['translation_roles'])) != len(motion['translation_roles']):
        raise ValueError('Invalid translated roles')
    # Full root/clip validation is shared with the legacy motion contract.
    return p


def resolve(spec, base):
    """Resolve a profile once; bind its bytes and all normalized choices to the job."""
    if 'profile' not in spec:
        return copy.deepcopy(spec)
    allowed = {'schema', 'profile', 'clips', 'tolerances'}
    if set(spec) - allowed:
        raise ValueError('Profile owns rig, mapping and repair policies; remove duplicate spec fields')
    ref = spec['profile']; path = (Path(base) / ref['file']).resolve()
    data = path.read_bytes(); sha = hashlib.sha256(data).hexdigest()
    if sha != ref.get('sha256'):
        raise ValueError('Character profile sha256 changed; review the new revision explicitly')
    p = validate(json.loads(data.decode('utf-8-sig')))
    if p['revision'] != ref.get('revision'):
        raise ValueError('Character profile revision mismatch')
    out = {k: copy.deepcopy(v) for k, v in spec.items() if k != 'profile'}
    for side in ('source', 'target'):
        out[side] = copy.deepcopy(p[side])
        out[side]['file'] = str((path.parent / p[side]['file']).resolve())
    pairs = p['roles']; target = lambda role: pairs[role]['target']
    out['mapping'] = {pair['target']: pair['source'] for pair in pairs.values()}
    a = AXES[p['coordinates']['source']['forward']]; b = AXES[p['coordinates']['target']['forward']]
    yaw = math.atan2(b[1], b[0]) - math.atan2(a[1], a[0])
    out['alignment_xyzw'] = [0, 0, math.sin(yaw/2), math.cos(yaw/2)]
    out['root_motion'] = {k: v for k, v in p['root_motion'].items() if k != 'translation_roles'}
    out['root_motion'].update(bone=target('root'), translation_bones=[target(r) for r in p['root_motion']['translation_roles']])
    for clip in out['clips']:
        if set(clip) - {'id', 'action', 'start_frame', 'end_frame', 'fps'}:
            raise ValueError('Clip repairs/contact windows belong to the character profile')
        if clip['id'] not in p['clip_policies']:
            raise ValueError('Missing profile policy for clip: ' + clip['id'])
        policy = copy.deepcopy(p['clip_policies'][clip['id']])
        if set(policy) - {'repairs', 'translation_offsets_m'}:
            raise ValueError('Unknown profile clip policy')
        offsets=policy.get('translation_offsets_m',{})
        if not isinstance(offsets,dict) or any(r not in p['root_motion']['translation_roles'] for r in offsets):
            raise ValueError('Calibration offsets require explicitly permitted translation roles')
        for role,vector in offsets.items():
            if not isinstance(vector,list) or len(vector)!=3:raise ValueError('Calibration offset must be a three-component metre vector')
            for v in vector:finite(v,'calibration offset',-.5,.5)
        clip['target_translation_offsets_m']={target(r):v for r,v in offsets.items()}
        repairs = policy.get('repairs', {})
        for kind in ('rotation_spikes', 'loop'):
            if kind in repairs:
                rule = repairs[kind]
                rule['bones'] = [target(r) for r in rule.pop('bone_roles')]
        for rule in repairs.get('contacts', []):
            rule['chain'] = [target(r) for r in rule.pop('chain_roles')]
        clip['repairs'] = repairs
    out['character_profile'] = p
    out['profile_dependency'] = {'file': str(path), 'sha256': sha, 'id': p['id'], 'revision': p['revision']}
    return out
