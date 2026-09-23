"""Godot 4 command adapter. Does not generate gameplay or judge game quality."""
from pathlib import Path
import os
import shutil


def executable(config):
    value = config.get("godot_executable") or os.environ.get("GODOT_BIN")
    candidate = str(value) if value else (shutil.which("godot") or shutil.which("godot4"))
    if not candidate:
        raise ValueError("Godot not found. Set godot_executable or GODOT_BIN.")
    path = Path(candidate).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Godot executable is missing: {path}")
    return path


def command(binary, engine, action, *, frames=180, script=None, preset=None, output=None, release=False):
    base = [str(binary), "--path", str(engine)]
    if action == "prepare":
        return base + ["--headless", "--editor", "--import"]
    if action == "smoke":
        return base + ["--headless", "--quit-after", str(frames)]
    if action == "test":
        return base + ["--headless", "--script", "res://" + script]
    if action == "play":
        return base
    if action in {"export", "build"}:
        return base + ["--headless", "--export-release" if release else "--export-debug", preset, str(output)]
    raise ValueError(f"Unsupported Godot action: {action}")
