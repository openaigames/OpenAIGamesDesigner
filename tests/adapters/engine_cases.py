"""Reusable project/command fixtures. Files are not real Unity/Unreal engines."""
import json
from pathlib import Path


def project(root, engine, executable):
    game = root / "game"
    game.mkdir()
    config = {"schema_version": 1, "engine": engine, "engine_root": "game",
              "editor_executable": str(executable)}
    if engine == "unity":
        (game / "Assets").mkdir()
        (game / "ProjectSettings").mkdir()
        (game / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.0.1f1\n")
    else:
        (game / "Example.uproject").write_text(json.dumps({"EngineAssociation": "5.6"}))
        config["project_file"] = "Example.uproject"
    (root / ".openaigame").mkdir()
    (root / ".openaigame/project.json").write_text(json.dumps(config))
    return game, config
