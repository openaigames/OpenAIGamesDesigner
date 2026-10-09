"""Verified quality-first model defaults; new jobs pin these before approval.

No network lookup or automatic model fallback happens during execution.
Update with official API evidence, not by sorting version names or release dates.
"""
from copy import deepcopy

CHECKED_AT = '2026-10-09'
TRIPO = 'v3.1-20260211'
HUNYUAN = '3.1'
SEEDREAM = 'doubao-seedream-5-0-pro-260628'
SEEDANCE = 'doubao-seedance-2-5-260628'
ELEVENLABS = {'speech': 'eleven_v4', 'music': 'music_v2_5',
              'sound_effect': 'eleven_text_to_sound_v2'}


def selection(provider, parameters):
    """Return a model field/default, or None for routes with no model selector."""
    if provider == 'elevenlabs':
        model = ELEVENLABS.get(parameters.get('kind'))
        return ('model_id', model) if model else None
    if provider == 'tripo':
        return None if parameters.get('type') == 'generate_multiview_image' else ('model_version', TRIPO)
    return {'hunyuan3d': ('Model', HUNYUAN), 'seedream': ('model', SEEDREAM),
            'seedance': ('model', SEEDANCE)}.get(provider)


def prepare(provider, request, settings=None):
    """Pin a missing model without mutating callers or explicit version choices."""
    prepared = deepcopy(request)
    if provider == 'hunyuan3d' and settings is not None and settings.get('mode') != 'api':
        return prepared
    parameters = prepared.setdefault('parameters', {})
    selected = selection(provider, parameters)
    if selected:
        field, model = selected
        parameters.setdefault(field, model)
    return prepared
