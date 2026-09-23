"""Unity inspection, native Test Framework and explicit Editor helper execution."""
from pathlib import Path
from ..common import binary, configured
from ..native_support import settings, required, token, write_json, evidence
from .reports import normalize_tests
import json

def inspect(config, project):
    binary(config)
    version_file = project / "ProjectSettings/ProjectVersion.txt"
    if not version_file.is_file() or not (project / "Assets").is_dir():
        raise ValueError("Expected Unity Assets and ProjectSettings/ProjectVersion.txt")
    text = version_file.read_text(encoding="utf-8-sig")
    version = next((line.split(":", 1)[1].strip() for line in text.splitlines()
                    if line.startswith("m_EditorVersion:")), "")
    if not version:
        raise ValueError("Missing Unity m_EditorVersion")
    return {"engine": "unity", "project_version": version,
            "version_source": str(version_file), "editor_version_verified": False}

def command(config, project, action, run, output):
    if action in config.get("commands", {}):
        return configured(config, action, project, run, output)
    base = [str(binary(config)), "-projectPath", str(project)]
    if action == "prepare":
        return base + ["-batchmode", "-quit", "-logFile", str(run / "editor.log")]
    if action == "play":
        return base + ["-logFile", str(run / "editor.log")]
    opts = settings(config, 'unity')
    if action == 'test':
        platform = required(opts, 'test_platform')
        if platform not in {'EditMode', 'PlayMode'}:
            raise ValueError('unity.test_platform must be EditMode or PlayMode; player tests use commands.test')
        argv = base + ['-batchmode', '-runTests', '-testPlatform', platform,
                       '-testResults', str(run / 'unity-tests.xml'), '-logFile', str(run / 'editor.log')]
        if opts.get('test_filter'):
            argv += ['-testFilter', required(opts, 'test_filter')]
        return argv  # -quit would terminate asynchronous Test Framework execution early.
    if action in {'smoke', 'build', 'export'}:
        for name in ('OAGDEngineBridge.cs', 'OAGDBuild.cs'):
            helper = project / 'Assets/Editor/OpenAIGamesDesigner' / name
            bundled = Path(__file__).with_name(name)
            if not helper.is_file() or helper.read_bytes() != bundled.read_bytes():
                raise ValueError('Install/review the current Unity helpers with tools/engine_setup.py first')
        request = {'report': str(run / 'unity-result.json'), 'scene': '', 'seconds': 3,
                   'scenes': [], 'target': '', 'output': '', 'development': True}
        argv = base + ['-batchmode', '-logFile', str(run / 'editor.log')]
        if action == 'smoke':
            scene = required(opts, 'smoke_scene')
            _scene(project, scene)
            seconds = opts.get('smoke_seconds', 3)
            if type(seconds) not in {int, float} or not 1 <= seconds <= 60:
                raise ValueError('unity.smoke_seconds must be between 1 and 60')
            request.update(scene=scene, seconds=seconds)
            method = 'Smoke'
        else:
            target = token(required(opts, 'build_target'), 'Unity build target', r'[A-Za-z0-9_]+')
            scenes = opts.get('build_scenes')
            if not isinstance(scenes, list) or not scenes:
                raise ValueError('unity.build_scenes must list actual project scene files')
            for scene in scenes:
                _scene(project, scene)
            name = required(opts, 'build_name')
            if name in {'.', '..'} or '/' in name or '\\' in name or ':' in name:
                raise ValueError('unity.build_name must be a filename, not a path')
            development = opts.get('development', True)
            if type(development) is not bool:
                raise ValueError('unity.development must be boolean')
            output.mkdir(parents=True, exist_ok=True)
            request.update(scenes=scenes, target=target, output=str(output / name), development=development)
            cli_targets = {'StandaloneWindows64':'Win64', 'StandaloneWindows':'Win',
                           'StandaloneLinux64':'Linux64', 'StandaloneOSX':'OSXUniversal',
                           'Android':'Android', 'iOS':'iOS', 'WebGL':'WebGL'}
            if target not in cli_targets:
                raise ValueError('Unsupported native build_target; configure commands for this platform')
            argv += ['-buildTarget', cli_targets[target]]
            method = 'Build'
        write_json(run / 'unity-request.json', request)
        return argv + ['-executeMethod', 'OAGD.EngineBridge.' + method, '-oagdRequest', str(run / 'unity-request.json')]
    raise ValueError(f'Unsupported Unity action: {action}')


def _scene(project, value):
    if not isinstance(value, str) or not value.startswith('Assets/'):
        raise ValueError('Unity scene paths must start with Assets/')
    path = (project / value).resolve()
    if not path.is_relative_to(project.resolve()) or path.suffix != '.unity' or not path.is_file():
        raise ValueError(f'Unity scene missing/outside project: {value}')


def finalize(config, project, action, run, output):
    if action in config.get('commands', {}):
        return {}
    if action == 'test':
        return {'native_test_report': normalize_tests(run / 'unity-tests.xml', run)}
    if action in {'smoke', 'build', 'export'}:
        report = run / 'unity-result.json'
        if not report.is_file():
            raise ValueError('Unity helper completion report missing')
        data = json.loads(report.read_text(encoding='utf-8-sig'))
        if (not isinstance(data, dict) or data.get('success') is not True
                or type(data.get('errors')) is not int or data['errors'] != 0
                or not isinstance(data.get('project'), str) or not data.get('version')):
            raise ValueError(f'Unity helper failed: {data}')
        if Path(data.get('project', '')).resolve() != project.resolve():
            raise ValueError('Unity report belongs to a different project')
        expected_action = 'smoke' if action == 'smoke' else 'build'
        if data.get('action') != expected_action:
            raise ValueError('Unity helper reported the wrong action')
        if action == 'smoke' and (data.get('entered_play') is not True
                                or type(data.get('frames')) is not int or data['frames'] < 1):
            raise ValueError('Unity did not demonstrate Play Mode frames')
        if action in {'build', 'export'} and not any(p.is_file() and p.stat().st_size for p in output.rglob('*')):
            raise ValueError('Unity build produced no nonempty output')
        return {'native_result': data, 'native_result_file': evidence(report, run)}
    return {}
