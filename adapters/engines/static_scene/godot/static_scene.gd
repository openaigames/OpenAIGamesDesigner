extends RefCounted
## Editor/import-time adapter. The saved scene needs no toolkit runtime component.

static func collect(node: Node, output: Dictionary) -> void:
	if str(node.name).begins_with("Node_"):
		output[int(str(node.name).trim_prefix("Node_"))] = node
	for child in node.get_children():
		collect(child, output)

static func matrix_transform(m: Array) -> Transform3D:
	return Transform3D(Basis(Vector3(m[0],m[1],m[2]),Vector3(m[4],m[5],m[6]),Vector3(m[8],m[9],m[10])),Vector3(m[12],m[13],m[14]))

static func inspect_material(material: Material) -> Dictionary:
	if not material is BaseMaterial3D:
		return {"supported": false}
	var m := material as BaseMaterial3D
	var textures := {}
	for entry in [["base_color",BaseMaterial3D.TEXTURE_ALBEDO,"sRGB"],["normal",BaseMaterial3D.TEXTURE_NORMAL,"linear; OpenGL +Y"],["metallic",BaseMaterial3D.TEXTURE_METALLIC,"linear B"],["roughness",BaseMaterial3D.TEXTURE_ROUGHNESS,"linear G"],["emission",BaseMaterial3D.TEXTURE_EMISSION,"sRGB"]]:
		var t := m.get_texture(entry[1])
		if t:
			textures[entry[0]] = {"width": t.get_width(),"height":t.get_height(),"consumer_sampling":entry[2]}
	return {"supported":true,"color":[m.albedo_color.r,m.albedo_color.g,m.albedo_color.b,m.albedo_color.a],"roughness":m.roughness,"metallic":m.metallic,"textures":textures,"normal_enabled":m.normal_enabled,"normal_scale":m.normal_scale,"roughness_channel":m.roughness_texture_channel,"metallic_channel":m.metallic_texture_channel,"cull_mode":m.cull_mode,"emission_enabled":m.emission_enabled,"emission_energy":m.emission_energy_multiplier}

static func prepare(revision: String, destination: String) -> Dictionary:
	if FileAccess.file_exists(destination):
		return {"ok":false,"error":"Use a new scene destination"}
	var plan = JSON.parse_string(FileAccess.get_file_as_string(revision.path_join("plan.json")))
	if not plan is Dictionary or plan.get("schema") != "oagd.static-scene/1":
		return {"ok":false,"error":"Invalid static scene plan"}
	# Python static_scene.check verifies plan identity. Native adapter independently
	# validates every frozen file before passing it to the engine importer.
	for relative in plan.files:
		if str(relative).is_absolute_path() or ".." in str(relative).split("/") or ":" in relative or "\\" in relative or FileAccess.get_sha256(revision.path_join(relative)) != plan.files[relative]:
			return {"ok":false,"error":"Frozen file changed or invalid path"}
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var error := document.append_from_file(revision.path_join("scene.glb"), state)
	if error != OK:
		return {"ok":false,"error":"Native GLTF load failed: %s" % error}
	var root := document.generate_scene(state)
	if not root:
		return {"ok":false,"error":"Native GLTF scene generation failed"}
	var nodes := {}
	collect(root,nodes)
	var reports := []
	for row in plan.nodes:
		var id := int(row.id)
		if not nodes.has(id):
			root.free()
			return {"ok":false,"error":"Native importer dropped node %s" % id}
		var n: Node3D = nodes[id]
		if not n.transform.is_equal_approx(matrix_transform(row.local_matrix)):
			root.free()
			return {"ok":false,"error":"Native local transform differs"}
		if row.parent != null and n.get_parent() != nodes[int(row.parent)]:
			root.free()
			return {"ok":false,"error":"Native hierarchy differs"}
		n.set_meta("source_node_index",id)
		n.set_meta("source_name",row.name)
		n.set_meta("static_scene_plan",plan.plan_id)
		var record := {"id":id,"name":str(n.name),"materials":[]}
		if row.mesh != null:
			if not n is MeshInstance3D or not n.mesh:
				root.free()
				return {"ok":false,"error":"Mesh node missing native mesh"}
			for surface in n.mesh.get_surface_count():
				record.materials.append(inspect_material(n.get_active_material(surface)))
		reports.append(record)
	var packed := PackedScene.new()
	error = packed.pack(root)
	if error == OK:
		error = ResourceSaver.save(packed,destination,ResourceSaver.FLAG_COMPRESS)
	root.free()
	return {"ok":error==OK,"error_code":error,"scene":destination,"nodes":reports,"plan_id":plan.plan_id,"collision":"none"}
