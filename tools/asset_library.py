#!/usr/bin/env python3
"""Asset source discovery, bounded acquisition and a project-local asset register."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.assets import http_io
from adapters.assets import polyhaven
from urllib.parse import urlsplit, urlunsplit
from adapters.assets.archive_io import relative_path, extract_zip
from game_workflow import atomic_json, now, sha
from validate_records import contained, check_record

CATALOG = Path(__file__).resolve().parents[1] / 'adapters/assets/sources.json'
KINDS = ('2d', '3d', 'ui', 'texture', 'hdri', 'vfx', 'animation', 'audio', 'font', 'module')


def sources(kind=None, query='', catalog=CATALOG, *, access=None, login=None):
    if access not in (None, 'direct', 'user-step') or login not in (None, 'none', 'required', 'conditional', 'unknown'):
        raise ValueError('Unsupported source access or login filter')
    data = json.loads(catalog.read_text(encoding='utf-8'))
    def matches(entry):
        route = entry.get('download', {})
        if kind and kind not in entry['kinds']:
            return False
        if login and route.get('login', 'unknown') != login:
            return False
        if access and route.get('mode') != access:
            return False
        if access == 'direct':
            evidence = entry.get('verification', {})
            # A free badge or anonymous webpage is not a tested file transfer.
            if route.get('login') != 'none' or evidence.get('status') != 'sample_download_passed' or not evidence.get('files'):
                return False
        return True
    entries = [entry for entry in data['sources'] if matches(entry)]
    return {'status': 'search_plan', 'results_are_assets': False,
            'catalog_checked_at': data.get('checked_at'),
            'verification_scope': data.get('verification_policy', 'Source metadata only; verify the selected asset before acquisition.'),
            'sources': [{**entry, 'search_query': f'site:{entry["domain"]} {query} {kind or "game assets"}'.strip()}
                        for entry in entries]}


def file_record(root, path):
    return {'path': path.relative_to(root).as_posix(), 'sha256': sha(path), 'bytes': path.stat().st_size}


def metadata(request):
    for key in ('title', 'source_url', 'author'):
        if not isinstance(request.get(key), str) or not request[key].strip():
            raise ValueError('Asset request requires title, source_url and author (unknown is allowed)')
    if not request['source_url'].startswith('https://'):
        raise ValueError('source_url must identify the original HTTPS asset page')
    if request.get('kind') not in KINDS:
        raise ValueError('Unsupported asset kind')
    license_info = request.get('license')
    if not isinstance(license_info, dict) or not isinstance(license_info.get('name'), str):
        raise ValueError('Record license.name; use unknown if it has not been checked')
    if license_info.get('status', 'unverified') not in ('unverified', 'reviewed'):
        raise ValueError('license.status must be unverified or reviewed')
    if license_info.get('status') == 'reviewed' and not license_info.get('evidence_files'):
        raise ValueError('Reviewed licensing requires project-local evidence_files')
    return {key: request[key] for key in ('title', 'source_url', 'author', 'kind', 'license')} | {
        'source_id': request.get('source_id', 'custom'), 'version': request.get('version', 'unspecified'),
        'notes': request.get('notes', '')}


def records(root):
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(root.glob('.openaigame/asset-library/*/record.json'))]


def check_files(root, record):
    return check_record('asset-library', record, root,
                        root / '.openaigame/asset-library' / record['asset_id'] / 'record.json')


def acquire(root, request, job=None):
    info = metadata(request)
    requested = request.get('files', [])
    if job is None and (not isinstance(requested, list) or not requested):
        raise ValueError('Acquisition requires files with name and url or local')
    max_bytes = request.get('max_download_bytes', 1024**3)
    if type(max_bytes) is not int or not 1 <= max_bytes <= 8 * 1024**3:
        raise ValueError('Invalid max_download_bytes')
    seen = set()
    for entry in requested:
        name = relative_path(entry['name'])
        key = str(name).casefold()
        if key in seen or ('url' in entry) == ('local' in entry):
            raise ValueError('Duplicate filenames or ambiguous file source')
        seen.add(key)
        if 'local' in entry:
            if not contained(root, entry['local']).is_file():
                raise ValueError('Missing local asset')
    evidence = []
    for name in info['license'].get('evidence_files', []):
        path = contained(root, name)
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing license evidence')
        evidence.append(path)
    identity = hashlib.sha256(json.dumps({'request': request, 'job': job and job['job_id'],
        'evidence': [sha(p) for p in evidence],
        'local_inputs': [sha(contained(root, e['local'])) for e in requested if 'local' in e]}, sort_keys=True).encode()).hexdigest()
    for record in records(root):
        if record.get('request_sha256') == identity and record.get('status') == 'acquired' and not check_files(root, record):
            return {**record, 'reused': True}
    asset_id = 'AS' + uuid.uuid4().hex
    ledger = contained(root, '.openaigame/asset-library/' + asset_id)
    ledger.mkdir(parents=True)
    target_root = contained(root, 'assets-source/' + asset_id)
    record = {'schema_version': 1, 'asset_id': asset_id, 'created_at': now(), **info,
              'request_sha256': identity, 'method': 'generated' if job else 'external', 'status': 'acquiring',
              'files': [], 'license_evidence': [], 'quality_validation': 'not_checked', 'engine_import': 'not_run'}
    atomic_json(ledger / 'record.json', record)
    try:
        record['origins'] = []
        for entry in requested:
            origin = {'name': entry['name']}
            if 'url' in entry:
                parts = urlsplit(entry['url'])
                origin['url_without_query'] = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
            else:
                origin['local'] = entry['local']
                origin['sha256'] = sha(contained(root, entry['local']))
            record['origins'].append(origin)
        for index, path in enumerate(evidence):
            saved = ledger / 'license' / (str(index) + '-' + path.name)
            saved.parent.mkdir(exist_ok=True)
            shutil.copy2(path, saved)
            record['license_evidence'].append(file_record(root, saved))
        if job:
            if job['status'] not in ('succeeded', 'registered') or not job['artifacts']:
                raise ValueError('Generation must have registered outputs')
            for artifact in job['artifacts']:
                path = contained(root, artifact['path'])
                if not path.is_file() or sha(path) != artifact['sha256']:
                    raise ValueError('Generated artifact changed or is missing')
                record['files'].append(file_record(root, path))
            record['generation'] = {'job_id': job['job_id'], 'provider': job['provider'],
                                    'provider_job_id': job.get('provider_job_id'),
                                    'record': '.openaigame/asset-jobs/' + job['job_id'] + '/job.json'}
        else:
            target_root.mkdir(parents=True)
            for entry in requested:
                target = contained(target_root, str(relative_path(entry['name'])))
                target.parent.mkdir(parents=True, exist_ok=True)
                if 'url' in entry:
                    http_io.download(entry['url'], target, max_bytes, entry.get('sha256'))
                else:
                    source = contained(root, entry['local'])
                    if not 0 < source.stat().st_size <= max_bytes:
                        raise ValueError('Local asset is empty or exceeds size limit')
                    if entry.get('sha256') and sha(source) != entry['sha256']:
                        raise ValueError('Local asset hash mismatch')
                    shutil.copy2(source, target)
                record['files'].append(file_record(root, target))
                if entry.get('extract'):
                    if target.suffix.lower() != '.zip':
                        raise ValueError('Only ZIP extraction is supported; preserve other packages for their native importer')
                    for path in extract_zip(target, target.with_name(target.name + '.contents'), max_bytes):
                        record['files'].append(file_record(root, path))
                atomic_json(ledger / 'record.json', record)
        record['status'] = 'acquired'
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        record['status'] = 'failed'
        record['notes'] = 'Acquisition incomplete; inspect retained files and original source. No import or quality success claimed.'
        atomic_json(ledger / 'record.json', record)
        raise
    atomic_json(ledger / 'record.json', record)
    return record


def index(root, out):
    target = contained(root, out)
    if target.exists():
        raise ValueError('Choose a new index path; do not overwrite authored design documents')
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
    lines = ['# 资产登记索引', '', '| ID | 名称 | 类型 | 来源 | 许可 | 获取状态 | 记录 |', '| --- | --- | --- | --- | --- | --- | --- |']
    for row in records(root):
        link = '.openaigame/asset-library/' + row['asset_id'] + '/record.json'
        lines.append('| ' + ' | '.join(cell(v) for v in [row['asset_id'], row['title'], row['kind'], row['source_url'], row['license']['name'], row['status'], link]) + ' |')
    lines += ['', '路径相对游戏项目根。登记仅证明文件获取；引擎导入、质量与许可适用范围需分别核实。', '']
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(lines), encoding='utf-8')
    return {'path': target.relative_to(root).as_posix(), 'assets': len(records(root))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    discover = sub.add_parser('sources', help='Prepare source search queries for the host browser/search tool; not live results')
    discover.add_argument('--kind', choices=KINDS)
    discover.add_argument('--query', default='')
    discover.add_argument('--access', choices=('direct', 'user-step'),
                          help='Filter verified anonymous sample downloads or sources needing extra steps')
    discover.add_argument('--login', choices=('none', 'required', 'conditional', 'unknown'),
                          help='Account requirement, separate from browser/tool steps')
    search = sub.add_parser('search', help='Search live Poly Haven assets')
    search.add_argument('--query', default='')
    search.add_argument('--kind', choices=tuple(polyhaven.TYPES))
    search.add_argument('--limit', type=int, default=20)
    variants = sub.add_parser('files', help='List live Poly Haven file variants and dependencies')
    variants.add_argument('--asset', required=True)
    for name in ('acquire', 'from-job'):
        command = sub.add_parser(name)
        command.add_argument('--request', required=True)
        if name == 'from-job': command.add_argument('--job', required=True)
    listing = sub.add_parser('list')
    listing.add_argument('--query', default='')
    sub.add_parser('verify')
    export = sub.add_parser('index')
    export.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'sources':
            result = sources(args.kind, args.query, access=args.access, login=args.login)
        elif args.action == 'search':
            result = polyhaven.search(args.query, args.kind, args.limit)
        elif args.action == 'files':
            result = polyhaven.files(args.asset)
        else:
            if args.project is None or not args.project.is_dir():
                raise ValueError('Select an existing game project')
            root = args.project.resolve()
            if args.action in ('acquire', 'from-job'):
                request = json.loads(contained(root, args.request).read_text(encoding='utf-8-sig'))
                job = None
                if args.action == 'from-job':
                    from asset_workflow import read_job
                    _, job = read_job(root, args.job)
                result = acquire(root, request, job)
            elif args.action == 'list':
                result = [r for r in records(root) if args.query.casefold() in (r['title'] + ' ' + r['kind']).casefold()]
            elif args.action == 'verify':
                result = [{'asset_id': r['asset_id'], 'errors': check_files(root, r)} for r in records(root)]
            else:
                result = index(root, args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.action == 'verify' and any(r['errors'] for r in result) else 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        print(json.dumps({'error': 'Asset operation failed. Check request fields, source access, filenames and retained acquisition records.'}))
        return 2


if __name__ == '__main__':
    # JSON includes localized catalog text; redirected Windows stdout may use a legacy code page.
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
