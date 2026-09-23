"""Read-only UE Python commandlet entry point; executed inside Unreal."""
import json
from pathlib import Path
import re
import unreal

command = unreal.SystemLibrary.get_command_line()
match = re.search(r'-OAGDReport=(?:"([^"]+)"|(.*?)(?=\s+-|$))', command)
if not match:
    raise RuntimeError('Missing -OAGDReport')
destination = Path(match.group(1) or match.group(2))
project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())
destination.write_text(json.dumps({'project': project, 'version': unreal.SystemLibrary.get_engine_version(),
                                   'scope': 'project-load-only'}, indent=2), encoding='utf-8')
