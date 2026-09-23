#!/usr/bin/env python3
"""File-first project scaffolding and recorded engine commands (Python 3.10+)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import uuid

TOOLKIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLKIT))
from adapters.engines import godot, unity, unreal, web_common, threejs, phaser
from adapters.engines.common import configured
from validate_records import contract, PROJECT_ENTRIES

CONFIG = ".openaigame/project.json"
IGNORED = {".git", ".godot", "__pycache__", "node_modules", ".venv", "Library", "Temp", "Logs", "obj", "Binaries", "Intermediate", "Saved", "DerivedDataCache"}
DOCUMENTS = {
    "prototype": ("milestones/prototype.md", "production/milestones"),
    "vertical-slice": ("milestones/vertical-slice.md", "production/milestones"),
    "task": ("task.md", "production/tasks"),
    "feature-spec": ("feature-spec.md", "design/features"),
    "asset-spec": ("asset-spec.md", "design/assets"),
    "validation-report": ("validation-report.md", "tests/reports"),
    "decision": ("decision.md", "production/decisions"),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local(root, value):
    """Resolve a project-owned path, disallowing symlink/traversal escapes."""
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path must stay inside the project: {value}")
    return path


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def write_new(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as out:
        out.write(text)


def identifier(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ValueError("Use a 1-64 character identifier containing letters, digits, - or _.")
    return value


def load_config(root):
    config = json.loads(local(root, CONFIG).read_text(encoding="utf-8"))
    errors = contract("project", config)
    if errors:
        raise ValueError("Invalid project config: " + "; ".join(errors))
    if not isinstance(config.get("engine_root"), str):
        raise ValueError("engine_root must be a project-relative path.")
    local(root, config["engine_root"])
    return config


def render(template, values):
    text = (TOOLKIT / "templates" / template).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def scaffold_project(args):
    """Save a new idea before engine selection; never infer rules or overwrite work."""
    root = args.project.resolve()
    brief = args.brief.strip()
    if not brief:
        raise ValueError("A nonempty user brief is required.")
    destinations = [local(root, name) for name in PROJECT_ENTRIES]
    if any(p.exists() for p in destinations) or local(root, CONFIG).exists():
        raise ValueError("Project records already exist; read and update them in place instead of scaffolding again.")
    if any((root / name).exists() for name in ("project.godot", "ProjectSettings")) or list(root.glob("*.uproject")):
        raise ValueError("Existing engine project detected; use project intake without imposing a new layout.")
    management = render("project-management.md", {"name": root.name})
    management = management.replace("- 本轮目标：待定义。", "- 本轮目标：澄清并推进用户提出的游戏需求，原话见概览。")
    management = management.replace("| 职责 | 真实文件 | 本轮需处理内容 |\n| --- | --- | --- |",
        "| 职责 | 真实文件 | 本轮需处理内容 |\n| --- | --- | --- |\n"
        "| 概览 | [Game Concept.md](Game%20Concept.md) | 已保存用户输入，待澄清关键未知 |\n"
        "| 策划 | [Game Design Document.md](Game%20Design%20Document.md) | 入口已建立，规则待讨论 |\n"
        "| 美术 | [Art Direction.md](Art%20Direction.md) | 入口已建立，方向待讨论 |\n"
        "| 技术 | [Technical Design.md](Technical%20Design.md) | 入口已建立，条件待核实 |\n"
        "| 验证 | [Risk & Assumption List.md](Risk%20%26%20Assumption%20List.md) | 入口已建立，尚无执行证据 |")
    concept = "# 项目概览\n\n## 用户输入\n\n" + "\n".join("> " + line for line in brief.splitlines()) + (
        "\n\n## 当前依据与待决\n\n上述内容是用户输入。核心体验的具体规则、制作条件及首个实验范围由后续讨论确定；"
        "未填写内容不代表默认选择。当前未生成引擎工程，也未执行玩法验证。\n\n"
        "本入口目前仅保存原话；形成设计后需补玩家处境、行动与取舍、反馈、体验支柱及其决定状态。"
        "制作范围和资产明细由管理及美术记录负责，不从实现倒推用户已认可的定位。\n")
    pending = [
        ("游戏设计", "核心交互、规则与边界；不从模糊目标默认加入闪避、体力或其他机制。", "明确首个核心交互或获授权采用默认方案时记录规则及其依据；实施后回写流程、操作条件、状态/例外、重置与保留、参数主源和实际验证，不能只列功能名。"),
        ("美术与表现", "视觉方向、角色、场景、动画、VFX、声音和 UI；暂无已核实的资产记录。", "制作可见资产前明确本轮模型/动作与占位范围或选材委托；收到参考或使用素材后按表登记来源、用途、实际文件/代码位置、状态与限制。程序绘图、合成音效、系统字体和内置资源也登记，最终方向可以继续待定。"),
        ("技术与工程", "引擎、版本、框架、工程入口与运行方式；当前尚未核实。", "环境检查或实施后立即记录技术事实，包括模块职责、状态与数据流、配置/存档位置和可复现运行/检查方法；未决定的选型另列待定，不等待用户批准才记事实。"),
        ("风险与验证", "首个实验问题、观察方法与验收依据；当前没有执行或试玩证据。", "设计形成时补假设、影响与判断标准；每次检查后关联实际操作/观察、版本、证据、限制及下一步，失败或中断也要记录。测试总数和结构检查不替代覆盖范围或文档内容核对。"),
    ]
    bodies = [management, concept] + [
        f"# {title}\n\n状态：待讨论\n\n## 已知\n\n用户目标见 [Game Concept.md](Game%20Concept.md)。本方向尚未整理专业结论。\n\n"
        f"## 待定\n\n{unknown}\n\n## 后续补充条件\n\n{trigger}\n\n"
        "入口存在不代表设计已完成、用户已确认或工程已实现。\n"
        for title, unknown, trigger in pending]
    bodies[2] += (
        "\n## 玩家操作\n\n"
        "按已知动作和设备逐项填写，未确定的输入标待定；当前不预设任何按键或玩法。无直接玩家输入时可省略。\n\n"
        "| 动作 | 设备/输入 | 触发方式 | 可用条件/上下文 | 行为与反馈 | 状态与依据 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
    )
    bodies[3] += (
        "\n## 资产总览\n\n"
        "有实际候选或素材后逐项登记；当前没有资产条目。候选、选定与实际交付分开记录，详细来源及证据通过资产 ID 关联。\n\n"
        "| 资产 ID | 对象/用途 | 类型 | 资源名称或方案 | 临时/正式 | 选用状态与依据 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "\n## 来源与交付进度\n\n"
        "| 资产 ID | 来源与许可依据 | 源文件/引擎路径 | 制作或获取状态 | 导入状态 | 验证结果与证据 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "\n涉及动画时，再按对象与动作建立资源映射，记录模型/骨架、动画来源、衔接、适配缺口和实际状态。\n"
    )
    bodies[4] += (
        "\n## 技术信息导航\n\n"
        "[工程与环境](#工程与环境) · [系统职责与实现位置](#系统职责与实现位置) · "
        "[运行与检查入口](#运行与检查入口) · [验证与待决](#验证与待决)\n\n"
        "以下按实际依据逐项填写；当前没有已核实的引擎、模块、命令或运行结果。不要从示例或候选推定已采用架构。\n"
        "\n## 工程与环境\n\n"
        "| 项目 | 目标/已选方案 | 实际核实情况 | 状态与依据 | 位置或补充条件 |\n"
        "| --- | --- | --- | --- | --- |\n"
        "\n## 系统职责与实现位置\n\n"
        "| 系统/模块 | 职责与边界 | 状态/数据归属 | 实际入口或规格 | 实现与验证状态 |\n"
        "| --- | --- | --- | --- | --- |\n\n"
        "模块关系或关键过程需要图示时，按实际依据补简短关系图、时序图或状态图，并注明方案/实现版本；"
        "初始化不预设模块，不生成无依据的架构图。复杂接口另用输入/输出与事件表，详细内容链接负责的规格。\n"
        "\n## 运行与检查入口\n\n"
        "| 目的 | 入口/命令引用 | 工作目录与前置条件 | 预期产物或结果 | 实际执行状态/证据 |\n"
        "| --- | --- | --- | --- | --- |\n"
        "\n## 验证与待决\n\n"
        "| 问题/检查项 | 当前结论与证据 | 影响范围 | 下一步/恢复条件 |\n"
        "| --- | --- | --- | --- |\n"
    )
    for path, content in zip(destinations, bodies):
        write_new(path, content)
    print(json.dumps({"project": str(root), "created": [p.name for p in destinations],
                      "engine_created": False, "next": "Clarify the key experience unknown and update records before implementation"}, ensure_ascii=False))


def init_project(args):
    root = args.project.resolve()
    config_path = local(root, CONFIG)
    if config_path.exists():
        raise ValueError("Project already configured; existing files were not replaced.")
    engine = local(root, args.engine_root)
    selected = args.engine
    if args.create_engine and selected not in {"godot", "threejs", "phaser"}:
        raise ValueError("Blank project creation supports Godot, Three.js and Phaser; use an existing Unity/Unreal project")
    if args.create_engine and engine.exists() and any(engine.iterdir()):
        raise ValueError("Cannot create a blank engine project in a nonempty directory.")
    if selected == "godot" and not args.create_engine and not (engine / "project.godot").is_file():
        raise ValueError("No existing project.godot. Use --create-engine for a new blank project.")
    config = {"schema_version": 1, "engine": selected, "engine_root": args.engine_root,
              "godot_executable": str(args.godot.resolve()) if args.godot else "",
              "expected_version": args.expected_version or ""}
    if selected in web_common.FRAMEWORKS:
        config.pop("godot_executable")
        config["node_executable"] = str(args.node.resolve()) if args.node else ""
        config["package_manager_cli"] = str(args.package_manager_cli.resolve()) if args.package_manager_cli else ""
        web_common.executable(config)
        if not args.create_engine:
            web_common.inspect(config, engine)
    elif selected != "godot":
        config.pop("godot_executable")
        config["editor_executable"] = str(args.editor.resolve()) if args.editor else ""
        if args.project_file: config["project_file"] = args.project_file
        {"unity": unity, "unreal": unreal}[selected].inspect(config, engine)
    management = local(root, "Project Management.md")
    management_text = render("project-management.md", {"name": root.name}) if not management.exists() else None
    # Check managed destinations before changing an existing project.
    for folder in ("runs", "builds"):
        local(root, folder)
    if args.create_engine and selected in web_common.FRAMEWORKS:
        for relative, content in web_common.starter(selected).items():
            write_new(local(engine, relative), content)
    elif args.create_engine:
        write_new(engine / "project.godot", '[application]\nconfig/name="New Game Project"\nrun/main_scene="res://main.tscn"\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
        write_new(engine / "main.tscn", '[gd_scene format=3]\n\n[node name="Main" type="Node2D"]\n')
    atomic_json(config_path, config)
    if management_text is not None:
        write_new(management, management_text)
    for folder in ("runs", "builds"):
        marker = local(root, folder + "/.gdignore")
        if not marker.exists():
            write_new(marker, "")
    print(json.dumps({"project": str(root), "config": str(config_path), "engine": str(engine)}, ensure_ascii=False))


def create_document(args):
    root = args.project.resolve()
    kind = args.kind
    slug = identifier(args.id)
    template, folder = DOCUMENTS[kind]
    # Preserve the older project convention instead of splitting existing records.
    if kind == "asset-spec" and local(root, "assets/specs").is_dir() and not local(root, folder).exists():
        folder = "assets/specs"
    destination = local(root, f"{folder}/{slug}.md")
    write_new(destination, render(template, {"id": slug, "title": args.title or slug}))
    print(str(destination))


def tree_fingerprint(engine, project=None):
    """Hash source bytes, not generated imports. A fingerprint is NOT a backup."""
    hashes = {}
    excluded = {project / name for name in ("runs", "builds", ".openaigame")} if project else set()
    for directory, dirs, files in os.walk(engine, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED and Path(directory) / d not in excluded)
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix in {".tmp", ".log"}:
                continue
            relative = str(path.relative_to(engine)).replace("\\", "/")
            if path.is_symlink():
                raise ValueError(f"Resolve linked engine inputs explicitly before recording: {relative}")
            hashes[relative] = sha(path)
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError("Linked engine directories need explicit provenance handling.")
    return hashes


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=15)


def execute(argv, cwd, logfile, timeout):
    options = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NO_WINDOW}
    with logfile.open("wb") as log:
        process = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, shell=False, **options)
        try:
            return process.wait(timeout=timeout), None
        except subprocess.TimeoutExpired:
            stop_process(process)
            return process.returncode, "timeout"
        except KeyboardInterrupt:
            stop_process(process)
            return process.returncode, "cancelled"


def inputs(root, paths, run):
    records = []
    for index, value in enumerate(paths):
        source = local(root, value)
        if not source.is_file():
            raise ValueError(f"Missing input document: {value}")
        snapshot = run / "inputs" / f"{index:03d}-{source.name}"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, snapshot)
        records.append({"path": str(source.relative_to(root)), "sha256": sha(snapshot),
                        "snapshot": str(snapshot.relative_to(run))})
    return records


def run_project_engine(args, config):
    root = args.project.resolve()
    engine = local(root, config["engine_root"])
    adapter = {"unity": unity, "unreal": unreal, "threejs": threejs, "phaser": phaser}[config["engine"]]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run = local(root, "runs/" + run_id)
    run.mkdir(parents=True)
    manifest = {"schema_version": 1, "run_id": run_id, "action": args.action,
                "started_at": now(), "status": "preparing", "command_status": "not_run",
                "task": args.task, "milestone": args.milestone, "config": config,
                "gameplay_validation": "not_run", "visual_validation": "not_run",
                "commands": [], "notes": []}
    path = run / "manifest.json"
    atomic_json(path, manifest)
    try:
        paths = list(args.input)
        for relation in (args.task, args.milestone):
            if relation and relation not in paths: paths.append(relation)
        manifest["inputs"] = inputs(root, paths, run)
        info = adapter.inspect(config, engine)
        manifest["engine_inspection"] = info
        if config.get("expected_version") and config["expected_version"] != info["project_version"]:
            raise ValueError("Project engine version/association differs from expected_version")
        manifest["notes"].append("Project metadata inspected; installed editor version and compatibility require a real engine check")
        if args.action == "doctor":
            manifest["status"] = "passed"
            manifest["notes"].append("Configuration and paths checked only; no engine process executed")
        else:
            output = local(root, f"builds/{run_id}")
            if args.action == "export": output.mkdir(parents=True)
            argv = adapter.command(config, engine, args.action, run, output)
            manifest["engine_inputs"] = tree_fingerprint(engine, root)
            manifest["executable_sha256"] = sha(Path(argv[0]))
            manifest["status"] = "running"
            atomic_json(path, manifest)
            code, stopped = execute(argv, engine, run / "engine.log", args.timeout)
            manifest["commands"].append({"argv": argv, "exit_code": code, "stop": stopped, "log": "engine.log"})
            manifest["command_status"] = stopped or ("passed" if code == 0 else "failed")
            manifest["status"] = manifest["command_status"]
            text = (run / "engine.log").read_text(encoding="utf-8", errors="replace")
            if (run / "editor.log").is_file():
                text += (run / "editor.log").read_text(encoding="utf-8", errors="replace")
            errors = [line for line in text.splitlines() if re.search(r"(?:error CS\d+|Fatal error:|AutomationTool exiting with ExitCode=[1-9]|: Error:)", line)]
            manifest["engine_errors"] = errors
            if errors and manifest["status"] == "passed": manifest["status"] = "failed"
            if code == 0 and not stopped and hasattr(adapter, 'finalize'):
                manifest.update(adapter.finalize(config, engine, args.action, run, output))
            if args.action == "test" and manifest["status"] == "passed":
                report = run / "test-results.json"
                data = json.loads(report.read_text(encoding="utf-8-sig")) if report.is_file() else {}
                if (not isinstance(data, dict) or type(data.get("tests")) is not int or data["tests"] < 1
                        or type(data.get("failed")) is not int or data["failed"] != 0
                        or type(data.get("errors")) is not int or data["errors"] != 0):
                    manifest["status"] = "failed"
                    manifest["notes"].append("test requires test-results.json with actual tests>0, failed=0, errors=0")
                else: manifest["test_report"] = {**data, "path": "test-results.json", "sha256": sha(report)}
            if (args.action == "export" or (args.action == "build" and config['engine'] in {*web_common.FRAMEWORKS, 'unity'})) and manifest["status"] == "passed":
                if config["engine"] in web_common.FRAMEWORKS and (not (output / "index.html").is_file() or not (output / "index.html").stat().st_size):
                    raise ValueError("Web export requires a nonempty index.html in the requested output directory")
                files = [p for p in output.rglob("*") if p.is_file()]
                if not files or not any(p.stat().st_size > 0 for p in files):
                    manifest["status"] = "failed"; manifest["notes"].append("No nonempty exported files in requested output directory")
                else:
                    for p in files: local(output, str(p.relative_to(output)))
                    manifest["build_files"] = {p.relative_to(root).as_posix(): sha(p) for p in files}
            manifest["engine_inputs_after"] = tree_fingerprint(engine, root)
            manifest["engine_changed_during_run"] = manifest["engine_inputs_after"] != manifest["engine_inputs"]
            if manifest["engine_changed_during_run"] and args.action != "prepare" and manifest["status"] == "passed":
                manifest["status"] = "needs_review"
        manifest["notes"].append("Commands and recorded files do not approve gameplay, import quality or milestone completion")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        manifest["status"] = "failed" if manifest["commands"] else "blocked"
        manifest["notes"].append(str(error))
    finally:
        manifest["finished_at"] = now(); atomic_json(path, manifest)
    print(json.dumps({"run": str(run), "status": manifest["status"], "notes": manifest["notes"]}, ensure_ascii=False))
    return 0 if manifest["status"] == "passed" else 1


def run_engine(args):
    root = args.project.resolve()
    config = load_config(root)
    if config["engine"] != "godot":
        return run_project_engine(args, config)
    # No Markdown commands or unbounded custom shell commands are evaluated here.
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run = local(root, "runs/" + run_id)
    run.mkdir(parents=True)
    manifest = {"schema_version": 1, "run_id": run_id, "action": args.action,
                "started_at": now(), "status": "preparing", "command_status": "not_run",
                "task": args.task, "milestone": args.milestone,
                "gameplay_validation": "not_run", "visual_validation": "not_run",
                "notes": [], "config": config, "commands": []}
    manifest_path = run / "manifest.json"
    atomic_json(manifest_path, manifest)
    try:
        paths = list(args.input)
        for relation in (args.task, args.milestone):
            if relation and relation not in paths:
                paths.append(relation)
        manifest["inputs"] = inputs(root, paths, run)
        engine = local(root, config["engine_root"])
        if not (engine / "project.godot").is_file():
            raise ValueError("Missing project.godot in configured engine_root.")
        binary = godot.executable(config)
        manifest["engine_executable_sha256"] = sha(binary)
        version_command = [str(binary), "--version"]
        code, stopped = execute(version_command, engine, run / "version.log", 15)
        manifest["commands"].append({"argv": version_command, "exit_code": code, "stop": stopped, "log": "version.log"})
        version = (run / "version.log").read_text(encoding="utf-8", errors="replace").strip()
        if code != 0 or stopped or not re.match(r"4\.\d+", version):
            raise ValueError("Godot 4 version probe failed; see version.log.")
        manifest["engine_version"] = version
        expected = config.get("expected_version")
        if expected and version != expected:
            raise ValueError(f"Engine version changed: expected {expected}, found {version}")
        manifest["engine_inputs"] = tree_fingerprint(engine, root)
        manifest["notes"].append("Engine input hashes identify content; they are not restorable backups. External dependencies require separate version records.")
        if args.action == "doctor":
            manifest["command_status"] = "passed"
            manifest["status"] = "passed"
        else:
            script = None
            output = None
            custom = args.action in config.get('commands', {})
            if args.action == "test" and not custom:
                if not args.script:
                    raise ValueError("test requires --script, relative to the Godot project.")
                script_path = local(engine, args.script)
                if not script_path.is_file():
                    raise ValueError("Test script does not exist.")
                script = script_path.relative_to(engine).as_posix()
            if args.action in {"export", "build"} and not custom:
                if not args.preset or not (engine / "export_presets.cfg").is_file():
                    raise ValueError("Export needs an existing preset and matching export templates.")
                name = config.get('godot', {}).get('export_filename', 'game.exe')
                if not isinstance(name, str) or not name or '/' in name or '\\' in name or ':' in name or name in {'.', '..'}:
                    raise ValueError('godot.export_filename must be a single filename for the selected platform')
                output = local(root, f"builds/{run_id}/{name}")
                output.parent.mkdir(parents=True)
            if custom:
                custom_output = local(root, f'builds/{run_id}')
                if args.action in {'export', 'build'}:
                    output = custom_output
                    output.mkdir(parents=True)
                command = configured(config, args.action, engine, run, custom_output)
                manifest['executable_sha256'] = sha(Path(command[0]))
            else:
                command = godot.command(binary, engine, args.action, frames=args.frames,
                                        script=script, preset=args.preset, output=output,
                                        release=config.get('godot', {}).get('export_mode', 'debug') == 'release')
            manifest["status"] = "running"
            atomic_json(manifest_path, manifest)
            code, stopped = execute(command, engine, run / "engine.log", args.timeout)
            manifest["commands"].append({"argv": command, "exit_code": code, "stop": stopped, "log": "engine.log"})
            log = (run / "engine.log").read_text(encoding="utf-8", errors="replace")
            errors = [line for line in log.splitlines() if re.match(r"\s*(?:SCRIPT ERROR:|ERROR:|Parse Error:)", line)]
            manifest["engine_errors"] = errors
            manifest["command_status"] = stopped or ("passed" if code == 0 else "failed")
            manifest["status"] = stopped or ("passed" if code == 0 and not errors else "failed")
            if args.action == "test":
                if custom:
                    report = run / 'test-results.json'
                    data = json.loads(report.read_text(encoding='utf-8-sig')) if report.is_file() else {}
                    valid = (isinstance(data,dict) and type(data.get('tests')) is int and data['tests'] > 0
                             and type(data.get('failed')) is int and data['failed'] == 0
                             and type(data.get('errors')) is int and data['errors'] == 0)
                    if not valid:
                        if manifest['status'] == 'passed': manifest['status'] = 'failed'
                        manifest['notes'].append('Custom test requires actual test-results.json with tests>0, failed=0, errors=0')
                    else:
                        manifest['test_report'] = {**data, 'path':'test-results.json', 'sha256':sha(report)}
                else:
                    # GDScript errors may exit zero; require the native assertion marker.
                    passed_marker = re.search(r"^OAGD_TEST_PASS count=([1-9][0-9]*)\s*$", log, re.MULTILINE)
                    manifest["assertions"] = int(passed_marker[1]) if passed_marker else 0
                    if not passed_marker and manifest["status"] == "passed":
                        manifest["status"] = "failed"
                        manifest["notes"].append("Test script did not emit OAGD_TEST_PASS count=N.")
            if output is not None and custom:
                files = list(output.rglob('*'))
                files = [p for p in files if p.is_file()]
                for p in files: local(output, str(p.relative_to(output)))
                if not files or not any(p.stat().st_size for p in files):
                    if manifest['status'] == 'passed': manifest['status'] = 'failed'
                    manifest['notes'].append('Custom exporter produced no nonempty output files')
                manifest['build_files'] = {p.relative_to(root).as_posix():sha(p) for p in files}
            elif output is not None:
                if (not output.is_file() or not output.stat().st_size) and manifest["status"] == "passed":
                    manifest["status"] = "failed"
                    manifest["notes"].append("Exporter did not produce the expected nonempty output file.")
                if output.is_file():
                    manifest["build"] = {"path": str(output.relative_to(root)), "sha256": sha(output)}
                    manifest["build_files"] = {p.relative_to(root).as_posix(): sha(p)
                                               for p in output.parent.rglob("*") if p.is_file()}
            manifest["engine_inputs_after"] = tree_fingerprint(engine, root)
            manifest["engine_changed_during_run"] = manifest["engine_inputs_after"] != manifest["engine_inputs"]
            if manifest["engine_changed_during_run"]:
                manifest["notes"].append("Engine inputs changed during execution. Recheck relevant results against the final source.")
                if args.action != "prepare" and manifest["status"] == "passed":
                    manifest["status"] = "needs_review"
        manifest["notes"].append("Command completion does not approve gameplay, visual quality, a task, or a milestone.")
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        manifest["status"] = "blocked"
        manifest["notes"].append(str(error))
    finally:
        manifest["finished_at"] = now()
        atomic_json(manifest_path, manifest)
    print(json.dumps({"run": str(run), "status": manifest["status"], "notes": manifest["notes"]}, ensure_ascii=False))
    return 0 if manifest["status"] == "passed" else 1


def status(args):
    root = args.project.resolve()
    records = []
    for path in sorted(local(root, "runs").glob("*/manifest.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        records.append({key: value.get(key) for key in ("run_id", "action", "status", "task", "milestone", "gameplay_validation", "visual_validation")})
    print(json.dumps(records[-args.limit:], ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="subcommand", required=True)
    scaffold = sub.add_parser("scaffold", help="Save a new brief and management entry without choosing an engine")
    scaffold.add_argument("--project", type=Path, required=True)
    scaffold.add_argument("--brief", required=True, help="The user's actual request, not an invented design")
    init = sub.add_parser("init")
    init.add_argument("--project", type=Path, required=True)
    init.add_argument("--engine-root", default="game")
    init.add_argument("--engine", choices=("godot", "unity", "unreal", "threejs", "phaser"), default="godot")
    init.add_argument("--node", type=Path)
    init.add_argument("--package-manager-cli", type=Path)
    init.add_argument("--editor", type=Path)
    init.add_argument("--project-file")
    init.add_argument("--godot", type=Path)
    init.add_argument("--expected-version")
    init.add_argument("--create-engine", action="store_true")
    document = sub.add_parser("document")
    document.add_argument("--project", type=Path, required=True)
    document.add_argument("--kind", choices=tuple(DOCUMENTS), required=True)
    document.add_argument("--id", required=True)
    document.add_argument("--title")
    run = sub.add_parser("run")
    run.add_argument("--project", type=Path, required=True)
    run.add_argument("--action", choices=("doctor", "prepare", "smoke", "test", "play", "export", "build"), required=True)
    run.add_argument("--input", action="append", default=[])
    run.add_argument("--task")
    run.add_argument("--milestone")
    run.add_argument("--script")
    run.add_argument("--preset")
    run.add_argument("--frames", type=int, default=180)
    run.add_argument("--timeout", type=int, default=120)
    state = sub.add_parser("status")
    state.add_argument("--project", type=Path, required=True)
    state.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        if args.subcommand == "scaffold":
            scaffold_project(args)
        elif args.subcommand == "init":
            init_project(args)
        elif args.subcommand == "document":
            create_document(args)
        elif args.subcommand == "run":
            if args.frames < 1 or not 1 <= args.timeout <= 3600:
                raise ValueError("frames must be positive; timeout must be 1..3600 seconds.")
            return run_engine(args)
        else:
            if args.limit < 1:
                raise ValueError("limit must be positive")
            status(args)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    # Project names and paths can be Unicode even when a parent process captures legacy-encoded stdout.
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
