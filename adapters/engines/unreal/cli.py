"""Unreal project inspection, Automation tests, UBT and UAT execution."""
import json
from .reports import normalize_tests
from pathlib import Path
from ..common import binary, configured
from ..native_support import settings, required, token, file_path, evidence

def project_file(config, project):
    relative = config.get("project_file", "")
    path = (project / relative).resolve()
    if not relative or not path.is_relative_to(project.resolve()) or path.suffix != ".uproject" or not path.is_file():
        raise ValueError("project_file must identify a .uproject inside engine_root")
    return path

def inspect(config, project):
    binary(config)
    path = project_file(config, project)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict): raise ValueError("uproject metadata must be an object")
    return {"engine": "unreal", "project_version": str(data.get("EngineAssociation", "")),
            "version_source": str(path), "editor_version_verified": False}

def command(config, project, action, run, output):
    path = project_file(config, project)
    if action in config.get("commands", {}):
        return configured(config, action, project, run, output)
    if action == "play":
        return [str(binary(config)), str(path), "-game", "-log"]
    opts = settings(config, 'unreal')
    editor = binary(config)
    cmd_editor = editor.with_name('UnrealEditor-Cmd.exe') if editor.suffix.lower() == '.exe' else editor
    if not cmd_editor.is_file():
        raise ValueError('UnrealEditor-Cmd is missing beside editor_executable')
    base = [str(cmd_editor), str(path)]
    flags = ['-unattended', '-nop4', '-nosplash', f'-abslog={run / "editor.log"}']
    if action == 'prepare':
        # No map/Actor writes: the script only records the actually loaded project.
        return base + ['-run=pythonscript', '-EnablePlugins=PythonScriptPlugin',
                       f'-script={Path(__file__).with_name("inspect_project.py")}',
                       f'-OAGDReport={run / "unreal-result.json"}'] + flags
    if action == 'smoke':
        scene = map_name(required(opts, 'smoke_map'))
        seconds = opts.get('smoke_seconds', 3)
        if type(seconds) not in (float, int) or not 1 <= seconds <= 60:
            raise ValueError('unreal.smoke_seconds must be 1..60')
        return base + [scene, '-game', f'-seconds={seconds}', '-NullRHI', '-nosound'] + flags
    if action == 'test':
        selected = token(required(opts, 'test_filter'), 'test_filter', r'[A-Za-z0-9_ ./-]+')
        return base + [f'-ExecCmds=Automation RunTests {selected}',
                       '-TestExit=Automation Test Queue Empty',
                       f'-ReportOutputPath={run / "automation"}', '-NullRHI', '-nosound'] + flags
    if action in {'build', 'export'}:
        dotnet = file_path(required(opts, 'dotnet_executable'), 'unreal.dotnet_executable')
        engine = editor.parents[2]
        platform = token(required(opts, 'platform'), 'platform', r'[A-Za-z0-9_]+')
        configuration = opts.get('configuration', 'Development')
        if configuration not in {'Debug', 'DebugGame', 'Development', 'Test', 'Shipping'}:
            raise ValueError('Invalid Unreal configuration')
        if action == 'build':
            target = token(required(opts, 'build_target'), 'build_target', r'[A-Za-z0-9_]+')
            dll = file_path(str(engine / 'Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll'), 'UnrealBuildTool')
            return [str(dotnet), str(dll), target, platform, configuration,
                    f'-Project={path}', '-WaitMutex', '-NoHotReloadFromIDE']
        maps = opts.get('export_maps')
        if not isinstance(maps, list) or not maps:
            raise ValueError('unreal.export_maps must list explicitly selected maps')
        maps = [map_name(m) for m in maps]
        dll = file_path(str(engine / 'Binaries/DotNET/AutomationTool/AutomationTool.dll'), 'AutomationTool')
        return [str(dotnet), str(dll), 'BuildCookRun', f'-project={path}',
                '-noP4', '-unattended', '-utf8output', '-build', '-cook', '-stage', '-pak', '-archive',
                f'-platform={platform}', f'-clientconfig={configuration}',
                f'-map={"+".join(maps)}', f'-archivedirectory={output}']
    raise ValueError(f'Unsupported Unreal action: {action}')


def map_name(value):
    value = token(value, 'map package', r'/[A-Za-z0-9_/-]+')
    if value.count('/') < 2 or '//' in value or value.endswith('/'):
        raise ValueError('Map must be a package path such as /Game/Maps/Test')
    return value


def finalize(config, project, action, run, output):
    if action in config.get('commands', {}):
        return {}
    if action == 'test':
        return {'native_test_report': normalize_tests(run / 'automation/index.json', run)}
    if action == 'prepare':
        path = run / 'unreal-result.json'
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if (not isinstance(data, dict) or not isinstance(data.get('project'), str)
                or not isinstance(data.get('version'), str) or not data['version']
                or Path(data['project']).resolve() != project_file(config, project)):
            raise ValueError('Unreal inspection reported the wrong project or no actual version')
        return {'native_result': data, 'native_result_file': evidence(path, run)}
    if action == 'smoke':
        text = (run / 'editor.log').read_text(encoding='utf-8', errors='replace')
        scene = settings(config, 'unreal')['smoke_map']
        # A zero exit alone can mean startup ended before loading the requested world.
        import re
        loaded = any('Bringing World' in line and scene in line and 'up for play' in line for line in text.splitlines())
        if not loaded or not re.search(r'Engine is initialized|Game Engine Initialized', text):
            raise ValueError('No evidence that the requested map entered an initialized game runtime')
        return {'native_result': {'map': scene, 'headless': True, 'world_started': True},
                'native_result_file': evidence(run / 'editor.log', run)}
    return {}
