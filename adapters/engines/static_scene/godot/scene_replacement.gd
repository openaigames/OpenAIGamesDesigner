extends RefCounted
## Persistent, conflict-aware native replacement. Call only with a checked plan.
const Importer = preload("static_scene.gd")

static func digest(value: Variant) -> String:
	return JSON.stringify(value).sha256_text()

static func number(v: float) -> float:
	return snappedf(v,0.00001)

static func value(v: Variant) -> Variant:
	if v is Texture2D:
		var image: Image = v.get_image()
		return {"image":image.get_data().hex_encode().sha256_text(),"width":image.get_width(),"height":image.get_height(),"format":image.get_format()}
	if v is Mesh:
		var surfaces := []
		for i in v.get_surface_count():
			surfaces.append({"arrays":var_to_bytes(v.surface_get_arrays(i)).hex_encode().sha256_text(),"material":value(v.surface_get_material(i))})
		return surfaces
	if v is Resource:
		var result := {"class":v.get_class()}
		for p in v.get_property_list():
			if int(p.usage)&PROPERTY_USAGE_STORAGE and p.name not in ["resource_name","resource_path","resource_local_to_scene","script"]:
				result[p.name]=value(v.get(p.name))
		return result
	match typeof(v):
		TYPE_VECTOR3:return [number(v.x),number(v.y),number(v.z)]
		TYPE_VECTOR2:return [number(v.x),number(v.y)]
		TYPE_COLOR:return [number(v.r),number(v.g),number(v.b),number(v.a)]
		TYPE_TRANSFORM3D:return [value(v.basis.x),value(v.basis.y),value(v.basis.z),value(v.origin)]
		TYPE_FLOAT:return number(v)
		TYPE_ARRAY:
			var array := []
			for x in v:array.append(value(x))
			return array
		TYPE_DICTIONARY:
			var d := {}
			var keys: Array = v.keys();keys.sort()
			for k in keys:d[str(k)]=value(v[k])
			return d
		TYPE_NIL,TYPE_BOOL,TYPE_INT,TYPE_STRING,TYPE_STRING_NAME:return v
		_:return var_to_bytes(v).hex_encode().sha256_text()

static func snapshot(node: Node) -> Dictionary:
	var d := {"name":str(node.name),"class":node.get_class(),"children":[],"metadata":{}}
	var keys := node.get_meta_list();keys.sort()
	for key in keys:
		if key!="oagd_replacement_receipt":d.metadata[str(key)]=value(node.get_meta(key))
	if node is Node3D:d.transform=value(node.transform);d.visible=node.visible
	if node.get_script()!=null:d.script=FileAccess.get_sha256(node.get_script().resource_path)
	if node is MeshInstance3D:
		d.mesh=value(node.mesh);d.material_override=value(node.material_override);d.overrides=[]
		for s in node.get_surface_override_material_count():d.overrides.append(value(node.get_surface_override_material(s)))
		d.cast_shadow=node.cast_shadow
	if node is CollisionObject3D:
		d.layer=node.collision_layer;d.mask=node.collision_mask;d.priority=node.collision_priority
	if node is CollisionShape3D:d.disabled=node.disabled;d.shape=value(node.shape)
	for child in node.get_children():d.children.append(snapshot(child))
	return d

static func fingerprint(node: Node) -> String:
	return digest(snapshot(node))

static func lookup(root: Node) -> Dictionary:
	var out := {}
	for n in [root]+root.find_children("*","Node",true,false):
		if n.has_meta("stable_id"):
			var id := str(n.get_meta("stable_id"))
			if out.has(id):return {"error":"Duplicate stable ID: "+id}
			out[id]=n
	return out

static func capture(root: Node, ids: Array) -> Dictionary:
	var nodes := lookup(root)
	var objects := {}
	for id in ids:
		if nodes.has("error") or not nodes.has(id) or not nodes[id] is MeshInstance3D or nodes[id].get_parent()!=root:return {"error":"Grayboxes must be direct MeshInstance3D children"}
		for n in [nodes[id]]+nodes[id].find_children("*","Node",true,false):
			if n.get_script()!=null:return {"error":"Keep scripted/custom grayboxes outside this transaction"}
		objects[id]={"fingerprint":fingerprint(nodes[id]),"snapshot":snapshot(nodes[id])}
	return {"schema":"oagd.scene-baseline/1","engine":"godot","objects":objects}

static func own(root: Node, owner: Node) -> void:
	# Flatten imported scene ownership so newly attached proxies survive packing.
	root.scene_file_path=""
	root.owner=owner
	for c in root.get_children():own(c,owner)

static func states(n: Node) -> Dictionary:
	var shapes := []
	for c in n.find_children("*","CollisionShape3D",true,false):shapes.append({"path":str(n.get_path_to(c)),"disabled":c.disabled})
	return {"visible":n.visible,"shapes":shapes}

static func restore(n: Node, s: Dictionary) -> void:
	n.visible=s.visible
	for c in s.shapes:n.get_node(NodePath(c.path)).disabled=c.disabled

