#!/usr/bin/env python3
"""Build a portable skill bundle into a new destination; never overwrite installs."""
import argparse
from pathlib import Path
import shutil
import hashlib
import json
from check_installation import bundle_id, MANIFEST


def package(destination):
    source = Path(__file__).resolve().parents[1]
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Destination already exists; choose a new bundle directory.")
    if destination.is_relative_to(source) and not destination.is_relative_to(source / "dist"):
        raise ValueError("Bundle must be under dist or outside the source repository.")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".godot", "runtime")
    shutil.copytree(source / "skills", destination, ignore=ignore)
    runtime = destination / "game-preproduction/runtime"
    for folder in ("templates", "workflows", "adapters", "schemas"):
        shutil.copytree(source / folder, runtime / folder, ignore=ignore)
    (runtime / "tools").mkdir()
    for name in ("game_workflow.py", "engine_setup.py", "engine_workflow.py", "asset_workflow.py", "asset_library.py", "settings_server.py", "project_workbench.py", "asset_audit.py", "numeric_workflow.py", "validate_records.py", "check_installation.py"):
        shutil.copy2(source / "tools" / name, runtime / "tools" / name)
    shutil.copytree(source / 'tools/settings-ui', runtime / 'tools/settings-ui')
    shutil.copytree(source / 'tools/workbench', runtime / 'tools/workbench', ignore=ignore)
    shutil.copy2(source / "tools/README.md", runtime / "tools/README.md")
    (runtime / "tests").mkdir()
    shutil.copy2(source / "tests/README.md", runtime / "tests/README.md")
    files = {p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(destination.rglob('*')) if p.is_file()}
    (destination / MANIFEST).write_text(json.dumps({'version':1,'bundle_id':bundle_id(files),'files':files},
                                                 ensure_ascii=False,indent=2),encoding='utf-8')
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(package(args.output))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")
