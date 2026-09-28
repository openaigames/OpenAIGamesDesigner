class_name OAGDObservation
extends Node
## Attach to a project-owned test scene. Gameplay explicitly marks rule/feedback
## events; sampling does not infer successful input, hits or artistic quality.

var objects: Dictionary = {}
var tracked: Dictionary = {}
var events: Array = []
var routes: Dictionary = {}
var parameters: Array = []
var started_usec: int = 0
var game_seconds: float = 0.0
var sample_cost_usec: int = 0
var sample_count: int = 0
var queries: Array = []

func _ready() -> void:
	started_usec = Time.get_ticks_usec()
	process_priority = 10000

func ray_query(object_id: String, query_id: String, start: Vector2, finish: Vector2, mask: int, purpose: String, exclude: Array = []) -> Dictionary:
	assert(objects.has(object_id) and queries.size() < 50000)
	var node: Node2D = tracked[object_id]
	var excluded: Array[RID] = []
	for entry in exclude:
		assert(entry is RID)
		excluded.append(entry)
	var parameters_query := PhysicsRayQueryParameters2D.create(start,finish,mask,excluded)
	var hit := node.get_world_2d().direct_space_state.intersect_ray(parameters_query)
	var row := {"id":query_id,"object":object_id,"clock":"game","time":game_seconds,
		"start":[start.x,start.y],"end":[finish.x,finish.y],"blocked":not hit.is_empty(),
		"channel":"collision_mask=" + str(mask),"conditions":purpose + "; call from physics processing"}
	if not hit.is_empty():
		row.point = [hit.position.x,hit.position.y]
		row.normal = [hit.normal.x,hit.normal.y]
		row.hit_object = str(hit.collider.get_path())
	queries.append(row)
	return row

func register_object(object_id: String, node: Node2D, kind: String = "actor") -> void:
	objects[object_id] = {"id":object_id,"label":node.name,"source":str(node.get_path()),"kind":kind}
	tracked[object_id] = node
	routes[object_id] = {"id":object_id + "-route","object":object_id,"clock":"game",
		"measurement":"actual_movement","samples":[],"conditions":"sampled global_position after scene processing"}

func mark_event(object_id: String, event_name: String, details: Dictionary = {}) -> void:
	assert(objects.has(object_id), "Register the actual object before recording its events")
	events.append({"id":"event-" + str(events.size()),"object":object_id,"clock":"game",
		"time":game_seconds,"event":event_name,"data":details})

func sample_parameter(object_id: String, node: Object, property_name: String, unit: String, author_source: String) -> Error:
	if not objects.has(object_id):
		return ERR_DOES_NOT_EXIST
	var found := false
	for item in node.get_property_list():
		if str(item.name) == property_name:
			found = true
	if not found:
		return ERR_DOES_NOT_EXIST
	var actual: Variant = node.get(property_name)
	if not (actual is int or actual is float or actual is bool or actual is String):
		return ERR_INVALID_DATA
	parameters.append({"id":property_name,"object":object_id,"value":actual,"unit":unit,
		"provenance":"runtime_readback","source":author_source,"conditions":"actual property sampled in running scene"})
	return OK

func _process(delta: float) -> void:
	game_seconds += delta
	var begin := Time.get_ticks_usec()
	for object_id in tracked:
		var node: Node2D = tracked[object_id]
		if is_instance_valid(node) and node.is_inside_tree():
			var position := node.global_position
			routes[object_id].samples.append([game_seconds,position.x,position.y])
	sample_cost_usec += Time.get_ticks_usec() - begin
	sample_count += 1

