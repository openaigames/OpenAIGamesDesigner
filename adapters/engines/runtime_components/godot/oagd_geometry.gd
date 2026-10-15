class_name OAGDGeometry
extends RefCounted
## JSON companion to exported GLB. Instantiates native editable nodes with stable IDs.
static func valid_number(value) -> bool:
	return (value is int or value is float) and is_finite(value)

static func valid_vector(value) -> bool:
	return value is Array and value.size() == 3 and valid_number(value[0]) and valid_number(value[1]) and valid_number(value[2])

static func valid_scene(value) -> bool:
	if not value is Dictionary or not valid_number(value.get("schema_version")) or value.schema_version != 1 or value.get("coordinates") != "RH_Y_UP_METRES_CCW" or not value.get("meshes") is Array:
		return false
	var ids := {}
	for record in value.meshes:
		if not record is Dictionary or not record.get("id") is String or record.id.is_empty() or ids.has(record.id) or not record.get("collision") is bool:
			return false
		ids[record.id] = true
		for field in ["positions", "normals", "indices", "color"]:
			if not record.get(field) is Array: return false
		if record.positions.is_empty() or record.positions.size() != record.normals.size() or record.indices.is_empty() or record.indices.size() % 3 != 0 or record.color.size() != 4:
			return false
		for component in record.color:
			if not valid_number(component) or component < 0 or component > 1: return false
		for vector in record.positions + record.normals:
			if not valid_vector(vector): return false
		for index in record.indices:
			if not valid_number(index) or index < 0 or index >= record.positions.size() or index != floor(index): return false
	return true

static func load_scene(path: String, parent: Node3D) -> Dictionary:
	var value = JSON.parse_string(FileAccess.get_file_as_string(path))
	# Reject the whole document before allocating resources or adding any nodes.
	if not is_instance_valid(parent) or not valid_scene(value):
		push_error("Invalid OAGD scene; no nodes created")
		return {}
	var result := {}
	for record in value.meshes:
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		var positions := PackedVector3Array()
		var normals := PackedVector3Array()
		var colors := PackedColorArray()
		var rgba = record.color
		var tint := Color(rgba[0], rgba[1], rgba[2], rgba[3])
		for p in record.positions:
			positions.append(Vector3(p[0], p[1], p[2]))
			colors.append(tint)
		for n in record.normals:
			normals.append(Vector3(n[0], n[1], n[2]))
		var indices := PackedInt32Array()
		# Godot front faces use clockwise winding; source glTF uses CCW.
		for i in range(0, record.indices.size(), 3):
			indices.append_array([record.indices[i], record.indices[i+2], record.indices[i+1]])
		arrays[Mesh.ARRAY_VERTEX] = positions
		arrays[Mesh.ARRAY_NORMAL] = normals
		arrays[Mesh.ARRAY_COLOR] = colors
		arrays[Mesh.ARRAY_INDEX] = indices
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var material := StandardMaterial3D.new()
		material.vertex_color_use_as_albedo = true
		mesh.surface_set_material(0, material)
		var instance := MeshInstance3D.new()
		instance.name = record.id
		instance.mesh = mesh
		parent.add_child(instance)
		if record.collision:
			instance.create_trimesh_collision()
		result[record.id] = instance
	return result
