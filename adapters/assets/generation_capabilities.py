"""Generation modes implemented by this installation. No network or credentials."""
from copy import deepcopy
from . import model_defaults

TRIPO_BASE = 'https://openapi.tripo3d.ai/v3'
TRIPO_IMAGE_BASE = TRIPO_BASE
TRIPO_ENDPOINTS = {
    'text_to_model': '/generation/text-to-model',
    'image_to_model': '/generation/image-to-model',
    'multiview_to_model': '/generation/multiview-to-model',
    'generate_multiview_image': '/generation/image-to-multiview',
}
HUNYUAN_KEY_BASE = 'https://api.ai3d.cloud.tencent.com/v1/ai3d'
HUNYUAN_HOST = 'ai3d.tencentcloudapi.com'
TRIPO_VIEWS = ('front', 'left', 'back', 'right')
HUNYUAN_VIEWS = ('front', 'left', 'right', 'back', 'top', 'bottom', 'left_front', 'right_front')
HUNYUAN_MODELS = {'3.0': ('Normal', 'Geometry', 'LowPoly', 'Sketch'),
                  '3.1': ('Normal', 'Geometry')}
TRIPO_MODES = {
    'text_to_model': {'label': '文字生成模型', 'min_images': 0, 'max_images': 0, 'prompt': 'required', 'output': 'model'},
    'image_to_model': {'label': '单图生成模型', 'min_images': 1, 'max_images': 1, 'prompt': 'none', 'output': 'model'},
    'multiview_to_model': {'label': '多视图生成模型', 'min_images': 2, 'max_images': 4, 'prompt': 'none', 'output': 'model'},
    'generate_multiview_image': {'label': '单图生成多视图图片', 'min_images': 1, 'max_images': 1, 'prompt': 'none', 'output': 'images'},
}


def connection(provider, settings, image_views=False, mode=None):
    if provider == 'tripo':
        mode = mode or ('generate_multiview_image' if image_views else 'text_to_model')
        return {'authentication': 'API Key', 'key_page': 'https://developers.tripo3d.ai/zh/keys',
                'submit_url': TRIPO_BASE + TRIPO_ENDPOINTS[mode],
                'query_url': TRIPO_BASE + '/tasks/{task_id}'}
    if provider != 'hunyuan3d':
        raise ValueError('这里只列出 Tripo 与混元 3D 的接口。')
    if settings.get('auth', 'tc3') == 'api_key':
        return {'authentication': 'API Key', 'key_page': 'https://console.cloud.tencent.com/ai3d/api-key',
                'submit_url': HUNYUAN_KEY_BASE + '/submit', 'query_url': HUNYUAN_KEY_BASE + '/query'}
    return {'authentication': 'SecretId / SecretKey（TC3 签名）',
            'key_page': 'https://console.cloud.tencent.com/cam/capi',
            'submit_url': 'https://' + HUNYUAN_HOST + '/', 'query_url': 'https://' + HUNYUAN_HOST + '/',
            'submit_action': 'SubmitHunyuanTo3DProJob', 'query_action': 'QueryHunyuanTo3DProJob'}


def describe(provider, request, settings=None, historical=False):
    p, images = request.get('parameters', {}), request.get('inputs', [])
    settings = settings or {}
    if provider == 'tripo':
        mode = p.get('type', 'image_to_model' if images else 'text_to_model')
        if mode not in TRIPO_MODES:
            raise ValueError('此安装版本未接入所选 Tripo 生成方式。')
        result = deepcopy(TRIPO_MODES[mode])
        result.update(mode=mode, model=p.get('model_version', model_defaults.TRIPO),
                      views=list(TRIPO_VIEWS if mode == 'multiview_to_model' else ('front',)))
        if mode == 'generate_multiview_image':
            result['model'] = '此接口不接收模型版本'
    elif provider == 'hunyuan3d':
        model, mode = p.get('Model', '3.0' if historical else model_defaults.HUNYUAN), p.get('GenerateType', 'Normal')
        if model not in HUNYUAN_MODELS or mode not in HUNYUAN_MODELS[model]:
            raise ValueError('所选混元模型版本与生成方式不匹配。')
        sketch = mode == 'Sketch'
        result = {'mode': mode, 'model': model, 'label': '草图与文字生成模型' if sketch else
                  '多视图生成模型' if len(images) > 1 else '单图生成模型' if images else '文字生成模型',
                  'min_images': 1 if sketch or images else 0,
                  'max_images': 1 if sketch else (4 if model == '3.0' else 8) if images else 0,
                  'prompt': 'optional_with_image' if sketch else 'none' if images else 'required',
                  'views': ['front'] if sketch else list(HUNYUAN_VIEWS[:4] if model == '3.0' else HUNYUAN_VIEWS),
                  'output': 'model'}
    else:
        raise ValueError('这里只列出 Tripo 与混元 3D 的生成方式。')
    if historical and provider == 'tripo' and result['output'] == 'model' and 'model_version' not in p:
        result['model'] = '未固定版本（历史服务默认）'
    if historical and provider == 'hunyuan3d' and 'Model' not in p:
        result['model'] = '3.0（历史默认，任务未固定）'
    result.update(provider=provider, prompt_with_images=result['prompt'] == 'optional_with_image',
                  **connection(provider, settings, result['output'] == 'images', result['mode']))
    return result