func _geometry(node: Node, rows: Array) -> void:
	var vertices: Array = []
	var collision := "unknown"
	var geometry_kind := "polygon"
	var shape_data: Dictionary = {}
	if node is CollisionPolygon2D:
		for point in node.polygon:
			vertices.append(node.global_transform * point)
		collision = "disabled" if node.disabled else "enabled"
	elif node is CollisionShape2D and node.shape != null:
		var shape: Shape2D = node.shape
		if shape is ConvexPolygonShape2D:
			for point in shape.points:
				vertices.append(node.global_transform * point)
		elif shape is CircleShape2D or shape is CapsuleShape2D:
			geometry_kind = "circle_outline" if shape is CircleShape2D else "capsule_outline"
			shape_data.radius = shape.radius
			var half_line: float = maxf(0,shape.height/2 - shape.radius) if shape is CapsuleShape2D else 0
			shape_data.half_line = half_line
			for index in range(48):
				var angle := index * TAU / 48
				var point: Vector2 = Vector2(cos(angle),sin(angle)) * shape.radius
				point.y += half_line * (1 if sin(angle) >= 0 else -1)
				vertices.append(node.global_transform * point)
		elif shape is SegmentShape2D:
			geometry_kind = "segment"
			vertices = [node.global_transform * shape.a,node.global_transform * shape.b]
		else:
			geometry_kind = "rectangle" if shape is RectangleShape2D else "broad_shape_bounds"
			var rect: Rect2 = shape.get_rect()
			for point in [rect.position,rect.position + Vector2(rect.size.x,0),rect.end,rect.position + Vector2(0,rect.size.y)]:
				vertices.append(node.global_transform * point)
		collision = "disabled" if node.disabled else "enabled"
	elif node is Polygon2D:
		for point in node.polygon:
			vertices.append(node.global_transform * point)
		collision = "disabled"
	if not vertices.is_empty():
		var key := str(node.get_path())
		objects[key] = {"id":key,"label":node.name,"source":key,"kind":node.get_class()}
		var low: Vector2 = vertices[0]
		var high := low
		var points: Array = []
		for point: Vector2 in vertices:
			low = low.min(point)
			high = high.max(point)
			points.append([point.x,point.y])
		rows.append({"id":key,"position":[node.global_position.x,node.global_position.y],
			"bounds":[[low.x,low.y],[high.x,high.y]],"vertices":points,"kind":node.get_class(),
			"measurement":"engine_geometry","collision":collision,"geometry_kind":geometry_kind,"geometry_source":key,"shape":shape_data})
	if node is Camera2D:
		var key := str(node.get_path())
		objects[key] = {"id":key,"label":node.name,"source":key,"kind":"camera"}
		rows.append({"id":key,"position":[node.global_position.x,node.global_position.y],"kind":"camera",
			"measurement":"runtime_sample","projection":{"zoom":[node.zoom.x,node.zoom.y],
			"viewport_size":[node.get_viewport_rect().size.x,node.get_viewport_rect().size.y],
				"rotation_radians":0.0 if node.ignore_rotation else node.global_rotation,
				"screen_center":[node.get_screen_center_position().x,node.get_screen_center_position().y]}})
	for child in node.get_children():
		_geometry(child,rows)

func capture(scene: Node, context: Dictionary) -> Dictionary:
	var spatial: Array = []
	_geometry(scene,spatial)
	for object_id in tracked:
		var node: Node2D = tracked[object_id]
		if is_instance_valid(node):
			spatial.append({"id":object_id,"position":[node.global_position.x,node.global_position.y],
				"kind":objects[object_id].kind,"measurement":"runtime_sample"})
	var actual_context := context.duplicate(true)
	actual_context.engine = "godot"
	actual_context.engine_version = Engine.get_version_info().string
	actual_context.sampling_overhead = "route sampling total " + str(sample_cost_usec) + " us / " + str(sample_count) + " samples; final export excluded; not GPU profiling"
	return {"schema_version":1,"context":actual_context,"objects":objects.values(),
		"clocks":[{"id":"game","unit":"seconds","description":"sum of process delta; affected by engine time scale; not hardware input latency"}],
		"events":events,"curves":[],"media":[],"parameters":parameters,
		"space":{"dimensions":2,"unit":"project_world_unit","axes":"Godot 2D +X right, +Y down",
			"objects":spatial,"routes":routes.values(),"queries":queries},
		"limitations":["Only project-declared gameplay events are recorded.",
			"Shape outlines/broad bounds are labeled; actual ray results apply only to their sampled positions and collision mask.",
			"No automatic audio/video capture or artistic judgement."]}

func save_capture(path: String, scene: Node, context: Dictionary) -> Error:
	var base := str(context.get("project", "")).replace("\\", "/").simplify_path().trim_suffix("/")
	var destination := path.replace("\\", "/").simplify_path()
	if base.is_empty() or not destination.to_lower().begins_with(base.to_lower() + "/"):
		return ERR_INVALID_PARAMETER
	if FileAccess.file_exists(destination):
		return ERR_ALREADY_EXISTS
	var directory_error := DirAccess.make_dir_recursive_absolute(destination.get_base_dir())
	if directory_error != OK:
		return directory_error
	var file := FileAccess.open(destination,FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(JSON.stringify(capture(scene,context),"\t"))
	file.close()
	return OK
