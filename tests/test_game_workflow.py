"""Contract tests for evidence, bounded commands and existing-file preservation."""
import contextlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import game_workflow as workflow
import package_skills


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.binary = self.root / "fake-godot.exe"
        self.binary.write_bytes(b"test-executable")
        self.call("init", "--godot", str(self.binary), "--create-engine")

    def call(self, action, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return workflow.main([action, "--project", str(self.root), *args])

    def run_fake(self, *, action="smoke", log="", exit_code=0, stop=None, version="4.7.2.stable.test", mutate=False, extra=()):
        before = set((self.root / "runs").glob("*/manifest.json"))
        def execute(argv, cwd, logfile, timeout):
            if "--version" in argv:
                logfile.write_text(version, encoding="utf-8")
                return 0, None
            logfile.write_text(log, encoding="utf-8")
            if mutate:
                (cwd / "main.tscn").write_text("changed")
            if "--export-debug" in argv and exit_code == 0:
                output = Path(argv[-1])
                output.write_bytes(b"executable")
                output.with_suffix(".pck").write_bytes(b"resources")
            return exit_code, stop
        with patch.object(workflow, "execute", execute):
            result = self.call("run", "--action", action, *extra)
        created = set((self.root / "runs").glob("*/manifest.json")) - before
        self.assertEqual(len(created), 1)
        path = created.pop()
        return result, json.loads(path.read_text()), path.parent

    def test_init_preserves_existing_files(self):
        management = self.root / "Project Management.md"
        management.write_text("User edits", encoding="utf-8")
        self.assertEqual(self.call("init", "--create-engine"), 2)
        self.assertEqual(management.read_text(), "User edits")

    def test_document_no_overwrite_or_escape(self):
        self.assertEqual(self.call("document", "--kind", "task", "--id", "T001"), 0)
        self.assertEqual(self.call("document", "--kind", "task", "--id", "T001"), 2)
        self.assertEqual(self.call("document", "--kind", "task", "--id", "../escape"), 2)

    def test_all_document_types_preserve_existing_project_content(self):
        destinations = {
            "prototype": "production/milestones",
            "vertical-slice": "production/milestones",
            "task": "production/tasks",
            "feature-spec": "design/features",
            "asset-spec": "design/assets",
            "validation-report": "tests/reports",
            "decision": "production/decisions",
        }
        management = self.root / "Project Management.md"
        before = management.read_bytes()
        for kind, folder in destinations.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.call("document", "--kind", kind, "--id", kind,
                                           "--title", "中文标题与空格 Title"), 0)
                path = self.root / folder / f"{kind}.md"
                content = path.read_text(encoding="utf-8")
                self.assertIn("中文标题与空格 Title", content)
                self.assertNotIn("{{", content)
                path.write_text("Existing user design", encoding="utf-8")
                self.assertEqual(self.call("document", "--kind", kind, "--id", kind), 2)
                self.assertEqual(path.read_text(), "Existing user design")
                self.assertEqual(self.call("document", "--kind", kind, "--id", "../escape"), 2)
        self.assertEqual(management.read_bytes(), before)

    def test_portable_bundle_uses_nested_milestone_templates(self):
        bundle = package_skills.package(self.root / "relocated toolkit")
        runtime = bundle / "game-preproduction/runtime"
        self.assertEqual(
            {p.relative_to(runtime / "templates").as_posix()
             for p in (runtime / "templates").rglob("*") if p.is_file()},
            {"project-management.md", "milestones/prototype.md", "milestones/vertical-slice.md",
             "task.md", "feature-spec.md", "asset-spec.md", "validation-report.md", "decision.md"},
        )
        target = self.root / "fresh project with spaces"
        for kind in ("prototype", "vertical-slice", "task", "feature-spec", "asset-spec",
                     "validation-report", "decision"):
            with self.subTest(kind=kind):
                result = subprocess.run(
                    [sys.executable, "-B", "-X", "utf8", str(runtime / "tools/game_workflow.py"),
                     "document", "--project", str(target), "--kind", kind, "--id", kind],
                    cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                generated = Path(result.stdout.strip())
                self.assertTrue(generated.is_file())
                self.assertTrue(generated.is_relative_to(target))

    def test_package_rejects_source_destinations_before_copying(self):
        source = Path(package_skills.__file__).resolve().parents[1]
        for folder in ("skills", "templates", "workflows", "adapters", "tools", "docs", "tests"):
            with self.subTest(folder=folder), patch.object(package_skills.shutil, "copytree") as copier:
                with self.assertRaises(ValueError):
                    package_skills.package(source / folder / "forbidden-bundle")
                copier.assert_not_called()

    def test_success_does_not_approve_quality(self):
        result, manifest, _ = self.run_fake()
        self.assertEqual(result, 0)
        self.assertEqual(manifest["status"], "passed")
        self.assertEqual(manifest["gameplay_validation"], "not_run")
        self.assertEqual(manifest["visual_validation"], "not_run")

    def test_zero_exit_script_error_fails(self):
        result, manifest, _ = self.run_fake(log="SCRIPT ERROR: Parse Error: bad code")
        self.assertEqual(result, 1)
        self.assertEqual(manifest["command_status"], "passed")
        self.assertEqual(manifest["status"], "failed")

    def test_failure_and_timeout_keep_records(self):
        for exit_code, stop, expected in [(2, None, "failed"), (-1, "timeout", "timeout"), (-1, "cancelled", "cancelled")]:
            with self.subTest(expected=expected):
                result, manifest, run = self.run_fake(exit_code=exit_code, stop=stop, log="diagnostic")
                self.assertEqual(result, 1)
                self.assertEqual(manifest["status"], expected)
                self.assertEqual((run / "engine.log").read_text(), "diagnostic")

    def test_test_script_requires_assertions(self):
        (self.root / "game/check.gd").write_text("test")
        for log, expected in [("", "failed"), ("OAGD_TEST_PASS count=8\n", "passed"), ("OAGD_TEST_PASS count=0\n", "failed")]:
            _, manifest, _ = self.run_fake(action="test", log=log, extra=("--script", "check.gd"))
            self.assertEqual(manifest["status"], expected)

    def test_input_snapshot_and_task_are_preserved(self):
        self.call("document", "--kind", "task", "--id", "T001")
        task = self.root / "production/tasks/T001.md"
        original = task.read_bytes()
        _, manifest, run = self.run_fake(extra=("--task", "production/tasks/T001.md"))
        task.write_text("Later changes")
        self.assertEqual((run / manifest["inputs"][0]["snapshot"]).read_bytes(), original)

    def test_invalid_input_and_version_drift_block(self):
        _, manifest, _ = self.run_fake(extra=("--input", "../outside.md"))
        self.assertEqual(manifest["status"], "blocked")
        config_path = self.root / workflow.CONFIG
        config = json.loads(config_path.read_text())
        config["expected_version"] = "4.6.2.stable.test"
        workflow.atomic_json(config_path, config)
        _, manifest, _ = self.run_fake()
        self.assertEqual(manifest["status"], "blocked")

    def test_changed_source_needs_review(self):
        _, manifest, _ = self.run_fake(mutate=True)
        self.assertEqual(manifest["status"], "needs_review")

    def test_project_root_engine_excludes_generated_runs(self):
        before = workflow.tree_fingerprint(self.root, self.root)
        (self.root / "runs/change.json").write_text("run")
        (self.root / "builds/game.exe").write_bytes(b"build")
        after = workflow.tree_fingerprint(self.root, self.root)
        self.assertEqual(before, after)

    def test_export_records_resources_as_well_as_executable(self):
        (self.root / "game/export_presets.cfg").write_text("preset")
        _, manifest, _ = self.run_fake(action="export", extra=("--preset", "Windows Desktop"))
        self.assertEqual(manifest["status"], "passed")
        self.assertEqual(len(manifest["build_files"]), 2)

    def test_real_subprocess_timeout_and_log(self):
        log = self.root / "timeout.log"
        code, stopped = workflow.execute([sys.executable, "-u", "-c", "import time; print('started'); time.sleep(30)"], self.root, log, 0.2)
        self.assertEqual(stopped, "timeout")
        self.assertIsNotNone(code)
        self.assertIn("started", log.read_text())


if __name__ == "__main__":
    unittest.main()
