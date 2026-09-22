"""Engine/provider adapter contracts, deliberately independent of editor installs."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import game_workflow as workflow
import validate_records as records
from adapters.engines import unity, unreal
from adapters.assets import image_provider, audio_provider, hunyuan3d
from adapters.processing import blender

spec = importlib.util.spec_from_file_location("engine_cases", ROOT / "tests/adapters/engine_cases.py")
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def call(self, root, action):
        with contextlib.redirect_stdout(io.StringIO()):
            code = workflow.main(["run", "--project", str(root), "--action", action, "--timeout", "10"])
        path = max(root.glob("runs/*/manifest.json"), key=lambda p: p.stat().st_mtime_ns)
        data = json.loads(path.read_text())
        self.assertEqual(records.check_record("run", data, root, path), [])
        return code, data

    def test_foreign_engines_require_real_project_hooks(self):
        for name, adapter in (("unity", unity), ("unreal", unreal)):
            root = self.root / name
            root.mkdir()
            game, config = cases.project(root, name, sys.executable)
            self.assertFalse(adapter.inspect(config, game)["editor_version_verified"])
            code, result = self.call(root, "doctor")
            self.assertEqual(code, 0)
            self.assertEqual(result["command_status"], "not_run")
            self.assertEqual(self.call(root, "export")[1]["status"], "blocked")
            with self.assertRaises(ValueError):
                adapter.command(config, game, "test", root / "run", root / "out")
            argv = adapter.command(config, game, "play", root / "run", root / "out")
            self.assertIn("-projectPath" if name == "unity" else "-game", argv)

    def test_project_test_report_is_required_and_hashed(self):
        game, config = cases.project(self.root, "unity", sys.executable)
        for report, expected in ((None, "failed"), ({"tests": 0, "failed": 0, "errors": 0}, "failed"),
                                 ({"tests": True, "failed": 0, "errors": 0}, "failed"),
                                 ([], "failed"), ({"tests": 2, "failed": 0, "errors": 0}, "passed")):
            code = "pass" if report is None else "from pathlib import Path; import sys; Path(sys.argv[1]).write_text(" + repr(json.dumps(report)) + ")"
            config["commands"] = {"test": [sys.executable, "-B", "-c", code, "{run}/test-results.json"]}
            workflow.atomic_json(self.root / ".openaigame/project.json", config)
            result = self.call(self.root, "test")[1]
            self.assertEqual(result["status"], expected, result)

    def test_export_requires_output_and_registers_real_file_hashes(self):
        game, config = cases.project(self.root, "unreal", sys.executable)
        for code, expected in (("pass", "failed"),
                               ("from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b'fixture build')", "passed")):
            config["commands"] = {"export": [sys.executable, "-B", "-c", code, "{output}/game.bin"]}
            workflow.atomic_json(self.root / ".openaigame/project.json", config)
            result = self.call(self.root, "export")[1]
            self.assertEqual(result["status"], expected, result)
            self.assertEqual(result["gameplay_validation"], "not_run")

    def test_provider_protocol_and_blender_command(self):
        with self.assertRaises(ValueError):
            image_provider.command({"command": [sys.executable, "missing placeholders"]}, self.root, self.root, self.root)
        argv = blender.command({"executable": sys.executable}, self.root / "req", self.root / "out", self.root / "res")
        self.assertIn("--disable-autoexec", argv)
        self.assertIn("--python-exit-code", argv)
        self.assertEqual(argv[-3:], [str(self.root / "req"), str(self.root / "out"), str(self.root / "res")])
        for provider, accepted, rejected in ((image_provider, "a.png", "a.wav"),
                                              (audio_provider, "a.wav", "a.png"),
                                              (hunyuan3d, "a.glb", "a.png")):
            provider.validate([Path(accepted)])
            with self.assertRaises(ValueError): provider.validate([Path(rejected)])


if __name__ == "__main__":
    unittest.main()
