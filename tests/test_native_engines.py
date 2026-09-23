"""Native commands, report integrity and explicit helper installation contracts."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from adapters.engines import unity, unreal, godot, web_common
from adapters.engines.unity import reports as unity_reports
from adapters.engines.unreal import reports as unreal_reports
from engine_setup import install_unity


class NativeEngines(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='engine with spaces ')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.game = self.root / 'game'
        self.run = self.root / 'run'
        self.out = self.root / 'out'
        self.game.mkdir(); self.run.mkdir()
        self.editor = self.root / 'UE/Engine/Binaries/Win64/UnrealEditor.exe'
        self.editor.parent.mkdir(parents=True)
        self.editor.touch(); self.editor.with_name('UnrealEditor-Cmd.exe').touch()
        (self.game / 'Sample.uproject').write_text('{}')
        self.config = {'schema_version':1, 'engine':'unreal', 'engine_root':'game',
                       'editor_executable':str(self.editor), 'project_file':'Sample.uproject'}

    def report(self, kind, content):
        raw = self.run / ('raw.xml' if kind == 'unity' else 'raw.json')
        raw.write_text(content, encoding='utf-8')
        return {'unity':unity_reports, 'unreal':unreal_reports}[kind].normalize_tests(raw, self.run)

    def test_nunit_empty_incomplete_setup_failure_rejected(self):
        for content in ['<test-run/>', '<test-run><test-case result="Unknown"/></test-run>',
                        '<test-run><test-case result="Passed"/><test-case result="NotRunnable"/></test-run>',
                        '<test-run><test-suite result="Failed"><test-case result="Passed"/></test-suite></test-run>',
                        '<test-run><test-case result="Passed">']:
            with self.subTest(content=content), self.assertRaises(ValueError): self.report('unity', content)

    def test_nunit_leaf_counts_and_provenance(self):
        result = self.report('unity', '<test-run><test-suite><test-case result="Passed"/><test-case result="Skipped"/></test-suite></test-run>')
        self.assertEqual((result['tests'], result['skipped']), (1,1))
        self.assertEqual(len(result['source']['sha256']), 64)

    def test_unreal_incomplete_or_error_report_rejected(self):
        for tests in [[], [{'state':'NotRun'}], [{'state':'InProcess'}], [{'state':'Success','errors':1}], [{'state':'Fail'}]]:
            with self.subTest(tests=tests), self.assertRaises(ValueError):
                self.report('unreal', json.dumps({'tests':tests}))
        self.assertEqual(self.report('unreal', '{"tests":[{"state":"Success"}]}')['tests'],1)

    def test_unreal_test_filter_cannot_inject_console_commands(self):
        self.config['unreal'] = {'test_filter':'System.Core; quit'}
        with self.assertRaises(ValueError): unreal.command(self.config,self.game,'test',self.run,self.out)
        self.config['unreal']['test_filter'] = 'System.Core.Math'
        argv = unreal.command(self.config,self.game,'test',self.run,self.out)
        self.assertIn('-ExecCmds=Automation RunTests System.Core.Math', argv)
        self.assertIn('-ReportOutputPath='+str(self.run/'automation'), argv)

    def test_unreal_build_and_export_require_explicit_targets_and_maps(self):
        self.config['unreal'] = {'dotnet_executable':sys.executable, 'platform':'Win64', 'build_target':'SampleEditor'}
        for name in ['UnrealBuildTool/UnrealBuildTool.dll', 'AutomationTool/AutomationTool.dll']:
            p=self.editor.parents[2]/'Binaries/DotNET'/name; p.parent.mkdir(parents=True,exist_ok=True); p.touch()
        argv=unreal.command(self.config,self.game,'build',self.run,self.out)
        self.assertIn('SampleEditor',argv)
        with self.assertRaises(ValueError): unreal.command(self.config,self.game,'export',self.run,self.out)
        self.config['unreal']['export_maps']=['/Game/Maps/Test']
        argv=unreal.command(self.config,self.game,'export',self.run,self.out)
        self.assertIn('-map=/Game/Maps/Test',argv)
        self.assertIn('-archivedirectory='+str(self.out),argv)

    def test_smoke_exit_without_world_evidence_rejected(self):
        self.config['unreal']={'smoke_map':'/Game/Test'}
        (self.run/'editor.log').write_text('Engine is initialized')
        with self.assertRaises(ValueError): unreal.finalize(self.config,self.game,'smoke',self.run,self.out)
        (self.run/'editor.log').write_text('Engine is initialized\nBringing World /Game/Test.Test up for play')
        self.assertTrue(unreal.finalize(self.config,self.game,'smoke',self.run,self.out)['native_result']['world_started'])

    def unity_project(self):
        (self.game/'Assets').mkdir(); (self.game/'ProjectSettings').mkdir()
        (self.game/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 2022.3.1f1')
        self.config.update(engine='unity', editor_executable=sys.executable)
        (self.root/'.openaigame').mkdir()
        (self.root/'.openaigame/project.json').write_text(json.dumps(self.config))

    def test_install_preserves_modified_helper(self):
        self.unity_project()
        p=install_unity(self.root)
        self.assertEqual(install_unity(self.root),p)
        p.write_text('// user changes')
        with self.assertRaises(ValueError): install_unity(self.root)
        self.assertEqual(p.read_text(),'// user changes')

    def test_shared_build_conflict_blocks_entire_helper_install(self):
        self.unity_project()
        directory = self.game/'Assets/Editor/OpenAIGamesDesigner'
        directory.mkdir(parents=True)
        shared = directory/'OAGDBuild.cs'
        shared.write_text('// user build helper')
        with self.assertRaises(ValueError): install_unity(self.root)
        self.assertFalse((directory/'OAGDEngineBridge.cs').exists())
        self.assertEqual(shared.read_text(), '// user build helper')

    def test_missing_build_dependency_blocks_editor_launch(self):
        self.unity_project()
        install_unity(self.root)
        (self.game/'Assets/Editor/OpenAIGamesDesigner/OAGDBuild.cs').unlink()
        self.config['unity']={'smoke_scene':'Assets/Real.unity'}
        (self.game/'Assets/Real.unity').touch()
        with self.assertRaisesRegex(ValueError, 'helpers'):
            unity.command(self.config,self.game,'smoke',self.run,self.out)

    def test_unity_tests_no_premature_quit(self):
        self.unity_project(); self.config['unity']={'test_platform':'EditMode'}
        argv=unity.command(self.config,self.game,'test',self.run,self.out)
        self.assertNotIn('-quit',argv)
        self.assertIn('-testResults',argv)

    def test_unity_requires_real_scene_and_installed_helper(self):
        self.unity_project()
        self.config['unity']={'smoke_scene':'Assets/Missing.unity'}
        with self.assertRaises(ValueError): unity.command(self.config,self.game,'smoke',self.run,self.out)
        install_unity(self.root)
        with self.assertRaises(ValueError): unity.command(self.config,self.game,'smoke',self.run,self.out)
        (self.game/'Assets/Real.unity').touch(); self.config['unity']['smoke_scene']='Assets/Real.unity'
        argv=unity.command(self.config,self.game,'smoke',self.run,self.out)
        self.assertIn('OAGD.EngineBridge.Smoke',argv)
        self.assertEqual(json.loads((self.run/'unity-request.json').read_text())['scene'],'Assets/Real.unity')

    def test_custom_commands_stay_authoritative(self):
        self.config['commands']={'test':[sys.executable,'custom.py','{run}']}
        self.assertEqual(unreal.command(self.config,self.game,'test',self.run,self.out),[sys.executable,'custom.py',str(self.run)])
        self.assertEqual(unreal.finalize(self.config,self.game,'test',self.run,self.out),{})

    def test_malformed_completion_report_cannot_leave_a_passed_run(self):
        for report in [[], {'success':True,'errors':False},
                       {'success':True,'errors':0,'project':str(self.game),'version':'2022',
                        'action':'smoke','entered_play':True,'frames':'many'}]:
            (self.run/'unity-result.json').write_text(json.dumps(report))
            with self.assertRaises(ValueError): unity.finalize({},self.game,'smoke',self.run,self.out)

    def test_godot_build_release_selection(self):
        argv=godot.command(Path(sys.executable),self.game,'build',preset='Linux',output=self.out/'game.x86_64',release=True)
        self.assertIn('--export-release',argv)

    def test_browser_smoke_requires_explicit_actual_build(self):
        config={'node_executable':sys.executable,'web':{'smoke_root':str(self.out)}}
        with self.assertRaises(ValueError): web_common.command(config,self.game,'smoke',self.run,self.out)
        self.out.mkdir(); (self.out/'index.html').write_text('<canvas/>')
        config['web'].update(playwright_module=sys.executable,browser_executable=sys.executable)
        argv=web_common.command(config,self.game,'smoke',self.run,self.out)
        self.assertTrue(argv[1].endswith('browser_smoke.cjs'))


if __name__ == '__main__': unittest.main()
