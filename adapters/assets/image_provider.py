"""Image generation through an explicitly configured local command wrapper."""
from .command_provider import command, validate_outputs
def validate(paths):
    validate_outputs(paths, {".png", ".jpg", ".jpeg", ".webp", ".tga", ".exr", ".svg"})
