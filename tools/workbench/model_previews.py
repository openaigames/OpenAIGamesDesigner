"""Validate engine-exported preview copies without treating them as source assets."""
import json
from . import art_registry


def read(root):
    path = root / '.asset-browser/previews.json'
    if not path.exists():
        return {}, None
    try:
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('预览映射路径或大小无效')
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('assets'), dict):
            raise ValueError('预览映射格式无效')
        return value['assets'], None
    except (OSError, ValueError) as error:
        return {}, str(error)


def resolve(root, source, record, info):
    try:
        if not isinstance(record, dict):
            raise ValueError('预览映射格式无效')
        target = record.get('path')
        preview = art_registry.asset_path(root, target)
        original = art_registry.asset_path(root, source)
        if preview == original or preview.suffix.lower() != '.glb':
            raise ValueError('关联预览须为独立 GLB 文件')
        if not preview.is_file():
            raise ValueError('预览文件不存在，请重新导出')
        if art_registry.digest(original) != record.get('source_sha256'):
            raise ValueError('原模型已变化，请重新导出预览')
        if art_registry.digest(preview) != record.get('sha256'):
            raise ValueError('预览文件已变化，请重新导出或核对版本')
        dependencies = record.get('dependencies', {})
        if not isinstance(dependencies, dict) or len(dependencies) > 4096:
            raise ValueError('预览依赖清单无效')
        for relative, expected in dependencies.items():
            dependency = art_registry.asset_path(root, relative)
            if not dependency.is_file() or art_registry.digest(dependency) != expected:
                raise ValueError('模型依赖已变化或丢失，请重新导出预览')
        metadata = info(preview)
        if not metadata or metadata.get('parseError') or not metadata.get('meshes'):
            raise ValueError('预览不是可读取的 GLB 模型')
        return {'kind': 'model', 'preview': 'derived', 'previewPath': target, 'previewExt': 'GLB',
                'previewNote': str(record.get('note', '引擎导出的关联预览'))[:400], **metadata}
    except (OSError, ValueError, TypeError):
        # A stale preview must never appear to be the current source version.
        return {'preview': 'unavailable', 'previewIssue': '关联预览已过期、缺失或无效，请从引擎重新导出。'}
