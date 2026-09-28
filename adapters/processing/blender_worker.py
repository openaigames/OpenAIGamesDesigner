"""Run inside an isolated Blender process; preserve inputs and emit new assets."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_recipe import plan


def import_source(bpy, source):
    """Return only objects added by this import, including hierarchy roots."""
    before = set(bpy.data.objects)
    suffix = source.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        # Editor-only bone display meshes must not become conversion output or statistics.
        options = {"disable_bone_shape": True} if "disable_bone_shape" in bpy.ops.import_scene.gltf.get_rna_type().properties else {}
        bpy.ops.import_scene.gltf(filepath=str(source), **options)
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source))
    else:
        bpy.ops.wm.obj_import(filepath=str(source))
    objects = [obj for obj in bpy.data.objects if obj not in before]
    if not any(obj.type in {"MESH", "ARMATURE"} or obj.animation_data for obj in objects):
        raise ValueError("Imported source has no supported mesh, rig or animation")
    return objects


def require_static(objects):
    """Refuse destructive processing of rigs, animated objects or shape keys."""
    if not any(obj.type == "MESH" for obj in objects):
        raise ValueError("Assembly/optimization requires a mesh")
    for obj in objects:
        if obj.type not in {"MESH", "EMPTY"} or obj.animation_data:
            raise ValueError("Assembly/optimization currently requires static meshes and empty nodes")
        if obj.type == "MESH" and (obj.data.shape_keys or obj.data.animation_data
                                    or any(mod.type == "ARMATURE" for mod in obj.modifiers)):
            raise ValueError("Skinned or morphing meshes need a character-specific processing recipe")


def stats(objects):
    """Count real triangles, vertices and materials, rather than polygon labels."""
    meshes = [obj for obj in objects if obj.type == "MESH"]
    for obj in meshes:
        obj.data.calc_loop_triangles()
    return {"mesh_objects": len(meshes), "vertices": sum(len(obj.data.vertices) for obj in meshes),
            "triangles": sum(len(obj.data.loop_triangles) for obj in meshes),
            "materials": len({slot.material for obj in meshes for slot in obj.material_slots if slot.material})}


def optimize(bpy, objects, ratio):
    """Apply explicitly requested decimation to independent static mesh copies."""
    if ratio == 1:
        return
    for obj in objects:
        if obj.type != "MESH":
            continue
        obj.data = obj.data.copy()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        modifier = obj.modifiers.new(name="OAGD_Decimate", type="DECIMATE")
        modifier.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def process(bpy, request, output_path):
    """Build a fresh recipe scene and return non-approval observations."""
    recipe = plan(request)
    if output_path.exists() and any(output_path.iterdir()):
        raise ValueError("Output must be new or empty; previous results are never overwritten")
    output_path.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    instances = []
    for instance in recipe["instances"]:
        source = Path(instance["source"])
        objects = import_source(bpy, source)
        if recipe["operation"] != "convert":
            require_static(objects)
        before = stats(objects)
        optimize(bpy, objects, recipe["decimate_ratio"])
        if recipe["operation"] == "assemble":
            root = bpy.data.objects.new(instance["id"], None)
            bpy.context.scene.collection.objects.link(root)
            for obj in objects:
                obj.name = instance["id"] + "__" + obj.name
                if obj.parent not in objects:
                    matrix = obj.matrix_world.copy()
                    obj.parent = root
                    obj.matrix_world = matrix
            root.location = instance["position"]
            root.rotation_euler = [math.radians(v) for v in instance["rotation_degrees"]]
            root.scale = instance["scale"]
        record = {k: v for k, v in instance.items() if k != "source"}
        record.update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                      before=before, after=stats(objects))
        instances.append(record)
    bpy.context.view_layer.update()
    report = {"version": 1, "operation": recipe["operation"], "blender_version": bpy.app.version_string,
              "coordinates": "Blender right-handed Z-up, meters, XYZ Euler degrees; GLB exports Y-up",
              "decimate_ratio": recipe["decimate_ratio"], "instances": instances,
              "inputs": [{"index": i, "path": item.get("path", Path(item["snapshot"]).name),
                          "sha256": hashlib.sha256(Path(item["snapshot"]).read_bytes()).hexdigest()}
                         for i, item in enumerate(request["inputs"])],
              "observations": stats(bpy.context.scene.objects), "quality_validation": "not_checked"}
    bpy.ops.file.pack_all()
    artifacts = []
    for output_format in ("blend", "glb"):
        if recipe["format"] not in (output_format, "both"):
            continue
        path = output_path / ("processed." + output_format)
        if output_format == "blend":
            bpy.ops.wm.save_as_mainfile(filepath=str(path))
        else:
            bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB")
        artifacts.append({"path": path.name})
    (output_path / "processing-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    artifacts.append({"path": "processing-report.json"})
    return {"artifacts": artifacts, "observations": report["observations"], "quality_validation": "not_checked"}


def main():
    """Consume the existing asset-job worker protocol."""
    import bpy
    request_path, output_path, result_path = map(Path, sys.argv[sys.argv.index("--") + 1:])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = process(bpy, request, output_path)
    result_path.write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
