class_name OAGDStaticAssets
extends RefCounted
## Editor preparation + reversible native scene replacement. Project owns the plan.
static func vector(a: Array) -> Vector3: return Vector3(a[0],a[1],a[2])
static func inspect_mesh(mesh: ArrayMesh) -> Dictionary:
	var surfaces := []; var triangles := 0; var lod_count := 0
	for i in range(mesh.get_surface_count()):
		var data := RenderingServer.mesh_get_surface(mesh.get_rid(),i)
		var count := int(data.get("index_count",data.vertex_count))/3; triangles += count
		var lods := []
		for lod in data.get("lods",[]): lods.append({"edge_length":lod.edge_length,"index_bytes":lod.index_data.size()})
		lod_count += lods.size()
		var m: StandardMaterial3D = mesh.surface_get_material(i)
		surfaces.append({"triangles":count,"lods":lods,"material":m.resource_name,"color":[m.albedo_color.r,m.albedo_color.g,m.albedo_color.b,m.albedo_color.a],"roughness":m.roughness,"metallic":m.metallic})
	var bounds := mesh.get_aabb()
	return {"triangles":triangles,"lod_count":lod_count,"surfaces":surfaces,"bounds":[[bounds.position.x,bounds.position.y,bounds.position.z],[bounds.end.x,bounds.end.y,bounds.end.z]]}
static func prepare_asset(source: String,destination: String) -> Dictionary:
	if FileAccess.file_exists(destination): return {"ok":false,"error":"Derived mesh exists"}
	var packed = load(source)
	if not packed is PackedScene: return {"ok":false,"error":"Source GLB did not import"}
	var root: Node = packed.instantiate(); var meshes := root.find_children("*","MeshInstance3D",true,false)
	if meshes.size()!=1: root.free(); return {"ok":false,"error":"One flattened mesh required"}
	var mesh: ArrayMesh = meshes[0].mesh
	var importer := ImporterMesh.new()
	for i in range(mesh.get_surface_count()): importer.add_surface(Mesh.PRIMITIVE_TRIANGLES,mesh.surface_get_arrays(i),[],{},mesh.surface_get_material(i),mesh.surface_get_name(i))
	importer.generate_lods(25,60,[])
	var derived := importer.get_mesh(); var stats := inspect_mesh(derived)
	var error := ResourceSaver.save(derived,destination); root.free()
	return {"ok":error==OK,"error":error,"path":destination,"observed":stats}
static func matches(node: MeshInstance3D,record: Dictionary) -> bool:
	if node.transform != Transform3D.IDENTITY or node.mesh.get_surface_count()!=1 or node.material_override!=null: return false
	var arrays := node.mesh.surface_get_arrays(0); var positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	if positions.size()!=record.positions.size(): return false
	for i in range(positions.size()):
		if positions[i].distance_to(vector(record.positions[i]))>.00001: return false
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	if indices.size()!=record.indices.size(): return false
	for i in range(0,indices.size(),3):
		if indices[i]!=record.indices[i] or indices[i+1]!=record.indices[i+2] or indices[i+2]!=record.indices[i+1]: return false
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	for i in range(positions.size()):
		if normals[i].distance_to(vector(record.normals[i]))>.001: return false
		# Native vertex colors are quantized to eight bits on upload.
		for k in range(4):
			if absf(colors[i][k]-record.color[k])>1.0/255.0+.00001: return false
	return true
static func apply(plan: Dictionary,baseline: Dictionary,lookup: Dictionary,parent: Node3D,asset_root: String) -> Dictionary:
	var records := {}; var assets := {}; var staged := []; var snapshots := []; var used := {}
	for r in baseline.meshes: records[r.id]=r
	for a in plan.assets: assets[a.id]=a
	# Every target/resource is checked before mutating any original scene node.
	for r in plan.replacements:
		if parent.get_node_or_null(NodePath(r.id))!=null: return {"ok":false,"error":"Replacement root already exists"}
		for id in r.targets:
			if used.has(id) or not lookup.has(id) or not records.has(id) or not matches(lookup[id],records[id]): return {"ok":false,"error":"Missing, reused or edited target: "+id}
			used[id]=true
		if not assets.has(r.asset) or not ResourceLoader.exists(asset_root+"/"+r.asset+".res"): return {"ok":false,"error":"Missing derived mesh"}
	for r in plan.replacements:
		var node := MeshInstance3D.new(); node.name=r.id; node.mesh=load(asset_root+"/"+r.asset+".res")
		node.position=vector(r.position); node.rotation.y=deg_to_rad(r.yaw_degrees); node.scale=Vector3.ONE*r.scale
		node.set_meta("replacement_id",r.id); node.set_meta("source_sha256",assets[r.asset].source_sha256); node.set_meta("target_ids",r.targets); node.set_meta("plan_id",plan.plan_id)
		if r.collision=="source_mesh": node.create_trimesh_collision()
		staged.append(node)
	for r in plan.replacements:
		for id in r.targets:
			var node: MeshInstance3D = lookup[id]; var collision := []
			for shape in node.find_children("*","CollisionShape3D",true,false):
				collision.append({"shape":shape,"disabled":shape.disabled})
				if r.collision=="source_mesh": shape.disabled=true
			snapshots.append({"node":node,"visible":node.visible,"collision":collision}); node.visible=false
	for node in staged: parent.add_child(node)
	return {"ok":true,"roots":staged,"undo":snapshots}
static func rollback(receipt: Dictionary) -> void:
	if not receipt.get("ok",false): return
	for s in receipt.undo:
		s.node.visible=s.visible
		for c in s.collision: c.shape.disabled=c.disabled
	for node in receipt.roots:
		if is_instance_valid(node): node.free()
	receipt.ok=false
