"""Validate deterministic Blender processing recipes without importing bpy."""
from __future__ import annotations

import math
from pathlib import Path
import re


def vector(value, field, positive=False):
    """Require three finite numbers, with positive scales when requested."""
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(field + " must contain three numbers")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError(field + " must contain finite numbers")
    if positive and any(v <= 0 for v in value):
        raise ValueError(field + " must be positive; bake mirrors separately")
    return value


def plan(request):
    """Resolve input indices to snapshots; never read arbitrary manifest paths."""
    if not isinstance(request, dict):
        raise ValueError("Request must be an object")
    inputs = request.get("inputs", [])
    params = request.get("parameters", {})
    if not isinstance(inputs, list) or not inputs or not isinstance(params, dict):
        raise ValueError("Blender requires inputs and object parameters")
    unknown = set(params) - {"operation", "format", "instances", "decimate_ratio"}
    if unknown:
        raise ValueError("Unknown Blender parameters: " + ", ".join(sorted(unknown)))
    operation = params.get("operation", "convert")
    if operation not in ("convert", "assemble", "optimize"):
        raise ValueError("Supported operations: convert, assemble, optimize")
    output_format = params.get("format", "glb")
    if output_format not in ("glb", "blend", "both"):
        raise ValueError("Supported outputs: glb, blend, both")
    ratio = params.get("decimate_ratio", 1.0)
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio):
        raise ValueError("decimate_ratio must be a finite number")
    if not 0 < ratio <= 1:
        raise ValueError("decimate_ratio must be greater than zero and at most one")
    if operation == "convert" and "decimate_ratio" in params:
        raise ValueError("Use optimize or assemble for explicit decimation")
    if operation == "optimize" and "decimate_ratio" not in params:
        raise ValueError("optimize requires an explicit decimate_ratio")
    if operation != "assemble" and "instances" in params:
        raise ValueError("instances are only supported for assemble")
    instances = params.get("instances") if operation == "assemble" else [{"id": "asset", "input": 0}]
    if not isinstance(instances, list) or not 1 <= len(instances) <= 512:
        raise ValueError("assemble requires 1–512 explicit instances")
    result, ids = [], set()
    for instance in instances:
        fields = {"id", "input", "position", "rotation_degrees", "scale"}
        if not isinstance(instance, dict) or set(instance) - fields:
            raise ValueError("Invalid instance fields")
        key = instance.get("id")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key) or key in ids:
            raise ValueError("Instance IDs must be unique safe identifiers")
        ids.add(key)
        index = instance.get("input")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(inputs):
            raise ValueError("Instance input index is out of range")
        entry = inputs[index]
        if not isinstance(entry, dict) or not isinstance(entry.get("snapshot"), str):
            raise ValueError("Worker inputs require recorded snapshots")
        source = Path(entry["snapshot"])
        if not source.is_absolute() or not source.is_file() or source.suffix.lower() not in {".glb", ".gltf", ".fbx", ".obj"}:
            raise ValueError("Source must be an existing absolute GLB, GLTF, FBX or OBJ snapshot")
        result.append({"id": key, "input": index, "source": str(source),
                       "position": vector(instance.get("position", [0, 0, 0]), "position"),
                       "rotation_degrees": vector(instance.get("rotation_degrees", [0, 0, 0]), "rotation_degrees"),
                       "scale": vector(instance.get("scale", [1, 1, 1]), "scale", positive=True)})
    return {"operation": operation, "format": output_format, "decimate_ratio": ratio, "instances": result}
