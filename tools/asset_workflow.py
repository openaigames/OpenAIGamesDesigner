#!/usr/bin/env python3
"""Local asset jobs: explicit submit/run/status/cancel/retry/register, no service daemon."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.assets import hunyuan3d, image_provider, audio_provider
from adapters.processing import blender
from game_workflow import atomic_json, identifier, now, sha, stop_process
from validate_records import contained, contract

PROVIDERS = {"hunyuan3d": hunyuan3d, "image": image_provider, "audio": audio_provider, "blender": blender}
TERMINAL = {"succeeded", "registered", "failed", "blocked", "cancelled", "interrupted"}

def location(root, job_id):
    return contained(root, ".openaigame/asset-jobs/" + identifier(job_id))

def read_job(root, job_id):
    path = location(root, job_id) / "job.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    errors = contract("asset-job", value)
    if errors: raise ValueError("Invalid job record: " + "; ".join(errors))
    if value["job_id"] != job_id: raise ValueError("Job ID mismatch")
    return path, value

def new_job(root, provider, request, settings, retry_of=None):
    if provider not in PROVIDERS or not isinstance(settings, dict):
        raise ValueError("Provider and settings must match a supported local adapter")
    if not isinstance(request, dict) or not isinstance(request.get("parameters", {}), dict):
        raise ValueError("Request must contain object parameters and an input path list")
    paths = request.get("inputs", [])
    if not isinstance(paths, list): raise ValueError("inputs must be an array")
    sources = []
    for item in paths:
        original = item["path"] if isinstance(item, dict) else item
        source = contained(root, item["snapshot"] if isinstance(item, dict) else item)
        contained(root, original)
        if not source.is_file(): raise ValueError(f"Missing input: {original}")
        if isinstance(item, dict) and sha(source) != item["sha256"]:
            raise ValueError("Retry input snapshot changed")
        sources.append((original, source))
    job_id = "A" + uuid.uuid4().hex
    folder = location(root, job_id)
    folder.mkdir(parents=True)
    snapshots = []
    for original, source in sources:
        target = contained(folder / "inputs", original)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        snapshots.append({"path": original, "snapshot": target.relative_to(root).as_posix(), "sha256": sha(target)})
    job = {"schema_version": 1, "job_id": job_id, "provider": provider, "provider_job_id": None,
           "created_at": now(), "status": "queued", "settings": settings,
           "request": {"parameters": request.get("parameters", {}), "inputs": snapshots},
           "attempts": [], "artifacts": [], "notes": []}
    if retry_of: job["retry_of"] = retry_of
    atomic_json(folder / "job.json", job)
    return job

def claim(folder):
    lock = folder / "worker.lock"
    with lock.open("x", encoding="utf-8") as out: out.write(str(os.getpid()))
    return lock

def artifacts(root, base, result, job):
    if not isinstance(result, dict) or not isinstance(result.get("artifacts"), list):
        raise ValueError("Result must contain artifacts array")
    provider_id = result.get("provider_job_id")
    if provider_id is not None and not isinstance(provider_id, str): raise ValueError("Invalid provider_job_id")
    paths = []
    for item in result["artifacts"]:
        if not isinstance(item, dict): raise ValueError("Invalid artifact entry")
        path = contained(base, item.get("path"))
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Artifact must be a nonempty file inside the project/output")
        if path in paths: raise ValueError("Duplicate artifact path")
        paths.append(path)
    PROVIDERS[job["provider"]].validate(paths)
    return [{"schema_version": 1, "path": p.relative_to(root).as_posix(), "sha256": sha(p),
             "bytes": p.stat().st_size, "source": {"job_id": job["job_id"], "provider": job["provider"],
             "provider_job_id": provider_id}, "quality_validation": "not_checked"} for p in paths]

def execute_job(root, job_id, timeout):
    path, _ = read_job(root, job_id)
    lock = claim(path.parent)
    process = None
    try:
        _, job = read_job(root, job_id)
        if job["status"] != "queued": raise ValueError("Only queued jobs can run; retry creates a new job")
        attempt = path.parent / "attempt-1"
        attempt.mkdir()
        output = attempt / "output"
        output.mkdir()
        result_path = attempt / "result.json"
        log_path = attempt / "provider.log"
        log_path.touch()
        request = json.loads(json.dumps(job["request"]))
        record = {"started_at": now(), "log": log_path.relative_to(root).as_posix()}
        job["attempts"].append(record)
        job["status"] = "running"
        atomic_json(path, job)
        try:
            for item in request["inputs"]:
                source = contained(root, item["snapshot"])
                if not source.is_file() or sha(source) != item["sha256"]: raise ValueError("Input snapshot missing or changed")
                item["snapshot"] = str(source)
            request_path = attempt / "request.json"
            atomic_json(request_path, request)
            argv = PROVIDERS[job["provider"]].command(job["settings"], request_path, output, result_path)
            record["argv"] = argv
            record["executable_sha256"] = sha(Path(argv[0]))
            atomic_json(path, job)
            import time
            options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
            with log_path.open("wb") as log:
                process = subprocess.Popen(argv, cwd=root, stdout=log, stderr=subprocess.STDOUT, shell=False, **options)
                deadline = time.monotonic() + timeout
                stop = None
                while process.poll() is None:
                    if (path.parent / "cancel.request").exists(): stop = "cancelled"
                    elif time.monotonic() >= deadline: stop = "timeout"
                    if stop:
                        stop_process(process); break
                    try: process.wait(timeout=0.1)
                    except subprocess.TimeoutExpired: pass
            record.update(exit_code=process.returncode, stop=stop)
            if stop or process.returncode != 0:
                job["status"] = "cancelled" if stop == "cancelled" else "failed"
                job["notes"].append(stop or "Provider returned nonzero exit code")
            else:
                result = json.loads(result_path.read_text(encoding="utf-8-sig"))
                job["artifacts"] = artifacts(root, output, result, job)
                job["provider_job_id"] = result.get("provider_job_id")
                record["result"] = result_path.relative_to(root).as_posix()
                record["result_sha256"] = sha(result_path)
                job["status"] = "succeeded"
                job["notes"].append("Files registered; import, licensing and game quality are not verified")
        except KeyboardInterrupt:
            if process: stop_process(process)
            job["status"] = "cancelled"
            job["notes"].append("Interrupted by operator")
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            if process: stop_process(process)
            job["status"] = "failed" if process else "blocked"
            job["notes"].append(str(error))
        finally:
            record["finished_at"] = now()
            atomic_json(path, job)
        return job
    finally:
        lock.unlink(missing_ok=True)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--provider", required=True, choices=tuple(PROVIDERS))
    submit.add_argument("--request", required=True)
    for name in ("run", "status", "cancel", "retry", "register", "mark-interrupted"):
        command = sub.add_parser(name)
        command.add_argument("--job", required=True)
        if name == "run": command.add_argument("--timeout", type=int, default=600)
        if name == "register": command.add_argument("--result", required=True)
        if name == "mark-interrupted": command.add_argument("--confirm-stopped", action="store_true")
    sub.add_parser("list")
    args = parser.parse_args(argv)
    root = args.project.resolve()
    try:
        if not root.is_dir(): raise ValueError("Project must exist")
        if args.action == "submit":
            config_path = contained(root, ".openaigame/asset-providers.json")
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
            if not isinstance(config, dict): raise ValueError("Provider configuration must be an object")
            settings = config.get(args.provider)
            if not isinstance(settings, dict): raise ValueError("Provider is not configured")
            request = json.loads(contained(root, args.request).read_text(encoding="utf-8-sig"))
            result = new_job(root, args.provider, request, settings)
        elif args.action == "list":
            result = [{"job_id": p.parent.name, "status": read_job(root, p.parent.name)[1]["status"]}
                      for p in sorted(root.glob(".openaigame/asset-jobs/*/job.json"))]
        elif args.action == "run":
            if not 1 <= args.timeout <= 86400: raise ValueError("timeout must be 1..86400 seconds")
            result = execute_job(root, args.job, args.timeout)
        elif args.action == "status":
            path, result = read_job(root, args.job)
            result = {**result, "cancel_requested": (path.parent / "cancel.request").exists()}
        elif args.action == "mark-interrupted":
            path, result = read_job(root, args.job)
            if not args.confirm_stopped: raise ValueError("Confirm the external worker has stopped before recovery")
            if result["status"] != "running": raise ValueError("Recovery only applies to abandoned running jobs")
            result["status"] = "interrupted"
            result["notes"].append("Operator confirmed worker stopped; remaining files are unverified")
            atomic_json(path, result)
            (path.parent / "worker.lock").unlink(missing_ok=True)
        elif args.action == "cancel":
            path, result = read_job(root, args.job)
            # A live worker owns status; cancellation is a separate signal.
            (path.parent / "cancel.request").touch()
            if result["status"] == "queued":
                try: lock = claim(path.parent)
                except FileExistsError: lock = None
                if lock:
                    try:
                        _, result = read_job(root, args.job)
                        if result["status"] == "queued":
                            result["status"] = "cancelled"; atomic_json(path, result)
                    finally: lock.unlink(missing_ok=True)
        else:
            path, result = read_job(root, args.job)
            lock = claim(path.parent)
            try:
                _, result = read_job(root, args.job)
                if args.action == "retry":
                    if result["status"] not in TERMINAL: raise ValueError("Only terminal jobs may be retried")
                    result = new_job(root, result["provider"], result["request"], result["settings"], result["job_id"])
                else:
                    if result["status"] != "queued": raise ValueError("Only queued jobs accept external results")
                    report = json.loads(contained(root, args.result).read_text(encoding="utf-8-sig"))
                    result["artifacts"] = artifacts(root, root, report, result)
                    result["provider_job_id"] = report.get("provider_job_id")
                    result["status"] = "registered"
                    result["notes"].append("External files registered; no provider execution or quality check claimed")
                    atomic_json(path, result)
            finally: lock.unlink(missing_ok=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.action == "run" and result["status"] != "succeeded" else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False)); return 2

if __name__ == "__main__":
    raise SystemExit(main())
