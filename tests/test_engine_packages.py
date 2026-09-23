"""Engine package migration must work without the maintenance checkout."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import package_skills
import check_installation
from adapters.engines import threejs, phaser


class EnginePackageTests(unittest.TestCase):
    def test_bundle_manifest_detects_missing_and_locally_modified_files(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle=package_skills.package(Path(temp)/'bundle')
            report=check_installation.check(bundle)
            self.assertEqual(report['missing'],[])
            self.assertEqual(report['changed'],[])
            (bundle/'game-art-direction/scripts/moodboard.py').unlink()
            (bundle/'game-design/SKILL.md').write_text('local customization')
            report=check_installation.check(bundle)
            self.assertEqual(report['missing'],['game-art-direction/scripts/moodboard.py'])
            self.assertEqual(report['changed'],['game-design/SKILL.md'])

    def test_framework_entries_reject_cross_engine_dispatch(self):
        for module, other in ((threejs, 'phaser'), (phaser, 'threejs')):
            with self.assertRaises(ValueError):
                module.command({'engine': other}, ROOT, 'play', ROOT, ROOT)
            with self.assertRaises(ValueError):
                module.inspect({'engine': other}, ROOT)

    def test_relocated_bundle_imports_and_real_cli_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = package_skills.package(Path(temp) / 'bundle')
            runtime = bundle / 'game-preproduction/runtime'
            script = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from adapters.engines import godot, unity, unreal, threejs, phaser, web_common
root = Path.cwd()
engine = root / 'game'
engine.mkdir()
(engine / 'Game.uproject').write_text('{"EngineAssociation":"5.8"}')
config = {'engine': 'unreal', 'editor_executable': sys.executable, 'project_file': 'Game.uproject'}
# The adapter resolves directory aliases (including Windows junctions).
actual = unreal.command(config, engine, 'play', root, root)[1:]
expected = [str((engine / 'Game.uproject').resolve()), '-game', '-log']
assert actual == expected, f'{actual!r} != {expected!r}'
assert '--headless' in godot.command(Path(sys.executable), engine, 'smoke')
assert threejs.starter() == web_common.starter('threejs')
assert phaser.starter() == web_common.starter('phaser')
assert callable(unity.command)
print(json.dumps({'engines': 5}))
'''
            result = subprocess.run([sys.executable, '-B', '-I', '-c', script, str(runtime)],
                                    cwd=temp, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['engines'], 5)
            entry = subprocess.run([sys.executable, '-B', str(runtime / 'tools/engine_workflow.py'), '--help'],
                                   cwd=temp, capture_output=True, text=True, timeout=30)
            self.assertEqual(entry.returncode, 0, entry.stderr)
            self.assertIn('recover', entry.stdout)
            for name in ('godot', 'unity', 'unreal', 'threejs', 'phaser'):
                self.assertTrue((runtime / 'adapters/engines' / name / 'README.md').is_file())
            self.assertTrue((runtime / 'adapters/engines/mcp.md').is_file())
            for relative in ('tools/engine_setup.py', 'adapters/engines/browser_smoke.cjs',
                             'tools/engine_workflow.py',
                             'adapters/engines/sessions.py', 'adapters/engines/registry.py', 'adapters/engines/request_contract.py',
                             'adapters/engines/unity/production.py', 'adapters/engines/unreal/production.py',
                             'adapters/engines/unity/OAGDProduction.cs', 'adapters/engines/unity/OAGDPlayback.cs',
                             'adapters/engines/unreal/production_worker.py', 'schemas/engine-session.schema.json',
                             'adapters/engines/unity/OAGDEngineBridge.cs', 'adapters/engines/unity/OAGDBuild.cs',
                             'adapters/engines/unity/reports.py', 'adapters/engines/unreal/reports.py',
                             'adapters/engines/unreal/inspect_project.py', 'adapters/engines/execution.md'):
                self.assertTrue((runtime / relative).is_file(), relative)


if __name__ == '__main__':
    unittest.main()
