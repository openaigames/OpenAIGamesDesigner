#!/usr/bin/env python3
"""Build a portable skill bundle into a new destination; never overwrite installs."""
import argparse
from pathlib import Path
import shutil
import hashlib
import json
import fnmatch
import os
import re
from urllib.parse import unquote
from check_installation import bundle_id, MANIFEST


LOCAL_NAMES = {'.git', '.hg', '.svn', '__pycache__', '.godot', 'runtime',
               '.venv', 'node_modules', '.openaigame', '.asset-browser',
               '.local-review', 'credentials', 'secrets', 'work', 'outputs',
               'action-test-output'}
LOCAL_PATTERNS = ('*.pyc', '*.pyo', '.env', '.env.*', 'credentials*.json',
                  'secrets*.json', '*.pem', '*.key', '*.p12', '*.pfx',
                  '*.log', '*.pid', '*.ready.json', 'ready.json')


def release_ignore(directory, names):
    """Apply release boundaries independently of Git and local ignore settings."""
    return [name for name in names
            if name.lower() in LOCAL_NAMES or
            (name.lower() not in {'.env.example', '.env.template'} and
             any(fnmatch.fnmatchcase(name.lower(), pattern) for pattern in LOCAL_PATTERNS)) or
            (Path(directory).as_posix().endswith('/tools/workbench/web') and name == 'demo')]


def relocate_links(text, source, destination, mapping):
    """Keep local Markdown links valid after shared runtime files move."""
    def replace(match):
        target = match.group(2)
        if re.match(r'^[a-zA-Z][\w+.-]*:', target) or target.startswith('#'):
            return match.group(0)
        path, separator, fragment = target.partition('#')
        packaged = mapping.get((source.parent / unquote(path)).resolve())
        if packaged is None:
            return match.group(0)
        relative = Path(os.path.relpath(packaged, destination.parent)).as_posix()
        return match.group(1) + relative + (separator + fragment if separator else '') + ')'
    return re.sub(r'(\[[^\]\n]*\]\()([^\s)]+)\)', replace, text)


def package(destination):
    source = Path(__file__).resolve().parents[1]
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Destination already exists; choose a new bundle directory.")
    if destination.is_relative_to(source) and not destination.is_relative_to(source / "dist"):
        raise ValueError("Bundle must be under dist or outside the source repository.")
    for relative in ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/README.md", "licenses/third-party-sources.json"):
        if not (source / relative).is_file():
            raise ValueError("Required license document is missing: " + relative)
    ignore = release_ignore
    shutil.copytree(source / "skills", destination, ignore=ignore)
    shutil.copy2(source / "LICENSE", destination / "LICENSE")
    for skill in destination.glob("*/SKILL.md"):
        shutil.copy2(source / "LICENSE", skill.parent / "LICENSE")
    runtime = destination / "game-preproduction/runtime"
    for folder in ("templates", "workflows", "adapters", "schemas"):
        shutil.copytree(source / folder, runtime / folder, ignore=ignore)
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(source / name, runtime / name)
    shutil.copytree(source / "licenses", runtime / "licenses", ignore=ignore)
    (runtime / "tools").mkdir()
    for name in ("game_workflow.py", "engine_setup.py", "engine_workflow.py", "asset_workflow.py", "asset_library.py", "asset_handoff.py", "action_workflow.py", "generation_capabilities.py", "settings_server.py", "project_workbench.py", "asset_audit.py", "numeric_workflow.py", "validate_records.py", "check_installation.py", "record_io.py", "record_evidence.py", "task_state.py", "content_roots.py", "observation.py", "project_links.py", "asset_fit.py", "engine_characters.py"):
        shutil.copy2(source / "tools" / name, runtime / "tools" / name)
    shutil.copytree(source / 'tools/settings-ui', runtime / 'tools/settings-ui', ignore=ignore)
    shutil.copy2(source / 'tools/numeric_models.py',runtime / 'tools/numeric_models.py')
    shutil.copy2(source / 'tools/audio_workflow.py',runtime / 'tools/audio_workflow.py')
    shutil.copy2(source / 'tools/asset_versions.py',runtime / 'tools/asset_versions.py')
    shutil.copytree(source / 'tools/workbench', runtime / 'tools/workbench', ignore=ignore)
    shutil.copy2(source / 'tools/environment_workflow.py', runtime / 'tools/environment_workflow.py')
    shutil.copytree(source / 'tools/environment', runtime / 'tools/environment', ignore=ignore)
    shutil.copy2(source / "tools/README.md", runtime / "tools/README.md")
    (runtime / "tests").mkdir()
    shutil.copy2(source / "tests/README.md", runtime / "tests/README.md")
    shutil.copytree(source / 'tests/fixtures',runtime / 'tests/fixtures',ignore=ignore)
    mapping = {}
    for target in destination.rglob('*'):
        if not target.is_file():
            continue
        if target.is_relative_to(runtime):
            original = source / target.relative_to(runtime)
        elif target == destination / 'LICENSE':
            original = source / 'LICENSE'
        else:
            original = source / 'skills' / target.relative_to(destination)
        if original.is_file():
            mapping[original.resolve()] = target
    for original, target in mapping.items():
        if target.suffix == '.md':
            content = original.read_text(encoding='utf-8-sig')
            rewritten = relocate_links(content, original, target, mapping)
            if rewritten != content:
                target.write_text(rewritten, encoding='utf-8')
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
