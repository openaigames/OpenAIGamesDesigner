extends Node3D
const Geometry = preload("res://addons/oagd/oagd_geometry.gd")
const Nav = preload("res://addons/oagd/oagd_navigation.gd")
const Motor = preload("res://addons/oagd/oagd_actor.gd")
var nav: Node3D
var actor: CharacterBody3D
var region: NavigationRegion3D
var agent: Dictionary
var scene: Dictionary
var queries: Array
var meshes: Dictionary
var label: Label
var camera: Camera3D
var checks: Array = []
var failures: Array = []
var results: Array = []
var trace: Array = []
var testing := false
var report := "user://scene.json"
var selected := 0
var serial := 0
var min_foot := 0.0
var sample_clock := 0.0

func v(a: Array) -> Vector3: return Vector3(a[0],a[1],a[2])
func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg == "--self-test": testing = true
		if arg.begins_with("--report="): report = arg.trim_prefix("--report=")
	scene = JSON.parse_string(FileAccess.get_file_as_string("res://generated/scene/scene.json"))
	agent = scene.navigation.agent; queries = scene.navigation.queries
	region = NavigationRegion3D.new(); add_child(region)
	meshes = Geometry.load_scene("res://generated/scene/scene.json",region)
	NavigationServer3D.map_set_cell_size(get_world_3d().navigation_map,.1)
	NavigationServer3D.map_set_cell_height(get_world_3d().navigation_map,.05)
	var mesh := NavigationMesh.new(); mesh.cell_size = .1; mesh.cell_height = .05
	mesh.agent_radius = agent.navigation_radius_m; mesh.agent_height = agent.navigation_height_m
	mesh.agent_max_climb = agent.max_step_m; mesh.agent_max_slope = agent.max_slope_degrees
	mesh.region_min_size = 1; mesh.region_merge_size = 0
	mesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	region.navigation_mesh = mesh; region.bake_navigation_mesh(false)
	nav = Nav.new(); add_child(nav); nav.configure(3,.3,2,25)
	actor = Motor.new(); actor.speed = 3; actor.floor_max_angle = deg_to_rad(agent.max_slope_degrees); actor.floor_snap_length = agent.max_step_m
	var collision := CollisionShape3D.new(); collision.shape = CapsuleShape3D.new(); collision.shape.radius = agent.radius_m; collision.shape.height = agent.height_m; actor.add_child(collision)
	var body := MeshInstance3D.new(); body.mesh = CapsuleMesh.new(); body.mesh.radius = agent.radius_m; body.mesh.height = agent.height_m
	var mat := StandardMaterial3D.new(); mat.albedo_color = Color(.1,.75,1); body.material_override = mat; actor.add_child(body); add_child(actor)
	camera = Camera3D.new(); camera.fov = 60; add_child(camera)
	var light := DirectionalLight3D.new(); light.rotation_degrees = Vector3(-70,-20,0); add_child(light)
	var canvas := CanvasLayer.new(); add_child(canvas); label = Label.new(); label.position = Vector2(18,16); label.add_theme_font_size_override("font_size",18); canvas.add_child(label)
	var row := HBoxContainer.new(); row.position = Vector2(18,100); canvas.add_child(row)
	for i in range(queries.size()):
		var button := Button.new(); button.text = queries[i].id; row.add_child(button); button.pressed.connect(func(): if not testing: select(i))
	var run := Button.new(); run.text = "Run route"; row.add_child(run); run.pressed.connect(func(): if not testing: start_route())
	var quit := Button.new(); quit.text = "Quit"; row.add_child(quit); quit.pressed.connect(func(): get_tree().quit())
	select(0)
	if testing: call_deferred("run_tests")

func select(index: int) -> void:
	selected = index; nav.clear(); actor.reset_motor(v(queries[index].start)+Vector3(0,agent.height_m/2+.03,0)); trace=[]; min_foot = INF
	var center := (v(queries[index].start)+v(queries[index].goal))/2
	camera.position = center+Vector3(12,18,18); camera.look_at(center)
func start_route() -> bool:
	serial += 1
	return nav.request("scene-%d" % serial,actor,v(queries[selected].goal),null,Vector3(0,-agent.height_m/2,0))
