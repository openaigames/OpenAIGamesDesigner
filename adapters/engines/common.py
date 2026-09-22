"""Shared engine command hooks, configured as argv arrays (never shell text)."""
from pathlib import Path
import re

def binary(config):
    path = Path(config.get("editor_executable", "")).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise ValueError("editor_executable must identify an existing absolute executable")
    return path.resolve()

def configured(config, action, project, run, output):
    command = config.get("commands", {}).get(action)
    if not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command):
        raise ValueError(f"Configure commands.{action} as a nonempty argv array for this project")
    values = {"project": str(project), "run": str(run), "output": str(output)}
    def expand(token):
        return re.sub(r"\{(project|run|output)\}", lambda m: values[m[1]], token)
    result = [expand(x) for x in command]
    if not Path(result[0]).is_absolute() or not Path(result[0]).is_file():
        raise ValueError("Configured command executable must be an existing absolute file")
    return result
