# MCP Tools and Command Adapters

[English](mcp.md) | [简体中文](mcp.zh-CN.md)

## Choose an Execution Path

1. Keep the agreed engine, project, and task. Discover services, tools, and resources actually exposed to the agent. A server entry in configuration does not prove connectivity.
2. Read actual tool descriptions and parameters. Prefer read-only calls to verify absolute project path, engine version, editor instance, and current scene. If identity is unavailable, inspect launch configuration, processes, and editor state. Do not write while ambiguity remains.
3. Use verified MCP tools for editor operations and native commands for builds/tests/packages. Prefer existing project scripts. For missing capabilities, describe the gap and use an authorized, verifiable alternative without changing engines or silently reducing requirements.
4. Establish a recoverable revision before writing and record target objects/expected results. Inspect actual returns, save, and reread/reopen. Compilation, persistence, and runtime correctness are separate checks.
5. Link results to the task, Technical Design, and validation report. Update GDD/Art Direction according to actual impact and summarize through project management.

After timeout/disconnection, inspect state/logs before retrying: operations may already have completed. Do not blindly recreate objects or mark failed saves complete. Automatic recovery requires identifiable targets/results and preservation of user edits.

## Provider and Capability Records

Keep a connection summary in game-project Technical Design.md; move longer material to design/technical/engine-connection.md. Recheck affected capabilities when versions/tool lists change. One successful tool does not validate an entire provider.

| Record | Contents |
| --- | --- |
| Project identity | Absolute path, engine version, instance/session ID, verification method |
| Provider | Upstream URL, installed version/commit, plugin version, service name |
| Environment | Launch method, working directory, connection scope/dependencies; record secret environment-variable names only |
| Status | Candidate / installed / connected / specific capability verified; connection time and evidence |
| Recovery baseline | Commit or actual backup location; treatment of unsaved changes |

| Required capability | Actual tool/command | Input/target | Evidence | Result/alternative |
| --- | --- | --- | --- | --- |
| Reading, editing, save/reopen, compilation, playtesting as needed | Discover in the active environment | Real object path | Raw output and recheck | Unverified / passed / failed / unsupported |

These are recording conventions, not prefilled passes. Instructions describe a method; real calls and rechecks establish connectivity.

## Retain Execution Evidence

CLI operations continue to write `runs/<run-id>/manifest.json`. For direct MCP calls, retain credential-free raw outputs, logs, and necessary screenshots in `runs/<time-and-task>-mcp/`. Link them, the task, and project revision from a project copy of the [validation template](../../templates/validation-report.md) under tests/.

Do not fabricate CLI manifests for MCP. validate_records.py neither audits arbitrary MCP outputs nor proves their authenticity. Reports identify executor, tools, before/after objects, save/reopen results, failures, and unperformed checks. If raw export is unavailable, record retrievable call IDs/locations and limitations. Separate playtest impressions from automated assertions.

## Candidate Providers

External entry points below are not bundled, automatically installed, or compatibility certifications. Pin actual versions and consult upstream installation instructions when selecting them.

| Engine | Candidate | Scope and checks |
| --- | --- | --- |
| Unreal | [chongdashu/unreal-mcp](https://github.com/chongdashu/unreal-mcp) | Experimental Python service connected to a C++ project plugin, with Actor/Blueprint tools. Compile and verify target UE, identity, persistence, and actual tool list |
| Unity | [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp) | Editor package/service; verify enabled groups, sessions, versions, save/Play/test capabilities |
| Godot | [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) | Editor launch, project execution, debugging, scene tools; verify actual tools and retain Godot CLI |

Three.js/Phaser use code, build tools, and agent browser tools. Browser connectivity does not establish game correctness, and no extra engine MCP is required for naming consistency.
