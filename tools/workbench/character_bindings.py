"""Read explicit engine character/action bindings; folder presence is not a binding."""
import json
from . import art_registry
from content_roots import in_game


def read(root, assets):
    path = root / '.asset-browser' / 'characters.json'
    if not path.exists():
        return [], None
    try:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('角色绑定清单路径或大小无效')
        data = json.loads(path.read_text('utf-8-sig'))
        if data.get('version') != 1 or not isinstance(data.get('characters'), list) or len(data['characters']) > 200:
            raise ValueError('角色绑定清单格式无效')
        legacy_dependencies = data.get('dependencies', {})
        known = {a['path']: a for a in assets}
        result, ids, errors = [], set(), []
        for row in data['characters']:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in ids:
                raise ValueError('角色 ID 无效或重复')
            ids.add(row['id'])
            try:
                dependencies = row.get('dependencies', legacy_dependencies)
                if not isinstance(dependencies, dict) or not dependencies or len(dependencies) > 4096:
                    raise ValueError('角色绑定缺少版本依据')
                for rel, expected in dependencies.items():
                    target = art_registry.asset_path(root, rel)
                    if not target.is_file() or art_registry.digest(target) != expected:
                        raise ValueError('角色绑定文件已变化，请重新从引擎同步：' + rel)
                model = row.get('model')
                if model not in known or model not in dependencies or not in_game(model, root):
                    raise ValueError('角色模型须关联游戏内容目录内的实际文件与版本')
                actions = row.get('actions')
                if not isinstance(actions, list) or len(actions) > 200:
                    raise ValueError('角色动作列表无效')
                for action in actions:
                    if not isinstance(action, dict) or not isinstance(action.get('label'), str) or not action['label'].strip():
                        raise ValueError('角色动作名称无效')
                    rel = action.get('path')
                    if rel not in known or rel not in dependencies or not in_game(rel, root):
                        raise ValueError('角色动作须关联游戏内容目录内的实际文件与版本')
                result.append({'id': row['id'][:100], 'title': str(row.get('title', known[model]['title']))[:150],
                               'role': row.get('role') if row.get('role') in ('player', 'boss', 'shared') else 'shared',
                               'model': model, 'actions': [{'label': a['label'][:150], 'path': a['path'], 'basis': str(a.get('basis','explicit_manifest'))[:200]} for a in actions],
                               'consumer': str(row.get('consumer',''))[:1000], 'session': str(row.get('session',''))[:1000], 'note': str(row.get('note', ''))[:1000]})
            except (OSError,ValueError,KeyError,TypeError) as error:
                errors.append(row['id'] + ': ' + str(error))
        return result, '; '.join(errors) or None
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [], str(exc)
