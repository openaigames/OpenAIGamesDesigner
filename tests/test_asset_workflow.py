"""Exercise local worker lifecycle with a real controlled subprocess; no model calls."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import asset_workflow as assets
import validate_records as records
import package_skills


class AssetWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.settings = {"command": [sys.executable, "-B", str(ROOT / "tests/fixtures/local_asset_provider.py"),
                                     "{request}", "{output}", "{result}"]}
        (self.root / ".openaigame").mkdir()
        assets.atomic_json(self.root / ".openaigame/asset-providers.json", {"image": self.settings})

    def call(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = assets.main(["--project", str(self.root), *args])
        return code, json.loads(out.getvalue())

    def submit(self, mode="success", inputs=None):
        assets.atomic_json(self.root / "request.json", {"parameters": {"mode": mode}, "inputs": inputs or []})
        code, job = self.call("submit", "--provider", "image", "--request", "request.json")
        self.assertEqual(code, 0, job)
        return job

    def test_submit_run_register_hash_and_tamper(self):
        job = self.submit()
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["attempts"], [])
        code, result = self.call("run", "--job", job["job_id"], "--timeout", "10")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["artifacts"][0]["quality_validation"], "not_checked")
        path, stored = assets.read_job(self.root, job["job_id"])
        self.assertEqual(records.check_record("asset-job", stored, self.root, path), [])
        (self.root / stored["artifacts"][0]["path"]).write_bytes(b"changed")
        self.assertTrue(records.check_record("asset-job", stored, self.root, path))
        self.assertEqual(self.call("run", "--job", job["job_id"])[0], 2)

    def test_failure_missing_output_and_escape_leave_evidence(self):
        for mode in ("fail", "missing", "escape"):
            with self.subTest(mode=mode):
                job = self.submit(mode)
                code, result = self.call("run", "--job", job["job_id"], "--timeout", "10")
                self.assertEqual(code, 1)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["artifacts"], [])
                self.assertTrue((self.root / result["attempts"][0]["log"]).is_file())

    def test_retry_preserves_original_input_and_links_new_job(self):
        source = self.root / "source.png"
        source.write_bytes(b"original input")
        job = self.submit("fail", ["source.png"])
        self.call("run", "--job", job["job_id"], "--timeout", "10")
        source.write_bytes(b"new source version")
        code, retry = self.call("retry", "--job", job["job_id"])
        self.assertEqual(code, 0)
        self.assertNotEqual(retry["job_id"], job["job_id"])
        self.assertEqual(retry["retry_of"], job["job_id"])
        self.assertEqual((self.root / retry["request"]["inputs"][0]["snapshot"]).read_bytes(), b"original input")
        self.assertEqual(retry["attempts"], [])
        snapshot = self.root / job["request"]["inputs"][0]["snapshot"]
        snapshot.write_bytes(b"tampered snapshot")
        self.assertEqual(self.call("retry", "--job", job["job_id"])[0], 2)

    def test_external_registration_is_distinct_from_execution(self):
        job = self.submit()
        (self.root / "external.png").write_bytes(b"external fixture")
        assets.atomic_json(self.root / "external.json", {"artifacts": [{"path": "external.png"}]})
        code, result = self.call("register", "--job", job["job_id"], "--result", "external.json")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "registered")
        self.assertEqual(result["attempts"], [])

    def test_queued_cancel_and_worker_lock(self):
        job = self.submit()
        lock = assets.claim(assets.location(self.root, job["job_id"]))
        self.assertEqual(self.call("run", "--job", job["job_id"])[0], 2)
        lock.unlink()
        self.assertEqual(self.call("cancel", "--job", job["job_id"])[1]["status"], "cancelled")
        self.assertEqual(self.call("run", "--job", job["job_id"])[0], 2)

    def test_actual_process_timeout(self):
        job = self.submit("wait")
        code, result = self.call("run", "--job", job["job_id"], "--timeout", "1")
        self.assertEqual(code, 1)
        self.assertEqual(result["attempts"][0]["stop"], "timeout")
        self.assertFalse((assets.location(self.root, job["job_id"]) / "worker.lock").exists())

    def test_cancel_running_worker_from_another_process(self):
        job = self.submit("wait")
        path = assets.location(self.root, job["job_id"])
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        process = subprocess.Popen([sys.executable, "-B", str(ROOT / "tools/asset_workflow.py"),
                                    "--project", str(self.root), "run", "--job", job["job_id"], "--timeout", "10"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                _, current = assets.read_job(self.root, job["job_id"])
                if current["status"] == "running": break
                time.sleep(0.02)
            self.assertEqual(current["status"], "running")
            self.call("cancel", "--job", job["job_id"])
            process.wait(timeout=10)
            self.assertEqual(assets.read_job(self.root, job["job_id"])[1]["status"], "cancelled")
        finally:
            if process.poll() is None:
                process.kill(); process.wait()

    def test_missing_command_and_changed_snapshot_block_execution(self):
        job = assets.new_job(self.root, "image", {"inputs": []}, {})
        result = assets.execute_job(self.root, job["job_id"], 5)
        self.assertEqual(result["status"], "blocked")
        (self.root / "input.png").write_bytes(b"input")
        job = self.submit(inputs=["input.png"])
        (self.root / job["request"]["inputs"][0]["snapshot"]).write_bytes(b"change")
        self.assertEqual(assets.execute_job(self.root, job["job_id"], 5)["status"], "blocked")
        with self.assertRaises(ValueError):
            assets.new_job(self.root, "image", {"inputs": ["../escape.png"]}, self.settings)

    def test_portable_runtime_can_execute_and_validate_assets(self):
        runtime = package_skills.package(self.root / "moved bundle") / "game-preproduction/runtime"
        job = self.submit()
        for script, args in (("asset_workflow.py", ["--project", str(self.root), "run", "--job", job["job_id"]]),
                             ("validate_records.py", ["--project", str(self.root)])):
            result = subprocess.run([sys.executable, "-B", str(runtime / "tools" / script), *args],
                                    cwd=self.root, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
