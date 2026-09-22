"""Protocol fixture only: writes identifiable bytes, NOT generated or valid media."""
import json
from pathlib import Path
import sys
import time

request_path, output, result = map(Path, sys.argv[1:])
request = json.loads(request_path.read_text(encoding="utf-8"))
mode = request["parameters"].get("mode", "success")
print("fixture provider started", flush=True)
if mode == "fail":
    raise SystemExit(7)
if mode == "wait":
    time.sleep(60)
if mode == "missing":
    raise SystemExit(0)
payload = b"fixture bytes, not media"
if request["inputs"]:
    payload += Path(request["inputs"][0]["snapshot"]).read_bytes()
(output / "candidate.png").write_bytes(payload)
path = "../candidate.png" if mode == "escape" else "candidate.png"
result.write_text(json.dumps({"artifacts": [{"path": path}], "provider_job_id": "fixture"}), encoding="utf-8")
