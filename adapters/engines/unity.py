"""Unity project inspection and editor commands; builds use project-owned hooks."""
from pathlib import Path
from .common import binary, configured

def inspect(config, project):
    binary(config)
    version_file = project / "ProjectSettings/ProjectVersion.txt"
    if not version_file.is_file() or not (project / "Assets").is_dir():
        raise ValueError("Expected Unity Assets and ProjectSettings/ProjectVersion.txt")
    text = version_file.read_text(encoding="utf-8-sig")
    version = next((line.split(":", 1)[1].strip() for line in text.splitlines()
                    if line.startswith("m_EditorVersion:")), "")
    if not version:
        raise ValueError("Missing Unity m_EditorVersion")
    return {"engine": "unity", "project_version": version,
            "version_source": str(version_file), "editor_version_verified": False}

def command(config, project, action, run, output):
    if action in config.get("commands", {}):
        return configured(config, action, project, run, output)
    base = [str(binary(config)), "-projectPath", str(project)]
    if action == "prepare":
        return base + ["-batchmode", "-quit", "-logFile", str(run / "editor.log")]
    if action == "play":
        return base + ["-logFile", str(run / "editor.log")]
    return configured(config, action, project, run, output)
