"""Deterministic, local specification -> checked meshes. No external service or DCC."""
from pathlib import Path
import sys


def command(settings, request, output, result):
    return [sys.executable, str(Path(__file__).with_name('procedural_worker.py')),
            str(request), str(output), str(result)]


def validate(paths):
    if not any(p.name == 'scene.glb' for p in paths) or not any(p.name == 'scene.json' for p in paths):
        raise ValueError('Procedural output requires scene.glb and scene.json')
