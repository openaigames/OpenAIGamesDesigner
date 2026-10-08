"""Generation modes implemented by this installation. No network or credentials."""
from copy import deepcopy

TRIPO_BASE = 'https://api.tripo3d.ai/v2/openapi'
TRIPO_IMAGE_BASE = 'https://openapi.tripo3d.ai/v3'
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


def connection(provider, settings, image_views=False):
    if provider == 'tripo':
        base = TRIPO_IMAGE_BASE if image_views else TRIPO_BASE
        return {'authentication': 'API Key', 'key_page': 'https://developers.tripo3d.ai/zh/keys',
                'submit_url': base + ('/generation/image-to-multiview' if image_views else '/task'),
                'query_url': base + ('/tasks/{task_id}' if image_views else '/task/{task_id}')}
    if provider != 'hunyuan3d':
        raise ValueError('这里只列出 Tripo 与混元 3D 的接口。')
    if settings.get('auth', 'tc3') == 'api_key':
        return {'authentication': 'API Key', 'key_page': 'https://console.cloud.tencent.com/ai3d/api-key',
                'submit_url': HUNYUAN_KEY_BASE + '/submit', 'query_url': HUNYUAN_KEY_BASE + '/query'}
    return {'authentication': 'SecretId / SecretKey（TC3 签名）',
            'key_page': 'https://console.cloud.tencent.com/cam/capi',
            'submit_url': 'https://' + HUNYUAN_HOST + '/', 'query_url': 'https://' + HUNYUAN_HOST + '/',
            'submit_action': 'SubmitHunyuanTo3DProJob', 'query_action': 'QueryHunyuanTo3DProJob'}


def describe(provider, request, settings=None):
    p, images = request.get('parameters', {}), request.get('inputs', [])
    settings = settings or {}
    if provider == 'tripo':
        mode = p.get('type', 'image_to_model' if images else 'text_to_model')
        if mode not in TRIPO_MODES:
            raise ValueError('此安装版本未接入所选 Tripo 生成方式。')
        result = deepcopy(TRIPO_MODES[mode])
        result.update(mode=mode, model=p.get('model_version', '由服务选择'),
                      views=list(TRIPO_VIEWS if mode == 'multiview_to_model' else ('front',)))
        if mode == 'generate_multiview_image':
            result['model'] = '此接口不接收模型版本'
    elif provider == 'hunyuan3d':
        model, mode = p.get('Model', '3.0'), p.get('GenerateType', 'Normal')
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
    result.update(provider=provider, prompt_with_images=result['prompt'] == 'optional_with_image',
                  **connection(provider, settings, result['output'] == 'images'))
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


def markdown():
    lines = ['# 本地已接入的 3D 生成方式', '',
             '本表由 `tools/generation_capabilities.py` 根据程序中的能力说明生成。它说明当前安装版本接入了什么，不代表账户已开通、网络可用或生成质量已通过检查。', '',
             '| 服务 | 模型版本 | 方式 | 图片数 | 文字 | 输出 |',
             '| --- | --- | --- | --- | --- | --- |']
    labels = {'required': '需要', 'none': '不发送', 'optional_with_image': '可与草图一起发送'}
    for provider in ('tripo', 'hunyuan3d'):
        for row in catalog(provider):
            count = str(row['min_images']) if row['min_images'] == row['max_images'] else f"{row['min_images']}–{row['max_images']}"
            lines.append(f"| {provider} | {row['model']} | {row['label']} / {row['mode']} | {count} | {labels[row['prompt']]} | {'多视图图片' if row['output'] == 'images' else '模型'} |")
    lines += ['', '图片方向、格式、大小及具体参数仍由提交检查核对。多视图图片须先检查同一对象的比例和构造，再作为下一次模型生成的输入。',
              '', '填写本地制作说明不等于发送了约束文字。发送记录与结果是否遵守要求分别检查。', '']
    return '\n'.join(lines)