static func preflight(root: Node3D, plan: Dictionary, assets: Dictionary) -> Dictionary:
	if plan.get("engine")!="godot" or plan.get("schema")!="oagd.scene-replacement/1":return {"ok":false,"error":"Wrong native plan"}
	if root.has_meta("oagd_replacement_receipt"):return {"ok":false,"error":"An applied transaction already exists"}
	var nodes := lookup(root)
	if nodes.has("error"):return {"ok":false,"error":nodes.error}
	for r in plan.replacements:
		if root.get_node_or_null(NodePath(r.id))!=null:return {"ok":false,"error":"Replacement name already exists"}
		if not assets.has(r.asset) or not assets[r.asset] is PackedScene:return {"ok":false,"error":"Missing native scene"}
		for id in r.targets:
			if not nodes.has(id) or nodes[id].get_parent()!=root or not plan.baseline.objects.has(id) or fingerprint(nodes[id])!=plan.baseline.objects[id].fingerprint:return {"ok":false,"error":"Graybox changed: "+str(id)}
	return {"ok":true}

static func apply(root: Node3D, plan: Dictionary, assets: Dictionary) -> Dictionary:
	var check := preflight(root,plan,assets)
	if not check.ok:return check
	var staged := []
	for r in plan.replacements:
		var wrapper := Node3D.new();wrapper.name=r.id
		wrapper.position=Vector3(r.position[0],r.position[1],r.position[2]);wrapper.rotation.y=deg_to_rad(r.yaw_degrees);wrapper.scale=Vector3.ONE*r.scale
		var instance: Node3D = assets[r.asset].instantiate();wrapper.add_child(instance)
		var imported := {};Importer.collect(instance,imported)
		var valid := true
		for row in plan.assets[r.asset].nodes:
			if not imported.has(int(row.id)) or imported[int(row.id)].get_meta("static_scene_plan","")!=plan.assets[r.asset].plan_id:valid=false
		if not valid:
			wrapper.free()
			for n in staged:n.free()
			return {"ok":false,"error":"Native scene does not match frozen revision"}
		if r.collision.policy=="source_mesh":
			for id in r.collision.nodes:
				var mesh_node: MeshInstance3D = imported[int(id)]
				var body := StaticBody3D.new();body.name="OAGDCollision";mesh_node.add_child(body)
				var shape := CollisionShape3D.new();shape.shape=mesh_node.mesh.create_trimesh_shape();body.add_child(shape)
		elif r.collision.policy=="boxes":
			for b in r.collision.boxes:
				var body := AnimatableBody3D.new();body.sync_to_physics=false
				body.name="OAGDBox_"+str(imported[int(b.node)].get_child_count());imported[int(b.node)].add_child(body)
				body.position=Vector3(b.center[0],b.center[1],b.center[2])
				var shape := CollisionShape3D.new();var box := BoxShape3D.new()
				box.size=Vector3(b.size[0],b.size[1],b.size[2]);shape.shape=box;body.add_child(shape)
		staged.append(wrapper)
	# Every resource is staged before hiding any original.
	var nodes := lookup(root)
	var receipt := {"schema":"oagd.replacement-receipt/1","plan_id":plan.plan_id,"targets":{},"roots":{}}
	for r in plan.replacements:
		for id in r.targets:
			var n: MeshInstance3D = nodes[id]
			receipt.targets[id]={"state":states(n),"before":fingerprint(n)}
			n.visible=false
			if r.collision.policy!="retain_graybox":
				for c in n.find_children("*","CollisionShape3D",true,false):c.disabled=true
			receipt.targets[id].after=fingerprint(n)
	for n in staged:
		root.add_child(n);own(n,root)
		receipt.roots[str(n.name)]=fingerprint(n)
	root.set_meta("oagd_replacement_receipt",receipt)
	return {"ok":true,"receipt":receipt}

static func rollback(root: Node3D) -> Dictionary:
	if not root.has_meta("oagd_replacement_receipt"):return {"ok":false,"error":"No applied transaction"}
	var receipt: Dictionary = root.get_meta("oagd_replacement_receipt")
	var nodes := lookup(root)
	if nodes.has("error"):return {"ok":false,"error":nodes.error}
	for id in receipt.targets:
		if not nodes.has(id) or nodes[id].get_parent()!=root or fingerprint(nodes[id])!=receipt.targets[id].after:return {"ok":false,"error":"Hidden original changed: "+str(id)}
	for path in receipt.roots:
		var n := root.get_node_or_null(NodePath(path))
		if n==null or fingerprint(n)!=receipt.roots[path]:return {"ok":false,"error":"Replacement changed: "+str(path)}
	for id in receipt.targets:restore(nodes[id],receipt.targets[id].state)
	for path in receipt.roots:root.get_node(NodePath(path)).free()
	root.remove_meta("oagd_replacement_receipt")
	return {"ok":true}

static func passage(world: World3D, start: Vector3, finish: Vector3, radius: float, height: float, mask: int=1) -> Dictionary:
	if world==null or not start.is_finite() or not finish.is_finite() or not is_finite(radius) or not is_finite(height) or radius<=0 or height<radius*2:return {"ok":false,"error":"Invalid capsule dimensions or world"}
	var shape := CapsuleShape3D.new();shape.radius=radius;shape.height=height
	var query := PhysicsShapeQueryParameters3D.new();query.shape=shape;query.transform=Transform3D(Basis.IDENTITY,start);query.collision_mask=mask
	var initial := world.direct_space_state.intersect_shape(query,1)
	query.motion=finish-start
	var motion := world.direct_space_state.cast_motion(query)
	return {"ok":true,"clear":initial.is_empty() and motion[0]>=.99999,"safe_fraction":motion[0],"initial_overlap":not initial.is_empty(),"radius":radius,"height":height}
