"""Blender command construction, using the bundled background conversion script."""
from pathlib import Path

def command(settings, request, output, result):
    executable = Path(settings.get("executable", "")).expanduser()
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("Blender requires an existing absolute executable")
    return [str(executable), "--background", "--factory-startup", "--disable-autoexec",
            "--python-exit-code", "1", "--python", str(Path(__file__).with_name("blender_worker.py")),
            "--", str(request), str(output), str(result)]

def validate(paths):
    if not paths or not any(p.suffix.lower() in {".glb", ".blend"} for p in paths):
        raise ValueError("Blender output requires a .glb or .blend")
