"""Build a portable, version-checked selection without modifying either game project."""
import json
from pathlib import Path
import shutil
import struct
from urllib.parse import unquote, urlparse
from .common import digest, inside, issue, issues_report, unique, write


def gltf_document(path):
    path = Path(path)
    if path.suffix.lower() == '.gltf':
        return json.loads(path.read_text(encoding='utf-8-sig'))
    with path.open('rb') as stream:
        header = stream.read(12)
        if len(header) != 12:
            raise ValueError('Truncated GLB')
        magic, version, length = struct.unpack('<4sII', header)
        if magic != b'glTF' or version != 2 or length != path.stat().st_size:
            raise ValueError('Invalid GLB header')
        chunk = stream.read(8)
        if len(chunk) != 8:
            raise ValueError('Missing GLB JSON')
        size, kind = struct.unpack('<II', chunk)
        if kind != 0x4E4F534A or size > length-20:
            raise ValueError('Invalid GLB JSON chunk')
        return json.loads(stream.read(size).decode('utf8'))


def dependencies(path, root):
    doc = gltf_document(path)
    found = []
    for item in doc.get('buffers', [])+doc.get('images', []):
        uri = item.get('uri', '')
        if not uri or uri.startswith('data:'):
            continue
        if urlparse(uri).scheme or uri.startswith(('/', '\\')):
            raise ValueError('External network or absolute glTF dependency is not portable')
        candidate = (Path(path).parent/unquote(uri)).resolve()
        if not candidate.is_relative_to(Path(root).resolve()):
            raise ValueError('glTF dependency escapes project')
        found.append(candidate.relative_to(Path(root).resolve()).as_posix())
    return found


def build(plan, root, output=None):
    if plan.get('schema') != 'environment-handoff/1':
        raise ValueError('Expected environment-handoff/1')
    for key in ('revision', 'selection_source', 'selection_sha256', 'coordinate', 'unit', 'target_engine'):
        if not plan.get(key):
            raise ValueError('Handoff requires '+key)
    authority = inside(root, plan['selection_source'])
    if digest(authority) != plan['selection_sha256']:
        raise ValueError('Selection record changed; refresh the current handoff')
    entries = unique(plan['files'])
    paths, issues = {}, []
    for name, item in entries.items():
        path = inside(root, item['path'])
        current = digest(path)
        if item.get('sha256') != current:
            raise ValueError('Selected file changed or lacks identity: '+item['path'])
        if not item.get('role') or item.get('transfer') not in ('portable', 'rebuild', 'reference', 'unknown'):
            raise ValueError('Each file needs a role and explicit transfer disposition')
        if item['path'] in paths:
            raise ValueError('Duplicate handoff path')
        paths[item['path']] = {**item, 'sha256':current}
        if item['transfer'] in ('rebuild', 'unknown'):
            issues.append(issue('target_work_remaining', 'warning', asset=name, transfer=item['transfer'], reason=item.get('note', '')))
        if item['transfer'] == 'rebuild' and not item.get('note'):
            raise ValueError('Describe what must be rebuilt')
    paths.setdefault(plan['selection_source'], {'id':'selection_record', 'path':plan['selection_source'],
                     'sha256':plan['selection_sha256'], 'role':'selection', 'transfer':'reference'})
    pending = list(paths)
    while pending:
        relative = pending.pop()
        item = paths[relative]
        deps = list(item.get('depends_on', []))
        if Path(relative).suffix.lower() in ('.gltf', '.glb'):
            deps += dependencies(inside(root, relative), root)
        for dep in deps:
            if dep not in paths:
                file = inside(root, dep)
                paths[dep] = {'id':'dependency:'+dep, 'path':dep, 'sha256':digest(file),
                              'role':'dependency', 'transfer':'portable', 'required_by':[relative]}
                pending.append(dep)
    result = issues_report('environment-handoff-report', issues, revision=plan['revision'],
                           target_engine=plan['target_engine'], coordinate=plan['coordinate'], unit=plan['unit'],
                           files=list(paths.values()), target_engine_validation='not_run',
                           note='Packaging and dependency checks do not prove target-engine appearance, collision or performance.')
    if output is not None:
        output = Path(output).resolve()
        if output == Path(root).resolve() or Path(root).resolve().is_relative_to(output):
            raise ValueError('Output cannot contain the source project')
        output.mkdir(parents=True, exist_ok=False)
        for relative, item in paths.items():
            dest = inside(output, relative, exists=False)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(inside(root, relative), dest)
            if digest(dest) != item['sha256']:
                raise ValueError('Copy changed during packaging: '+relative)
        write(output/'handoff-report.json', result)
        lines = ['地图交接', '版本：'+str(plan['revision']), '目标引擎：'+str(plan['target_engine']),
                 '单位：'+str(plan['unit']), '坐标：'+str(plan['coordinate']),
                 '', '目标引擎运行、画面、碰撞和性能尚未由打包工具验证。', '', '文件与处理方式：']
        for item in paths.values():
            lines.append(item['path']+' | '+item['role']+' | '+item['transfer']+' | '+item.get('note',''))
        lines += ['', '接入后核对单位、朝向、轮廓、材质、碰撞、机位和实际通行；记录当前引擎版本与真实证据。']
        (output/'交接说明.txt').write_text('\n'.join(lines), encoding='utf8')
    return result
