#!/usr/bin/env python3
"""Validate bundled record contracts and project-local references, without executing them."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
KINDS = ("project", "run", "asset-job", "artifact")
PROJECT_ENTRIES = ("Project Management.md", "Game Concept.md", "Game Design Document.md",
                   "Art Direction.md", "Technical Design.md", "Risk & Assumption List.md")

def contained(root, value):
    if not isinstance(value, str) or not value:
        raise ValueError("Expected a nonempty relative path")
    if Path(value).is_absolute():
        raise ValueError("Record paths must be relative")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Path escapes its record/project root")
    return path

def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()

def validate(value, schema, at="$"):
    """Interpret the subset used by the bundled schemas; unknown keywords fail closed."""
    supported = {"$schema", "title", "description", "$ref", "type", "required", "properties",
                 "additionalProperties", "items", "enum", "const", "minimum", "minLength",
                 "minItems", "pattern"}
    unsupported = set(schema) - supported
    if unsupported:
        return [f"{at}: unsupported schema keywords {sorted(unsupported)}"]
    if "$ref" in schema:
        name = schema["$ref"]
        if name not in {k + ".schema.json" for k in KINDS}:
            return [f"{at}: invalid schema reference"]
        return validate(value, json.loads((SCHEMAS / name).read_text(encoding="utf-8")), at)
    errors = []
    checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
              "string": lambda x: isinstance(x, str), "integer": lambda x: type(x) is int,
              "number": lambda x: type(x) in (int, float), "boolean": lambda x: type(x) is bool,
              "null": lambda x: x is None}
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    if types and not any(checks.get(t, lambda _: False)(value) for t in types):
        return [f"{at}: expected {types}"]
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        errors.append(f"{at}: unexpected constant")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{at}: invalid enum value")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value: errors.append(f"{at}: missing {key}")
        props = schema.get("properties", {})
        for key, item in value.items():
            sub = props.get(key, schema.get("additionalProperties", True))
            if sub is False: errors.append(f"{at}.{key}: unexpected property")
            elif isinstance(sub, dict): errors.extend(validate(item, sub, at + "." + key))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0): errors.append(f"{at}: too few items")
        for i, item in enumerate(value):
            errors.extend(validate(item, schema.get("items", {}), f"{at}[{i}]"))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0): errors.append(f"{at}: too short")
        if "pattern" in schema and not re.search(schema["pattern"], value): errors.append(f"{at}: invalid format")
    if type(value) in (int, float) and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{at}: below minimum")
    return errors

def contract(kind, value):
    return validate(value, json.loads((SCHEMAS / (kind + ".schema.json")).read_text(encoding="utf-8")))

def check_file(root, value, sha=None):
    path = contained(root, value)
    if not path.is_file():
        raise ValueError(f"Missing file: {value}")
    if sha and digest(path).lower() != sha.lower():
        raise ValueError(f"Hash mismatch: {value}")

def check_record(kind, value, project, record_path):
    errors = contract(kind, value)
    if errors: return errors
    try:
        if kind == "project":
            engine = contained(project, value["engine_root"])
            if not engine.is_dir(): raise ValueError("Missing engine_root")
        if kind == "run":
            for item in value.get("inputs", []):
                check_file(record_path.parent, item["snapshot"], item["sha256"])
            for item in value["commands"]:
                check_file(record_path.parent, item["log"])
            for name, sha in value.get("build_files", {}).items():
                check_file(project, name, sha)
            report = value.get("test_report")
            if report:
                check_file(record_path.parent, report["path"], report["sha256"])
            for relation in ("task", "milestone"):
                if value.get(relation): check_file(project, value[relation])
        if kind == "asset-job":
            for item in value["request"]["inputs"]:
                check_file(project, item["snapshot"], item["sha256"])
            if value["status"] in ("succeeded", "registered") and not value["artifacts"]:
                raise ValueError("Successful/registered asset job has no artifacts")
            for artifact in value["artifacts"]:
                check_file(project, artifact["path"], artifact["sha256"])
                if contained(project, artifact["path"]).stat().st_size != artifact["bytes"]:
                    raise ValueError("Artifact byte count mismatch")
            for item in value["attempts"]:
                if item.get("log"): check_file(project, item["log"])
                if item.get("result"): check_file(project, item["result"], item.get("result_sha256"))
        if kind == "artifact":
            check_file(project, value["path"], value["sha256"])
            if contained(project, value["path"]).stat().st_size != value["bytes"]:
                raise ValueError("Artifact byte count mismatch")
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(str(error))
    return errors

def markdown_errors(project, paths):
    errors = []
    for path in paths:
        path = path.resolve()
        if not path.is_relative_to(project): errors.append(f"Linked Markdown outside project: {path}"); continue
        for target in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", path.read_text(encoding="utf-8-sig")):
            target = target.strip().split(' "')[0].strip("<>")
            if re.match(r"^[A-Za-z][\w+.-]*:", target) or target.startswith("#") or "{{" in target: continue
            target = unquote(target.split("#")[0])
            try:
                resolved = contained(path.parent, target) if not target.startswith("..") else (path.parent / target).resolve()
                if not resolved.is_relative_to(project) or not resolved.exists(): errors.append(f"{path}: missing/outside link {target}")
            except ValueError as error: errors.append(f"{path}: {error}")
    return errors

def layout_errors(project, production=False):
    """Opt-in NEW-project convention; never a migration requirement for existing games."""
    errors = []
    required = PROJECT_ENTRIES
    for name in required:
        path = contained(project, name)
        if not path.is_file() or not path.read_text(encoding="utf-8-sig").strip():
            errors.append(f"New-project layout requires nonempty root document: {name}")
    management = contained(project, "Project Management.md")
    text = management.read_text(encoding="utf-8-sig") if management.is_file() else ""
    entry_links = {p for p in linked_files(project, management)}
    for name in PROJECT_ENTRIES[1:]:
        if contained(project, name) not in entry_links:
            errors.append(f"Management index must link the professional entry: {name}")
    for name in ("Game Design Document.md", "Art Direction.md", "Technical Design.md", "Risk & Assumption List.md"):
        for folder in ("Docs", "docs", "game/Docs", "game/docs"):
            if (project / folder / name).is_file() and not (project / name).is_file():
                errors.append(f"New-project professional entry misplaced: {folder}/{name}")
    if list(project.glob("*.uproject")) or (project / "project.godot").exists() or (project / "ProjectSettings").exists():
        errors.append("New-project engine must be under game/; existing projects should omit --layout")
    # Stop at engine roots and generated caches; do not enumerate every game asset.
    for directory, dirs, files in os.walk(project, followlinks=False):
        current = Path(directory)
        dirs[:] = [d for d in dirs if d not in {".git", ".godot", ".openaigame", "runs", "builds", "Library", "Temp", "Saved", "Intermediate", "Binaries", "DerivedDataCache", "DDC", "__pycache__"}
                   and not (current / d).is_symlink()]
        if "project.godot" in files or any(n.endswith(".uproject") for n in files) or ("ProjectSettings" in dirs and "Assets" in dirs):
            if not current.is_relative_to(project / "game"):
                errors.append(f"Engine root outside game/: {current.relative_to(project)}")
            dirs[:] = []
    config_path = contained(project, ".openaigame/project.json")
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if not isinstance(config, dict):
            raise ValueError("Project config must be an object")
        engine = contained(project, config.get("engine_root", ""))
        if not engine.is_relative_to(contained(project, "game")):
            errors.append("New-project engine_root must be game or a child of game")
    if production:
        management = contained(project, "Project Management.md")
        text = management.read_text(encoding="utf-8-sig") if management.is_file() else ""
        targets = [unquote(t.strip().strip("<>").split("#")[0])
                   for t in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", text)]
        for folder in ("production/milestones/", "production/tasks/"):
            linked = [contained(project, t) for t in targets if t.startswith(folder)]
            if not any(p.is_file() and p.read_text(encoding="utf-8-sig").strip() for p in linked):
                errors.append(f"Production handoff requires a real management link to {folder}")
        if "当前里程碑：尚未建立" in text:
            errors.append("Management milestone still has its initial placeholder")
        for name in ("Game Design Document.md", "Technical Design.md"):
            path = contained(project, name)
            if path.is_file() and "状态：待讨论" in path.read_text(encoding="utf-8-sig"):
                errors.append(f"Implementation needs current rules/technical facts, not an untouched pending entry: {name}")
    return errors


def linked_files(project, path):
    """Resolve real local file links without reading engine assets or remote URLs."""
    if not path.is_file():
        return []
    found = []
    for target in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", path.read_text(encoding="utf-8-sig")):
        target = target.strip().split(' "')[0].strip("<>")
        if re.match(r"^[A-Za-z][\w+.-]*:", target) or target.startswith("#"):
            continue
        resolved = (path.parent / unquote(target.split("#")[0])).resolve()
        if resolved.is_relative_to(project) and resolved.is_file():
            found.append(resolved)
    return found


def closeout_errors(project):
    """Check persistent handoff after implementation, including interrupted/failed work.

    Does not approve quality or infer task completion. Manual reports are allowed when
    the project used direct engine commands instead of the shared run recorder.
    """
    errors = []
    management = project / "Project Management.md"
    text = management.read_text(encoding="utf-8-sig") if management.is_file() else ""
    for initial in ("项目阶段：待依据现有工程和用户目标判断", "本轮目标：澄清并推进用户提出的游戏需求，原话见概览",
                    "工程入口：待按实际项目定位"):
        if initial in text:
            errors.append(f"Closeout still contains initial management text: {initial}")
    links = linked_files(project, management)
    if not any(p.is_relative_to(project / "game") or p == project / ".openaigame/project.json" for p in links):
        errors.append("Closeout needs a management link to the actual engine entry or project config")
    def evidence(path):
        return ((path.is_relative_to(project / "runs") and path.name == "manifest.json") or
                path.is_relative_to(project / "tests/reports")) and path.stat().st_size > 0
    owners = [management, project / "Risk & Assumption List.md"]
    owners += [p for p in links if p.is_relative_to(project / "production/tasks") or p.is_relative_to(project / "production/milestones")]
    for owner in owners:
        if not any(evidence(p) for p in linked_files(project, owner)):
            errors.append(f"Closeout needs an actual run/report link in {owner.relative_to(project)}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--layout", action="store_true", help="Check new-project layout; omit for existing/custom projects")
    parser.add_argument("--production", action="store_true", help="With --layout, check minimum implementation handoff files and links")
    parser.add_argument("--closeout", action="store_true", help="With --layout --production, check saved state and evidence links after implementation, even when incomplete")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    records = []
    try:
        if not project.is_dir(): raise ValueError("Project directory does not exist")
        if args.production and not args.layout: raise ValueError("--production requires --layout")
        if args.closeout and not args.production: raise ValueError("--closeout requires --production --layout")
        if args.file:
            if not args.kind: raise ValueError("--file requires --kind")
            path = args.file.resolve()
            if not path.is_relative_to(project): raise ValueError("--file must be inside project")
            records.append((args.kind, path))
        else:
            for kind, pattern in (("project", ".openaigame/project.json"), ("run", "runs/*/manifest.json"),
                                  ("asset-job", ".openaigame/asset-jobs/*/job.json")):
                records.extend((kind, p) for p in project.glob(pattern))
        errors = []
        if args.layout:
            errors.extend(layout_errors(project, args.production))
        if args.closeout:
            errors.extend(closeout_errors(project))
        for kind, path in records:
            if not path.resolve().is_relative_to(project): errors.append(f"{path}: outside project"); continue
            try:
                value = json.loads(path.read_text(encoding="utf-8-sig"))
                errors.extend(f"{path}: {e}" for e in check_record(kind, value, project, path))
            except (OSError, ValueError) as error: errors.append(f"{path}: {error}")
        if args.markdown:
            paths = list(project.glob("*.md"))
            for folder in ("design", "production", "tests", "assets"):
                paths.extend((project / folder).rglob("*.md"))
            errors.extend(markdown_errors(project, paths))
        print(json.dumps({"records_checked": len(records), "errors": errors,
                          "layout_checked": args.layout, "production_handoff_checked": args.production,
                          "closeout_checked": args.closeout,
                          "quality_validation": "not_performed"}, ensure_ascii=False, indent=2))
        return 1 if errors else 0
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False)); return 2

if __name__ == "__main__":
    raise SystemExit(main())
