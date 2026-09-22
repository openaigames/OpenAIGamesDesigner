"""Run inside Blender only. Import one source into a clean scene; save a new output."""
import json
from pathlib import Path
import sys

def main():
    import bpy
    request_path, output_path, result_path = map(Path, sys.argv[sys.argv.index("--") + 1:])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    inputs = request.get("inputs", [])
    if not inputs:
        raise ValueError("Blender processing requires a source input first, followed by its sidecars")
    source = Path(inputs[0]["snapshot"])
    params = request.get("parameters", {})
    output_format = params.get("format", "glb")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    suffix = source.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(source))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(source))
    else:
        raise ValueError("Supported inputs: GLB, GLTF, FBX, OBJ")
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / ("processed." + output_format)
    if output_format == "glb":
        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB")
    elif output_format == "blend":
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
    else:
        raise ValueError("Supported outputs: glb, blend")
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    result_path.write_text(json.dumps({"artifacts": [{"path": path.name}],
        "observations": {"mesh_objects": len(meshes),
                         "vertices": sum(len(obj.data.vertices) for obj in meshes)},
        "quality_validation": "not_checked"}), encoding="utf-8")

if __name__ == "__main__":
    main()
