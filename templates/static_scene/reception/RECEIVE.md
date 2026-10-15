# Receiving the Example

[English](RECEIVE.md) | [简体中文](RECEIVE.zh-CN.md)

Rebuilds from frozen inputs with two doors, two boxes, and two Clockhill building instances. Use the declared Godot/UE engine configuration; UE 5.8 requires Win64 C++ tools. OAGD_ENGINE_CONFIG points to JSON keys godot, unreal, godot_template, and ddc. Engine caches are not project sources.

Godot: runner.py gd-prepare --script baseline.gd; freeze.py Godot; runner.py gd-prepare; runner.py gd-prepare --script rollback.gd; runner.py godot --view applied / recovered. Give every runner call a distinct --label. After configure_export.py, run runner.py gd-export, then gd-package-run.

UE: runner.py build; runner.py ue-script --script baseline.py; freeze.py Unreal; runner.py ue-script; runner.py ue-script --script rollback.py; runner.py unreal --view applied / recovered; runner.py ue-export; runner.py ue-package-run. Inspect each JSON report, not just exit codes.

Every generated destination must be new. Failed outputs remain in evidence. After copy failure, receive into a fresh directory. Preserve interrupted native imports and rebuild from a newly received snapshot; do not overwrite unique edits. Keep manual-edit conflicts intact. New-process rollback validates receipts/current objects and rejects mismatches.

Input integrity, actual rebuild/runtime, and human acceptance are separate conclusions. Automated technical checks do not establish manual playtesting, complete map reachability, or finished art. Licenses are under provenance.