def validate_mode(provider, request):
    result = describe(provider, request)
    inputs, params = request.get('inputs', []), request.get('parameters', {})
    if not result['min_images'] <= len(inputs) <= result['max_images']:
        raise ValueError('参考图数量与所选生成方式不匹配。')
    field = 'prompt' if provider == 'tripo' else 'Prompt'
    prompt = params.get(field)
    if result['prompt'] == 'required' and (not isinstance(prompt, str) or not prompt.strip()):
        raise ValueError('文字生成需要填写约束文字（Prompt）。')
    if result['prompt'] == 'none' and field in params:
        raise ValueError('此图片生成方式不接收约束文字（Prompt）；请保留当前要求，再选择合适的生成方式。')
    for item in inputs:
        view = item.get('view', 'front') if isinstance(item, dict) else 'front'
        if view not in result['views']:
            raise ValueError('参考图方向与所选模型版本或生成方式不匹配。')
    return result


def catalog(provider, settings=None):
    if provider == 'tripo':
        requests = [{'parameters': {'type': mode}, 'inputs': [{}] * data['min_images']}
                    for mode, data in TRIPO_MODES.items()]
    elif provider == 'hunyuan3d':
        requests = [{'parameters': {'Model': model, 'GenerateType': mode}, 'inputs': [{}] * count}
                    for model, modes in HUNYUAN_MODELS.items() for mode in modes
                    for count in ((1,) if mode == 'Sketch' else (0, 1, 3))]
    else:
        return []
    return [describe(provider, request, settings) for request in requests]


def markdown(language='en'):
    if language not in ('en', 'zh-CN'):
        raise ValueError('Supported documentation languages: en, zh-CN')
    english = language == 'en'
    lines = ['# Supported 3D Generation Modes' if english else '# 3D 生成方式', '',
             '[English](generation-capabilities.md) | [简体中文](generation-capabilities.zh-CN.md)', '',
             ('Generated by `tools/generation_capabilities.py` from adapter definitions. These modes do not confirm account access, connectivity, or output quality.' if english else
              '本表由 `tools/generation_capabilities.py --language zh-CN` 根据适配器定义生成。列出的生成方式不代表账户已开通、网络可用或生成质量已通过检查。'), '',
             '| Service | Model | Mode | Images | Text | Output |' if english else '| 服务 | 模型版本 | 方式 | 图片数 | 文字 | 输出 |',
             '| --- | --- | --- | --- | --- | --- |']
    labels = ({'required': 'Required', 'none': 'Not sent', 'optional_with_image': 'Accepted with sketch'} if english else
              {'required': '需要', 'none': '不发送', 'optional_with_image': '可与草图一起发送'})
    names = {'文字生成模型': 'Text to model', '单图生成模型': 'Image to model',
             '多视图生成模型': 'Multiview to model', '单图生成多视图图片': 'Image to multiview images',
             '草图与文字生成模型': 'Sketch and text to model', '此接口不接收模型版本': 'No model parameter'}
    for provider in ('tripo', 'hunyuan3d'):
        for row in catalog(provider):
            count = str(row['min_images']) if row['min_images'] == row['max_images'] else f"{row['min_images']}–{row['max_images']}"
            model = names.get(row['model'], row['model']) if english else row['model']
            label = names[row['label']] if english else row['label']
            output = ('Multiview images' if row['output'] == 'images' else 'Model') if english else ('多视图图片' if row['output'] == 'images' else '模型')
            lines.append(f"| {provider} | {model} | {label} / {row['mode']} | {count} | {labels[row['prompt']]} | {output} |")
    lines += ['', (f'Tripo model generation uses the V3 API. New H3.1 jobs with textures also pin texture model `{model_defaults.TRIPO_TEXTURE}`. Explicit texture choices and retries keep their original parameters. Local image uploads require PNG/JPEG.' if english else
                   f'Tripo 模型生成使用 V3 API。开启纹理的新 H3.1 任务还会固定纹理模型 `{model_defaults.TRIPO_TEXTURE}`；显式纹理选择与重试保留原参数。本地图片上传要求 PNG/JPEG。'),
              '', ('Submission checks validate image views, formats, sizes, and parameters. Check that multiview images preserve the same object\'s proportions and construction before using them for a subsequent model-generation job.' if english else
                   '图片方向、格式、大小及具体参数由提交检查核对。多视图图片须先检查同一对象的比例和构造，再作为下一次模型生成的输入。'),
              '', ('A local brief does not mean constraint text was sent. Check transmission records and output compliance separately.' if english else
                   '填写本地制作说明不等于发送了约束文字。发送记录与结果是否遵守要求分别检查。'), '']
    return '\n'.join(lines)
