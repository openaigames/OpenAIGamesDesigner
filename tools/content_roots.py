"""One definition of game content ownership for scans, bindings and previews."""
from pathlib import Path
from record_io import local, read_json

GENERATED = {'.git','.godot','.openaigame','.asset-browser','__pycache__','node_modules',
             'library','temp','logs','binaries','intermediate','saved','deriveddatacache',
             'build','builds','dist','bin','obj'}
PROJECT_RECORDS = {'assets-source','source-assets','design','production','tests','tools','docs','runs','previews'}


def layout(root):
    root = Path(root).resolve()
    config_path = local(root,'.openaigame/project.json')
    if not config_path.exists():
        return {'roots':['game'], 'excluded':[], 'mode':'legacy-game-directory', 'engine':None,
                'reason':'未配置工程，沿用默认 game 目录归属；目录内不代表已绑定或品质通过。'}
    try:
        config = read_json(config_path)
        engine_root = config['engine_root']
        engine = config['engine']
        base = local(root,engine_root)
        if engine not in {'godot','unity','unreal','threejs','phaser'}:
            raise ValueError('未知引擎')
        declared = config.get('content_roots')
        if declared is not None:
            if not isinstance(declared,list) or not declared:
                raise ValueError('content_roots 必须是非空项目相对目录列表')
            roots = [local(root,item) for item in declared]
            if any(not p.is_relative_to(base) for p in roots):
                raise ValueError('内容根必须属于已配置工程')
        elif engine == 'unreal':
            roots = [base/'Content']
            plugins = base/'Plugins'
            if plugins.exists():
                roots.extend(p.resolve() for p in plugins.rglob('Content') if p.is_dir() and p.resolve().is_relative_to(base))
        elif engine == 'unity':
            roots = [base/'Assets']
        else:
            roots = [base]
        exclusions = config.get('asset_exclude_roots', [])
        if not isinstance(exclusions,list):
            raise ValueError('asset_exclude_roots 必须为项目相对目录列表')
        excluded = [local(root,item) for item in exclusions]
        return {'roots':[p.relative_to(root).as_posix() for p in roots],
                'excluded':[p.relative_to(root).as_posix() for p in excluded],
                'mode':'configured','engine':engine,'engine_root':engine_root,
                'reason':'依据工程配置和实际内容目录；目录内不代表已绑定或品质通过。'}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'roots':[], 'excluded':[], 'mode':'invalid', 'engine':None,
                'reason':'工程资产归属无法确认：'+str(error)}


def classify(root, relative, configured=None):
    result = {'location':'candidate','reason':''}
    try:
        root = Path(root).resolve()
        path = local(root,relative)
        parts = tuple(p.casefold() for p in path.relative_to(root).parts)
        config = configured if configured is not None else layout(root)
        if config['mode'] == 'invalid':
            result['reason'] = config['reason']
            return result
        if set(parts) & GENERATED:
            result['reason'] = '缓存、构建或派生预览不归为游戏源资产。'
            return result
        if any(path.is_relative_to(local(root,p)) for p in config['excluded']):
            result['reason'] = '项目明确排除的源素材或辅助目录。'
            return result
        matches = []
        for relative_root in config['roots']:
            content = local(root,relative_root)
            # Windows path comparison already follows the host's case rules.
            if path.is_relative_to(content):
                nested = path.relative_to(content).parts
                if nested and nested[0].casefold() in PROJECT_RECORDS:
                    continue
                matches.append(relative_root)
        if matches:
            result.update(location='game',reason=config['reason'],contentRoot=max(matches,key=len))
        else:
            result['reason'] = '文件位于配置的游戏内容目录之外。'
    except (OSError, ValueError, TypeError) as error:
        result['reason'] = '资产路径无法归类：'+str(error)
    return result


def in_game(relative, root=None):
    if root is not None:
        return classify(root,relative)['location'] == 'game'
    # Preserve the old helper's source API; all project operations pass a root.
    return (isinstance(relative,str) and '..' not in relative.replace('\\','/').split('/')
            and relative.replace('\\','/').split('/')[0].casefold() == 'game')
