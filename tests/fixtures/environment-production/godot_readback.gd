extends SceneTree

var mesh_count := 0
var triangle_count := 0
var material_count := 0
var combined: AABB

func visit(node: Node) -> void:
	if node is MeshInstance3D and node.mesh:
		var bounds: AABB = node.global_transform * node.get_aabb()
		combined = bounds if mesh_count == 0 else combined.merge(bounds)
		mesh_count += 1
		for surface in range(node.mesh.get_surface_count()):
			var arrays: Array = node.mesh.surface_get_arrays(surface)
			var indices = arrays[Mesh.ARRAY_INDEX]
			triangle_count += indices.size() / 3 if indices != null and indices.size() else arrays[Mesh.ARRAY_VERTEX].size() / 3
			if node.mesh.surface_get_material(surface):
				material_count += 1
	for child in node.get_children():
		visit(child)

func _initialize() -> void:
	var arguments := OS.get_cmdline_user_args()
	if arguments.size() != 2:
		quit(2)
		return
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var error := document.append_from_file(arguments[0], state)
	if error != OK:
		push_error("GLB import failed: " + str(error))
		quit(3)
		return
	var scene := document.generate_scene(state)
	if scene == null:
		quit(4)
		return
	root.add_child(scene)
	await process_frame
	visit(scene)
	var report := {"engine": "Godot", "version": Engine.get_version_info(),
		"source": arguments[0], "mesh_count": mesh_count, "triangles": triangle_count,
		"material_surfaces": material_count, "bounds_m": {
			"position": [combined.position.x, combined.position.y, combined.position.z],
			"size": [combined.size.x, combined.size.y, combined.size.z]},
		"visual_approval": "not_assessed", "collision_test": "not_run"}
	var file := FileAccess.open(arguments[1], FileAccess.WRITE)
	if file == null:
		quit(5)
		return
	file.store_string(JSON.stringify(report, "  "))
	file.close()
	print("ENVIRONMENT_GODOT_READBACK ", mesh_count, " meshes")
	quit(0 if mesh_count > 0 else 6)
