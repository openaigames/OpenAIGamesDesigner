"""Unreal project inspection and editor launch; automation is project-configured."""
import json
from .common import binary, configured

def project_file(config, project):
    relative = config.get("project_file", "")
    path = (project / relative).resolve()
    if not relative or not path.is_relative_to(project.resolve()) or path.suffix != ".uproject" or not path.is_file():
        raise ValueError("project_file must identify a .uproject inside engine_root")
    return path

def inspect(config, project):
    binary(config)
    path = project_file(config, project)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict): raise ValueError("uproject metadata must be an object")
    return {"engine": "unreal", "project_version": str(data.get("EngineAssociation", "")),
            "version_source": str(path), "editor_version_verified": False}

def command(config, project, action, run, output):
    path = project_file(config, project)
    if action in config.get("commands", {}):
        return configured(config, action, project, run, output)
    if action == "play":
        return [str(binary(config)), str(path), "-game", "-log"]
    return configured(config, action, project, run, output)
