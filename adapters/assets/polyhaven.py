"""Read-only Poly Haven catalogue API; retain attribution and variant dependencies."""
import re
from . import http_io

BASE = 'https://api.polyhaven.com'
TYPES = {'hdri': 0, 'texture': 1, '3d': 2}


def search(query='', kind=None, limit=20):
    if kind is not None and kind not in TYPES:
        raise ValueError('Poly Haven supports 3d, texture and hdri')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('limit must be 1..100')
    catalogue = http_io.json_request(BASE + '/assets')
    terms = query.casefold().split()
    results = []
    for asset_id, item in catalogue.items():
        if not isinstance(item, dict) or (kind and item.get('type') != TYPES[kind]):
            continue
        words = ' '.join(str(item.get(k, '')) for k in ('name', 'description', 'tags', 'categories')).casefold()
        if not all(term in words or term in asset_id.casefold() for term in terms):
            continue
        results.append({'asset_id': asset_id, 'title': item.get('name', asset_id),
                        'source': 'Poly Haven', 'source_url': 'https://polyhaven.com/a/' + asset_id,
                        'authors': item.get('authors', {}), 'type': item.get('type'),
                        'license': 'CC0', 'thumbnail_url': item.get('thumbnail_url'),
                        'files_hash': item.get('files_hash')})
    return {'source': 'Poly Haven', 'results_are_assets': True, 'total_matches': len(results),
            'assets': results[:limit], 'license_url': 'https://polyhaven.com/license',
            'api_terms': 'https://polyhaven.com/our-api'}


def files(asset_id):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,150}', asset_id):
        raise ValueError('Invalid Poly Haven asset ID')
    return {'source': 'Poly Haven', 'asset_id': asset_id,
            'source_url': 'https://polyhaven.com/a/' + asset_id,
            'variants': http_io.json_request(BASE + '/files/' + asset_id),
            'note': 'Select a format/resolution and retain all include dependencies with their relative paths.'}
