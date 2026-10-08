"""Bounded requests for read-only mesh audits and derived mesh configuration."""
import math
import re

CONFIG_FIELDS = {'op', 'source', 'path', 'strategy', 'asset_role', 'lods',
                 'nanite', 'platform_supports_nanite', 'lod_for_collision'}
NANITE_FIELDS = {'preserve_area', 'keep_percent_triangles', 'trim_relative_error',
                 'fallback_target', 'fallback_percent_triangles', 'fallback_relative_error'}


def asset_path(value, writable=False):
    root = 'Game' if writable else '[A-Za-z][A-Za-z0-9_]*'
    if (not isinstance(value, str) or
            not re.fullmatch('/' + root + r'/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*', value)):
        raise ValueError('Expected an asset package path' + (' under /Game/' if writable else ''))


def number(value, lower, upper, positive=False):
    if (type(value) not in (float, int) or not math.isfinite(value) or
            not lower <= value <= upper or (positive and value == 0)):
        raise ValueError('Mesh settings require finite numbers in their documented range')


def validate_operation(op):
    if not isinstance(op, dict) or set(op) - CONFIG_FIELDS:
        raise ValueError('Unknown mesh configuration fields')
    if op.get('op') != 'static_mesh_configure':
        raise ValueError('Expected static_mesh_configure')
    asset_path(op.get('source'))
    asset_path(op.get('path'), writable=True)
    if op['source'] == op['path']:
        raise ValueError('Configure a new derived asset; source must remain editable')
    if op.get('asset_role') not in ('building', 'prop', 'foliage', 'ground'):
        raise ValueError('Explicit asset_role required')
    strategy = op.get('strategy')
    if strategy == 'lod':
        if 'nanite' in op or 'platform_supports_nanite' in op:
            raise ValueError('LOD strategy disables Nanite on the derived copy')
        lods = op.get('lods')
        if not isinstance(lods, list) or not 2 <= len(lods) <= 8:
            raise ValueError('LOD strategy requires 2..8 levels including LOD0')
        previous_percent, previous_screen = 2, 2
        for index, lod in enumerate(lods):
            if not isinstance(lod, dict) or set(lod) != {'percent_triangles', 'screen_size'}:
                raise ValueError('Each LOD needs percent_triangles and screen_size')
            percent, screen = lod['percent_triangles'], lod['screen_size']
            number(percent, 0, 1, positive=True)
            number(screen, 0, 1)
            if percent >= previous_percent or screen >= previous_screen:
                raise ValueError('LOD percentages and screen sizes must decrease')
            if index == 0 and (percent != 1 or screen != 1):
                raise ValueError('LOD0 must retain full geometry with screen_size 1')
            previous_percent, previous_screen = percent, screen
    elif strategy == 'nanite':
        if 'lods' in op:
            raise ValueError('Nanite strategy preserves existing conventional LODs')
        if op.get('platform_supports_nanite') is not True:
            raise ValueError('Confirm target platform supports Nanite in the request')
        settings = op.get('nanite', {})
        if not isinstance(settings, dict) or set(settings) - NANITE_FIELDS:
            raise ValueError('Unsupported Nanite settings')
        if 'preserve_area' in settings:
            if type(settings['preserve_area']) is not bool:
                raise ValueError('preserve_area must be boolean')
            if settings['preserve_area'] and op['asset_role'] != 'foliage':
                raise ValueError('Preserve Area is for foliage')
        for key in ('keep_percent_triangles', 'fallback_percent_triangles'):
            if key in settings:
                number(settings[key], 0, 1, positive=True)
        for key in ('trim_relative_error', 'fallback_relative_error'):
            if key in settings:
                number(settings[key], 0, 1e6)
        target = settings.get('fallback_target')
        if target is not None and target not in ('auto', 'percent_triangles', 'relative_error'):
            raise ValueError('Invalid fallback_target')
        if 'fallback_percent_triangles' in settings and target != 'percent_triangles':
            raise ValueError('Fallback percentage needs explicit percent_triangles target')
        if 'fallback_relative_error' in settings and target != 'relative_error':
            raise ValueError('Fallback error needs explicit relative_error target')
    else:
        raise ValueError('Choose lod or nanite strategy')
    if 'lod_for_collision' in op:
        index = op['lod_for_collision']
        if type(index) is not int or index < 0 or (strategy == 'lod' and index >= len(op['lods'])):
            raise ValueError('Collision LOD must refer to an existing level')


def validate_request(request):
    if 'mesh_audit' in request:
        spec = request['mesh_audit']
        if request['mode'] != 'inspect' or not isinstance(spec, dict):
            raise ValueError('mesh_audit uses read-only inspect mode')
        if set(spec) - {'paths', 'include_scene', 'warning_limits'}:
            raise ValueError('Unknown mesh audit fields')
        paths = spec.get('paths', [])
        if not isinstance(paths, list) or len(paths) > 512:
            raise ValueError('Use up to 512 unique explicit mesh package paths')
        for path in paths:
            asset_path(path)
        if len(set(paths)) != len(paths):
            raise ValueError('Duplicate mesh paths')
        include_scene = spec.get('include_scene', False)
        if type(include_scene) is not bool or (include_scene and not request.get('scene')):
            raise ValueError('Scene audit needs include_scene boolean and explicit saved scene')
        if not paths and not include_scene:
            raise ValueError('Select assets or a loaded scene for audit')
        limits = spec.get('warning_limits', {})
        if not isinstance(limits, dict) or set(limits) - {'triangles', 'material_slots', 'texture_dimension'}:
            raise ValueError('Unknown warning limits')
        if any(type(v) is not int or v <= 0 for v in limits.values()):
            raise ValueError('Warning limits must be positive integers; they are project-specific')
    destinations = set()
    for op in request.get('operations', []):
        if op.get('op') == 'static_mesh_configure':
            validate_operation(op)
            if op['path'] in destinations:
                raise ValueError('Duplicate derived mesh destination')
            destinations.add(op['path'])
