"""Local view snapshots -> documented Tencent professional API inputs.

No credentials or network I/O. A brief is local documentation, never a hidden Prompt.
"""
import base64
import hashlib
from pathlib import Path
import struct

from . import generation_capabilities
VIEWS = generation_capabilities.HUNYUAN_VIEWS
BASE_VIEWS = VIEWS[:4]
MAX_ENCODED = 8 * 1024**2


def views(request):
    inputs = request.get('inputs', [])
    if not isinstance(inputs, list) or len(inputs) > 8:
        raise ValueError('混元最多接收正面和七张有方向标记的参考图')
    result = []
    for item in inputs:
        if not isinstance(item, (str, dict)):
            raise ValueError('参考图须为项目路径或含 path、view 的对象')
        path = item if isinstance(item, str) else item.get('path', item.get('snapshot'))
        view = item.get('view') if isinstance(item, dict) else None
        if len(inputs) == 1 and view is None:
            view = 'front'
        if not isinstance(path, str) or not path or view not in VIEWS:
            raise ValueError('多视图每张图片必须注明有效 view，且包含 front 正面')
        result.append((view, path, item))
    labels = [x[0] for x in result]
    if result and (labels.count('front') != 1 or len(set(labels)) != len(labels)):
        raise ValueError('多视图必须包含一个 front，每个方向只能使用一张图片')
    if len(set(x[1] for x in result)) != len(result):
        raise ValueError('不同视角应使用不同图片，不能重复同一路径')
    return result


def validate(request):
    generation_capabilities.validate_mode('hunyuan3d', request)
    params = request.get('parameters', {})
    model = params.get('Model', '3.0')
    mode = params.get('GenerateType', 'Normal')
    if model not in generation_capabilities.HUNYUAN_MODELS:
        raise ValueError('混元模型版本须为 3.0 或 3.1')
    if mode not in ('Normal', 'Geometry', 'LowPoly', 'Sketch'):
        raise ValueError('混元生成模式无效')
    if mode not in generation_capabilities.HUNYUAN_MODELS[model]:
        raise ValueError('当前 3.1 路线未支持 LowPoly / Sketch，请使用 Normal 或 Geometry')
    if 'FaceCount' in params and (type(params['FaceCount']) is not int or not 3000 <= params['FaceCount'] <= 1500000):
        raise ValueError('FaceCount 须为 3000–1500000 的整数')
    if 'EnablePBR' in params and type(params['EnablePBR']) is not bool:
        raise ValueError('EnablePBR 须为布尔值')
    if 'PolygonType' in params and (mode != 'LowPoly' or params['PolygonType'] not in ('triangle', 'quadrilateral')):
        raise ValueError('PolygonType 仅供 LowPoly 模式使用')
    if 'ResultFormat' in params and params['ResultFormat'] not in ('STL', 'USDZ', 'FBX'):
        raise ValueError('ResultFormat 须为 STL、USDZ 或 FBX')
    rows = views(request)
    if model == '3.0' and any(v not in BASE_VIEWS for v, _, _ in rows):
        raise ValueError('顶、底和前斜视图需要 Model 3.1')
    prompt = params.get('Prompt')
    if prompt is not None and (not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1024):
        raise ValueError('Prompt 须为 1–1024 个字符')
    if rows and prompt is not None and not (model == '3.0' and mode == 'Sketch' and len(rows) == 1):
        raise ValueError('此图生模式不能同时发送 Prompt。文字可放入 brief 作为本地说明；不会传给云端。')
    if not rows and not prompt:
        raise ValueError('请选择参考图片，或填写文生 3D 的 Prompt')
    brief = request.get('brief')
    if brief is not None and (not isinstance(brief, str) or len(brief) > 12000):
        raise ValueError('本地制作说明 brief 最长 12000 字符')
    return rows


def image_size(data, kind):
    if kind == 'png' and data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        return struct.unpack('>II', data[16:24])
    if kind == 'jpeg' and data[:2] == b'\xff\xd8':
        pos = 2
        while pos + 4 <= len(data):
            if data[pos] != 255:
                break
            while pos < len(data) and data[pos] == 255:
                pos += 1
            if pos >= len(data):
                break
            marker = data[pos]; pos += 1
            if marker in (0xd8, 0xd9, 0x01) or 0xd0 <= marker <= 0xd7:
                continue
            if pos + 2 > len(data):
                break
            size = int.from_bytes(data[pos:pos + 2], 'big')
            if size < 2 or pos + size > len(data):
                break
            if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf) and size >= 7:
                height, width = struct.unpack('>HH', data[pos + 3:pos + 7])
                return width, height
            pos += size
    if kind == 'webp' and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        if data[12:16] == b'VP8X' and len(data) >= 30:
            return 1 + int.from_bytes(data[24:27], 'little'), 1 + int.from_bytes(data[27:30], 'little')
        if data[12:16] == b'VP8 ' and len(data) >= 30 and data[23:26] == b'\x9d\x01\x2a':
            return int.from_bytes(data[26:28], 'little') & 0x3fff, int.from_bytes(data[28:30], 'little') & 0x3fff
        if data[12:16] == b'VP8L' and len(data) >= 25 and data[20] == 0x2f:
            bits = int.from_bytes(data[21:25], 'little')
            return (bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1
    raise ValueError('图片格式或尺寸头无法读取，请提供有效 PNG/JPEG 图片')


def build_payload(request):
    rows = validate(request)
    payload = dict(request['parameters'])
    # Never accept caller-supplied URLs/base64 that bypass project snapshots.
    if any(k in payload for k in ('ImageUrl', 'ImageBase64', 'MultiViewImages')):
        raise ValueError('图片必须通过项目 inputs 快照传入')
    encoded_total = 0
    for view, _, item in rows:
        if not isinstance(item, dict) or 'snapshot' not in item:
            raise ValueError('生成前须先保存图片快照')
        path = Path(item['snapshot'])
        kind = path.suffix.lower().lstrip('.')
        kind = 'jpeg' if kind == 'jpg' else kind
        if kind not in (('png', 'jpeg') if len(rows) > 1 else ('png', 'jpeg', 'webp')):
            raise ValueError('多视图仅接受 PNG/JPEG，单图还支持 WebP')
        if not 0 < path.stat().st_size <= 6 * 1024**2:
            raise ValueError('单张图片须小于或等于 6 MiB')
        data = path.read_bytes()
        if item.get('sha256') and hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Input image changed after the generation request was prepared')
        width, height = image_size(data, kind)
        if not all(128 < n < 5000 for n in (width, height)):
            raise ValueError('图片每边尺寸须大于 128 且小于 5000')
        encoded = base64.b64encode(data).decode('ascii')
        encoded_total += len(encoded)
        if encoded_total > MAX_ENCODED:
            raise ValueError('全部图片 Base64 编码后总和不可超过 8 MiB；请先显式准备较小输入')
        if view == 'front':
            payload['ImageBase64'] = encoded
        else:
            payload.setdefault('MultiViewImages', []).append({'ViewType': view, 'ViewImageBase64': encoded})
    return payload


def summary(request):
    rows = views(request)
    return {'mode': 'multiview' if len(rows) > 1 else 'image' if rows else 'text',
            'prompt_sent': 'Prompt' in request['parameters'],
            'images': [{'view': view, 'path': path,
                        'field': 'ImageBase64' if view == 'front' else 'MultiViewImages.ViewImageBase64',
                        **({'sha256': item['sha256']} if isinstance(item, dict) and 'sha256' in item else {})}
                       for view, path, item in rows],
            'brief_sent': False}
