"""Measured image evidence. Semantic identity and symmetry still need review."""
import math
import warnings


def imaging():
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageOps
    except ImportError as exc:
        raise ValueError('Image evidence needs Pillow in the Python environment running this tool') from exc
    return Image, ImageChops, ImageDraw, ImageOps


def decode(path):
    Image, _, _, _ = imaging()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as source:
                if source.format not in ('PNG', 'JPEG', 'WEBP') or source.n_frames != 1:
                    raise ValueError('Use a single PNG, JPEG or WebP frame')
                if source.width * source.height > 16_000_000:
                    raise ValueError('Evidence image exceeds 16 million pixels')
                if source.getexif().get(274, 1) != 1:
                    raise ValueError('Normalize EXIF orientation before defining coordinates')
                source.load()
                return source.convert('RGBA')
    except (OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError('Cannot decode evidence image: ' + str(path)) from exc


def measure(root, view, path_fn):
    image = decode(path_fn(root, view['path']))
    mask = None
    segmentation = view.get('segmentation', {})
    if segmentation.get('alpha'):
        channel = image.getchannel('A')
        # Fully opaque images provide no foreground boundary.
        if channel.getextrema()[0] < 255:
            mask = channel.point(lambda x: 255 if x >= 128 else 0)
    elif segmentation.get('mask'):
        original = decode(path_fn(root, segmentation['mask']))
        if original.size != image.size:
            raise ValueError('Mask dimensions differ from image: ' + view['id'])
        mask = original.convert('L').point(lambda x: 255 if x >= 128 else 0)
    box = mask.getbbox() if mask else None
    metrics = {'size': list(image.size), 'foreground_box': list(box) if box else None,
               'segmentation': 'measured' if box else 'unknown'}
    if box:
        metrics['height_px'] = box[3] - box[1]
        metrics['bottom_y'] = box[3]
        metrics['touches_border'] = box[0] == 0 or box[1] == 0 or box[2] == image.width or box[3] == image.height
    return image, mask, metrics


def comparable(a, b):
    ca, cb = a.get('calibration', {}), b.get('calibration', {})
    return (a['projection'] == b['projection'] == 'orthographic'
            and ca.get('group') and ca.get('group') == cb.get('group')
            and ca.get('pixels_per_unit', 0) > 0 and cb.get('pixels_per_unit', 0) > 0)


def compare(check, views, measurements):
    a, b = views[check['a']], views[check['b']]
    _, ma, xa = measurements[a['id']]
    _, mb, xb = measurements[b['id']]
    result = {'id': check['id'], 'metric': check['metric'], 'priority': check['priority'],
              'evidence': [a['id'], b['id']], 'status': 'unknown', 'value': None,
              'tolerance': check['tolerance'], 'reason': ''}
    if not comparable(a, b):
        result['reason'] = 'Requires declared orthographic calibration in a shared group and pose'
        return result
    ca, cb = a['calibration'], b['calibration']
    metric = check['metric']
    if metric == 'landmark_height':
        la, lb = a.get('landmarks', {}).get(check['landmark']), b.get('landmarks', {}).get(check['landmark'])
        if not la or not lb or la['visibility'] != 'visible' or lb['visibility'] != 'visible':
            result['reason'] = 'Landmark is absent, occluded or unverified'
            return result
        # y is a normalized edge coordinate; baseline is in image pixels.
        value = abs((ca['baseline_y'] - la['y'] * xa['size'][1]) / ca['pixels_per_unit']
                    - (cb['baseline_y'] - lb['y'] * xb['size'][1]) / cb['pixels_per_unit'])
    else:
        if ma is None or mb is None or not xa['foreground_box'] or not xb['foreground_box']:
            result['reason'] = 'Foreground needs usable alpha or an explicit mask'
            return result
        if xa['touches_border'] or xb['touches_border']:
            result['reason'] = 'Foreground touches the frame; a complete silhouette is not established'
            return result
        if metric == 'height':
            ha = xa['height_px'] / ca['pixels_per_unit']
            hb = xb['height_px'] / cb['pixels_per_unit']
            value = abs(ha - hb) / max(ha, hb)
        elif metric == 'baseline':
            value = abs((ca['baseline_y'] - xa['bottom_y']) / ca['pixels_per_unit']
                        - (cb['baseline_y'] - xb['bottom_y']) / cb['pixels_per_unit'])
        else:
            if (a['direction'] != b['direction'] or xa['size'] != xb['size']
                    or ca != cb):
                result['reason'] = 'Silhouette IoU requires the same direction, canvas, scale and baseline'
                return result
            _, ImageChops, _, _ = imaging()
            union = ImageChops.lighter(ma, mb).histogram()[255]
            overlap = ImageChops.darker(ma, mb).histogram()[255]
            value = overlap / union if union else 0
    result.update(value=round(value, 6), status='pass' if (
        value >= check['tolerance'] if metric == 'silhouette_iou' else value <= check['tolerance']) else 'fail',
        reason='Measured using declared calibration; calibration accuracy remains a review responsibility')
    return result


def findings(plan, views, measurements):
    _, ImageChops, _, ImageOps = imaging()
    result = []
    for required in plan.get('required_views', []):
        actual = {v['direction'] for v in views.values() if v['set'] == required['set']}
        for direction in required['directions']:
            if direction not in actual:
                result.append({'id': 'missing:' + required['set'] + ':' + direction,
                               'kind': 'missing_view', 'evidence': [], 'reason': 'Required direction has no image'})
    rows = list(views.values())
    for i, a in enumerate(rows):
        ia = measurements[a['id']][0]
        for b in rows[i+1:]:
            if a['set'] != b['set'] or a['direction'] == b['direction']:
                continue
            ib = measurements[b['id']][0]
            if ia.size != ib.size:
                continue
            def same(x, y):
                return all(c.getbbox() is None for c in ImageChops.difference(x, y).split())
            kind = 'duplicate' if same(ia, ib) else 'mirror' if same(ia, ImageOps.mirror(ib)) else None
            if kind:
                result.append({'id': kind + ':' + a['id'] + ':' + b['id'], 'kind': kind,
                               'evidence': [a['id'], b['id']],
                               'reason': 'Pixel match is a review cue; symmetric objects can legitimately match'})
    return result


def contact_sheet(views, measurements, destination):
    Image, _, ImageDraw, _ = imaging()
    columns, cell_w, cell_h = 3, 300, 330
    sheet = Image.new('RGB', (columns * cell_w, math.ceil(len(views) / columns) * cell_h), '#292d34')
    draw = ImageDraw.Draw(sheet)
    for i, view in enumerate(views.values()):
        frame = measurements[view['id']][0].copy()
        frame.thumbnail((280, 280))
        x, y = i % columns * cell_w, i // columns * cell_h
        sheet.paste(frame, (x + (cell_w - frame.width)//2, y + 30 + (280-frame.height)//2), frame)
        draw.text((x + 10, y + 8), view['id'] + ' / ' + view['direction'], fill='white')
    sheet.save(destination)
