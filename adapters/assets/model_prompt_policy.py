"""Explicit user/project requirement for a provider-consumed 3D prompt.

This is a capability gate, not an approval receipt or a quality guarantee.
It deliberately does not invent image+text support in a provider API.
"""
import json
import hashlib
import os
from pathlib import Path

PROVIDERS = ('tripo', 'hunyuan3d')


class PromptPolicyError(ValueError):
    pass


def user_path():
    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share')))
    return base / 'OpenAIGamesDesigner' / 'generation-policy.json'


def policy(root=None):
    paths = [user_path()]
    if root is not None:
        paths.append(Path(root) / '.openaigame/generation-policy.json')
    enabled = False
    sources = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 16384:
                raise ValueError()
            value = json.loads(path.read_text('utf-8-sig'))
            if not isinstance(value, dict) or value.get('version') != 1:
                raise ValueError()
            flag = value.get('require_3d_prompt', False)
            if type(flag) is not bool:
                raise ValueError()
        except (OSError, ValueError, TypeError):
            raise PromptPolicyError('3D Prompt 要求配置无法读取，请修复 generation-policy.json；不会降级为无提示词生成。') from None
        # A project can strengthen a personal requirement, not silently waive it.
        enabled |= flag
        if flag:
            sources.append('project' if root is not None and path == paths[-1] else 'user')
    return {'require_3d_prompt': enabled, 'sources': sources}



def image_request_fingerprint(provider, request, settings, root):
    """Bind an explicit image-only choice to this project, parameters and real files.

    This records a changed creative preference; paid generation still requires
    the independent, single-use generation_approval receipt.
    """
    if root is None or settings.get('mode') != 'api' or provider != 'tripo':
        return None
    if request.get('parameters', {}).get('type') != 'multiview_to_model':
        return None
    entries = request.get('inputs', [])
    if not isinstance(entries, list) or not 2 <= len(entries) <= 4:
        return None
    base = Path(root).resolve()
    rows = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('view') not in ('front', 'back', 'left', 'right'):
            return None
        name = entry.get('path')
        actual = entry.get('snapshot', name)
        if not isinstance(name, str) or not isinstance(actual, str):
            return None
        path = (base / actual).resolve()
        if not path.is_relative_to(base) or not path.is_file() or not 0 < path.stat().st_size <= 20 * 1024**2:
            return None
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if entry.get('sha256') and entry['sha256'] != digest:
            return None
        rows.append({'path': name, 'view': entry['view'], 'sha256': digest})
    if len({row['view'] for row in rows}) != len(rows) or not any(row['view'] == 'front' for row in rows):
        return None
    value = {'project': os.path.normcase(str(base)), 'provider': provider,
             'parameters': request.get('parameters', {}),
             'inputs': sorted(rows, key=lambda row: row['view'])}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def image_only_choice(provider, request, settings, root):
    if root is None:
        return None
    path = Path(root) / '.openaigame/generation-policy.json'
    if not path.is_file():
        return None
    value = json.loads(path.read_text('utf-8-sig'))
    choices = value.get('image_only_requests', [])
    if not isinstance(choices, list) or len(choices) > 32:
        raise PromptPolicyError('项目的单次图片生成偏好记录无效。')
    for choice in choices:
        if (not isinstance(choice, dict) or choice.get('provider') != 'tripo'
                or not isinstance(choice.get('reason'), str) or not choice['reason'].strip()
                or not isinstance(choice.get('request_sha256'), str)
                or len(choice['request_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in choice['request_sha256'])):
            raise PromptPolicyError('项目的单次图片生成偏好记录无效。')
    if not choices:
        return None
    try:
        fingerprint = image_request_fingerprint(provider, request, settings, root)
    except (OSError, ValueError, TypeError):
        return None
    return next((choice for choice in choices if choice['provider'] == provider
                 and choice['request_sha256'] == fingerprint), None)


def assess(provider, request, settings, root=None):
    if provider not in PROVIDERS:
        return None
    # This route outputs reference images, not a 3D model. Keep the existing
    # 3D prompt policy and independent paid approval intact.
    if provider == 'tripo' and request.get('parameters', {}).get('type') == 'generate_multiview_image':
        from . import tripo_inputs
        tripo_inputs.validate(request)
        return None
    preference_required = policy(root)['require_3d_prompt']
    choice = image_only_choice(provider, request, settings, root)
    active = preference_required and choice is None
    params = request.get('parameters', {})
    images = bool(request.get('inputs'))
    field = 'prompt' if provider == 'tripo' else 'Prompt'
    prompt = params.get(field)
    present = isinstance(prompt, str) and bool(prompt.strip())
    from . import generation_capabilities
    capability = generation_capabilities.describe(provider, request, settings) if settings.get('mode') == 'api' else None
    joint = bool(capability and capability['prompt_with_images'] and len(request.get('inputs', [])) == 1)
    supported = settings.get('mode') == 'api' and (not images or joint)
    reason = None
    if active:
        if not supported:
            reason = ('已要求每次 3D 生成实际发送约束 Prompt。当前接口模式没有已确认的图片＋Prompt 支持；'
                      '请保留参考图并选择支持联合输入的模式。不会丢弃图片、把文字移到本地说明或自动切换模型。')
        elif not present:
            reason = '已要求每次 3D 生成实际发送约束 Prompt；请填写服务参数 ' + field + '。本地 brief 不计作 Prompt。'
    return {'required': active, 'preference_required': preference_required,
            'image_only_choice': choice, 'field': field, 'prompt': prompt if present else '',
            'present': present, 'image_prompt_supported': joint,
            'route_support_confirmed': supported, 'blocked': reason is not None,
            'reason': reason, 'quality_effect_verified': False}


def require(provider, request, settings, root=None):
    result = assess(provider, request, settings, root)
    if result and result['blocked']:
        raise PromptPolicyError(result['reason'])
    return result


def submission_evidence(root, job):
    """Read persisted transmission, never infer acceptance from a filled field."""
    if job.get('provider') not in PROVIDERS:
        return None
    base = Path(root).resolve() / '.openaigame/asset-jobs' / job['job_id']
    for number in range(len(job.get('attempts', [])), 0, -1):
        path = base / ('attempt-' + str(number)) / 'transmission.json'
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 128 * 1024:
                return {'status': 'unreadable'}
            value = json.loads(path.read_text('utf-8-sig'))
            field = 'prompt' if job['provider'] == 'tripo' else 'Prompt'
            text = value.get('parameters', {}).get(field)
            return {'status': value.get('status', 'unknown'),
                    'prompt_recorded': isinstance(text, str) and bool(text.strip()),
                    'prompt': text if isinstance(text, str) else '',
                    'provider_job_id': value.get('provider_job_id')}
        except (OSError, ValueError, TypeError, AttributeError):
            return {'status': 'unreadable'}
    return {'status': 'not_submitted'}
