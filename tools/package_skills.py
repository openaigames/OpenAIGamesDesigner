#!/usr/bin/env python3
"""Build a portable skill bundle into a new destination; never overwrite installs."""
import argparse
from pathlib import Path
import shutil


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
    for name in ("game_workflow.py", "asset_workflow.py", "numeric_workflow.py", "validate_records.py"):
        shutil.copy2(source / "tools" / name, runtime / "tools" / name)
    shutil.copy2(source / "tools/README.md", runtime / "tools/README.md")
    (runtime / "tests").mkdir()
    shutil.copy2(source / "tests/README.md", runtime / "tests/README.md")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(package(args.output))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")