func _physics_process(delta: float) -> void:
	if not is_instance_valid(actor): return
	nav.step(delta); actor.move_wish = Vector2(nav.desired_velocity.x,nav.desired_velocity.z)/actor.speed
	if nav.busy():
		min_foot = minf(min_foot,actor.position.y-agent.height_m/2); sample_clock += delta
		if sample_clock >= .1:
			sample_clock = 0; trace.append([actor.position.x,actor.position.y-agent.height_m/2,actor.position.z])
	label.text = "Generated scene | Godot | %s | %s %s\nCapsule r=%.2fm h=%.2fm | nav r=%.2fm | slope %.0f deg\nGenerated geometry + native navigation + collision motor" % [queries[selected].id,nav.state,nav.reason if nav.last_error.is_empty() else nav.last_error,agent.radius_m,agent.height_m,agent.navigation_radius_m,agent.max_slope_degrees]
func check(ok: bool,name: String) -> void:
	checks.append(name)
	if not ok: failures.append(name)
func delay(seconds: float) -> void: await get_tree().create_timer(seconds).timeout
func projected(point: Vector3) -> bool:
	return NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map,point).distance_to(point) < .5
func screenshot(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(report+"-"+name+".png")
func run_tests() -> void:
	await delay(.4)
	check(meshes.size()==scene.meshes.size(),"all generated stable IDs instantiated")
	var matching := true
	for record in scene.meshes:
		if not meshes.has(record.id) or meshes[record.id].get_child_count()!=1: matching=false
	check(matching,"each generated mesh has native triangle collision")
	check(region.navigation_mesh.get_polygon_count()>0 and nav.ready_map(),"generated collision baked into native navigation")
	var capsule: CapsuleShape3D = actor.get_child(0).shape
	check(is_equal_approx(capsule.radius,agent.radius_m) and is_equal_approx(capsule.height,agent.height_m),"actual capsule uses specification dimensions")
	check(is_equal_approx(region.navigation_mesh.agent_radius,agent.navigation_radius_m) and is_equal_approx(region.navigation_mesh.agent_height,agent.navigation_height_m),"nav bake uses specification clearance")
	check(is_equal_approx(rad_to_deg(actor.floor_max_angle),agent.max_slope_degrees) and is_equal_approx(region.navigation_mesh.agent_max_slope,agent.max_slope_degrees),"motor and navigation share slope limit")
	check(is_equal_approx(region.navigation_mesh.agent_max_climb,agent.max_step_m),"navigation uses specification step limit")
	for index in range(queries.size()):
		select(index); await delay(.15)
		var q: Dictionary = queries[index]; var prefix: String = q.id+": "
		check(projected(v(q.start)),prefix+"start room has navigation")
		check(projected(v(q.goal)),prefix+"goal room has navigation")
		var started := Time.get_ticks_msec(); var accepted := start_route()
		var path := []
		for point in nav.path: path.append([point.x,point.y,point.z])
		check(accepted==q.expected_reachable,prefix+"native reachability matches case expectation")
		if q.expected_reachable:
			var elapsed := 0.0
			while nav.busy() and elapsed < 26: await delay(.05); elapsed += .05
			check(nav.state=="arrived" and (actor.position-Vector3(0,agent.height_m/2,0)).distance_to(v(q.goal))<.65,prefix+"collision motor reaches destination")
			check(trace.size()>10 and min_foot > -.15,prefix+"sampled trajectory remains supported")
			check(nav.desired_velocity==Vector3.ZERO,prefix+"arrival stops steering")
		else:
			check(nav.last_error=="unreachable" and not nav.busy(),prefix+"partial path cannot report success")
		results.append({"id":q.id,"expected":q.expected_reachable,"accepted":accepted,"state":nav.state,"reason":nav.reason,"error":nav.last_error,"seconds":(Time.get_ticks_msec()-started)/1000.0,"path":path,"trajectory":trace.duplicate(true),"end":[actor.position.x,actor.position.y-agent.height_m/2,actor.position.z]})
		if q.id in ["curve","ramp","narrow","broken"]: await screenshot(q.id)
	nav.clear(); check(nav.path.is_empty() and nav.desired_velocity==Vector3.ZERO,"scene cleanup releases navigation")
	var output := FileAccess.open(report,FileAccess.WRITE)
	output.store_string(JSON.stringify({"engine":Engine.get_version_info().string,"spec_sha256":scene.spec_sha256,"agent":agent,"checks":checks,"failures":failures,"cases":results,"input":"automated native navigation and collision movement; no human playtest"},"  ")); output.close()
	get_tree().quit(0 if failures.is_empty() else 1)
