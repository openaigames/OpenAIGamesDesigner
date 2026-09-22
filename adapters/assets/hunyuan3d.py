"""Hunyuan3D local deployment wrapper; no assumed cloud API or bundled model."""
from .command_provider import command, validate_outputs
EXTENSIONS = {".glb", ".gltf", ".obj", ".fbx", ".ply", ".stl", ".png", ".jpg", ".jpeg", ".bin", ".mtl"}
PRIMARY = {".glb", ".gltf", ".obj", ".fbx", ".ply", ".stl"}
def validate(paths):
    validate_outputs(paths, EXTENSIONS)
    if not any(p.suffix.lower() in PRIMARY for p in paths):
        raise ValueError("Hunyuan3D result requires at least one model artifact")
