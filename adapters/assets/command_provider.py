"""Local provider protocol. A wrapper writes result JSON inside a job attempt."""
from pathlib import Path
import re

def command(settings, request, output, result):
    argv = settings.get("command")
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) for x in argv):
        raise ValueError("Provider command must be a nonempty argv array")
    values = {"request": str(request), "output": str(output), "result": str(result)}
    tokens = [re.sub(r"\{(request|output|result)\}", lambda m: values[m[1]], x) for x in argv]
    if not Path(tokens[0]).is_absolute() or not Path(tokens[0]).is_file():
        raise ValueError("Provider executable must be an existing absolute file")
    if not any("{request}" in x for x in argv) or not any("{result}" in x for x in argv):
        raise ValueError("Provider command must receive {request} and {result}")
    return tokens

def validate_outputs(paths, extensions):
    if not paths:
        raise ValueError("Provider returned no artifacts")
    for path in paths:
        if path.suffix.lower() not in extensions:
            raise ValueError(f"Unsupported artifact format: {path.suffix}")
