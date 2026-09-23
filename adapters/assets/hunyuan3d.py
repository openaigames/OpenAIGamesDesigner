"""Hunyuan3D API or explicitly configured local wrapper."""
from .command_provider import command as local_command, validate_outputs
from . import api_common
from .archive_io import DATA_EXTENSIONS
EXTENSIONS = DATA_EXTENSIONS | {'.zip'}
PRIMARY = {".glb", ".gltf", ".obj", ".fbx", ".ply", ".stl", '.usdz', '.usd', '.blend'}

def command(settings, request, output, result):
    if settings.get('mode') == 'api':
        return api_common.command('hunyuan3d', settings, request, output, result)
    return local_command(settings, request, output, result)
def validate(paths):
    validate_outputs(paths, EXTENSIONS)
    if not any(p.suffix.lower() in PRIMARY for p in paths):
        raise ValueError("Hunyuan3D result requires at least one model artifact")
