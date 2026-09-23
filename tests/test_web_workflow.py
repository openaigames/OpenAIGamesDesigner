"""Web routing, preservation and evidence contracts; fixtures are not browsers."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import game_workflow as workflow
import package_skills
from adapters.engines import web_common


class WebWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def call(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return workflow.main(list(args))

    def init(self, engine="threejs"):
        root = self.root / engine
        self.assertEqual(self.call("scaffold", "--project", str(root), "--brief", "A browser game"), 0)
        self.assertEqual(self.call("init", "--project", str(root), "--engine", engine,
                                   "--node", sys.executable, "--create-engine"), 0)
        return root

    def test_both_routes_scaffold_and_preserve_user_files(self):
        for engine in web_common.FRAMEWORKS:
            root = self.init(engine)
            self.assertEqual(len([p for p in root.glob("*.md")]), 6)
            entry = root / "game/src/main.js"
            entry.write_text("User implementation")
            self.assertEqual(self.call("init", "--project", str(root), "--engine", engine,
                                       "--node", sys.executable, "--create-engine"), 2)
            self.assertEqual(entry.read_text(), "User implementation")
            self.assertEqual(workflow.load_config(root)["engine"], engine)

    def test_nonempty_engine_refused_before_config_write(self):
        game = self.root / "game"
        game.mkdir()
        (game / "keep.txt").write_text("keep")
        self.assertEqual(self.call("init", "--project", str(self.root), "--engine", "phaser",
                                   "--node", sys.executable, "--create-engine"), 2)
        self.assertFalse((self.root / workflow.CONFIG).exists())
        self.assertEqual((game / "keep.txt").read_text(), "keep")

    def test_existing_project_wrong_framework_refused(self):
        root = self.init()
        (root / workflow.CONFIG).unlink()
        self.assertEqual(self.call("init", "--project", str(root), "--engine", "phaser", "--node", sys.executable), 2)
        self.assertFalse((root / workflow.CONFIG).exists())

    def test_missing_test_command_is_blocked(self):
        root = self.init()
        self.assertEqual(self.call("run", "--project", str(root), "--action", "test"), 1)
        manifest = json.loads(next((root / "runs").glob("*/manifest.json")).read_text())
        self.assertEqual(manifest["status"], "blocked")
        self.assertEqual(manifest["gameplay_validation"], "not_run")

    def test_prepare_uses_lock_and_node_not_shell(self):
        root = self.init()
        game = root / "game"
        config = workflow.load_config(root)
        for filename, lock, expected in [("npm-cli.js", "package-lock.json", "ci"),
                                         ("pnpm.cjs", "pnpm-lock.yaml", "--frozen-lockfile")]:
            cli = self.root / filename
            cli.write_text("// fixture")
            config["package_manager_cli"] = str(cli)
            (game / lock).write_text("{}")
            argv = web_common.command(config, game, "prepare", self.root, self.root)
            self.assertEqual(argv[0], str(Path(sys.executable).resolve()))
            self.assertIn(expected, argv)

    def test_export_requires_entry_and_keeps_quality_unverified(self):
        for index_present in (False, True):
            root = self.init("phaser" if index_present else "threejs")
            config = workflow.load_config(root)
            config["commands"] = {"export": [sys.executable, "{output}"]}
            workflow.atomic_json(root / workflow.CONFIG, config)
            def execute(argv, cwd, logfile, timeout):
                logfile.write_text("fixture export")
                out = Path(argv[1])
                (out / "bundle.js").write_text("// fixture")
                if index_present:
                    (out / "index.html").write_text("<html></html>")
                return 0, None
            with patch.object(workflow, "execute", execute):
                self.assertEqual(self.call("run", "--project", str(root), "--action", "export"), 0 if index_present else 1)
            manifest = json.loads(next((root / "runs").glob("*/manifest.json")).read_text())
            self.assertEqual(manifest["visual_validation"], "not_run")
            self.assertEqual(manifest["status"], "passed" if index_present else "failed")

    def test_portable_bundle_can_initialize_web_project(self):
        bundle = package_skills.package(self.root / "relocated bundle")
        runtime = bundle / "game-preproduction/runtime"
        root = self.root / "external project"
        result = subprocess.run([sys.executable, "-B", str(runtime / "tools/game_workflow.py"), "init",
                                 "--project", str(root), "--engine", "phaser", "--node", sys.executable,
                                 "--create-engine"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((root / "game/src/main.js").is_file())


if __name__ == "__main__":
    unittest.main()
