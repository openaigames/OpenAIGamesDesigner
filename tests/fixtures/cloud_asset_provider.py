"""Controlled subprocess fixture, never contacts a service."""
import json
from pathlib import Path
import sys

request, output, result = map(Path, sys.argv[1:])
data = json.loads(request.read_text(encoding='utf-8'))
remote = data.get('provider_job_id', 'fixture-remote-1')
result.with_name('remote.json').write_text(json.dumps({
    'provider': 'tripo', 'provider_job_id': remote, 'status': 'success'}), encoding='utf-8')
if 'provider_job_id' not in data:
    if data['parameters'].get('prompt') == 'timeout':
        import time
        time.sleep(60)
    raise SystemExit(1)  # Simulates loss of connection after cloud submission.
(output / 'model.glb').write_bytes(b'controlled test fixture, not a real model')
result.write_text(json.dumps({'provider_job_id': remote, 'artifacts': [{'path': 'model.glb'}]}), encoding='utf-8')
