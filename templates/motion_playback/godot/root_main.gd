extends Node3D
## Project-owned root-motion example and reproducible native scenarios.
const Playback = preload("res://addons/oagd_playback/oagd_playback.gd")
const RootMotor = preload("res://addons/oagd_playback/oagd_root_motion.gd")
const CASES = ["dash","roll","diagonal","wall","wall_diagonal","slow","fast","variable","pause","cancel","reentry","restart","controller_takeover","root_takeover"]
var actor: CharacterBody3D
var visual: Node3D
var skeleton: Skeleton3D
var motion: Playback
var motor: RootMotor
var wall: StaticBody3D
var camera: Camera3D
var label: Label
var output := ""
var capture := ""
var view := "game"
var fps := 60
var frame_index := 0
var case_index := -1
var elapsed := 0.0
var case_time := 0.0
var steps := {}
var rows: Array = []
var events: Array = []
var observed := {}
var paused := false

func box(at: Vector3, size: Vector3, color: Color) -> StaticBody3D:
	var body := StaticBody3D.new(); body.position = at
	var shape := CollisionShape3D.new(); var resource := BoxShape3D.new(); resource.size = size; shape.shape = resource; body.add_child(shape)
	var mesh := MeshInstance3D.new(); var cube := BoxMesh.new(); cube.size = size; mesh.mesh = cube
	var mat := StandardMaterial3D.new(); mat.albedo_color = color; mesh.material_override = mat; body.add_child(mesh); add_child(body)
	return body

func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--report="): output = arg.trim_prefix("--report=")
		if arg.begins_with("--frames="): capture = arg.trim_prefix("--frames=")
		if arg.begins_with("--view="): view = arg.trim_prefix("--view=")
		if arg.begins_with("--fps="): fps = int(arg.trim_prefix("--fps="))
	Engine.physics_ticks_per_second = fps; Engine.max_fps = fps
	if not capture.is_empty(): DirAccess.make_dir_recursive_absolute(capture)
	var light := DirectionalLight3D.new(); light.rotation_degrees = Vector3(-55,-25,0); light.light_energy = 1.5; add_child(light)
	var world := WorldEnvironment.new(); world.environment = Environment.new(); world.environment.background_mode = Environment.BG_COLOR; world.environment.background_color = Color("182332"); world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR; world.environment.ambient_light_color = Color.WHITE; world.environment.ambient_light_energy = .6; add_child(world)
	box(Vector3(0,-.1,0),Vector3(40,.2,40),Color("35445a"))
	wall = box(Vector3(0,1,-1.7),Vector3(12,2,.2),Color("c48638"))
	actor = CharacterBody3D.new(); actor.name = "RootPlayer"; add_child(actor)
	var shape := CollisionShape3D.new(); var capsule := CapsuleShape3D.new(); capsule.radius = .35; capsule.height = 1.8; shape.shape = capsule; shape.position.y = .9; actor.add_child(shape)
	var binding: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://bindings.json"))
	visual = load("res://" + binding.get("character_scene","character.tscn")).instantiate(); actor.add_child(visual); visual.rotation.y = PI
	skeleton = visual.find_children("*","Skeleton3D",true,false)[0]; observed = binding.observation_bones
	motion = Playback.new(); add_child(motion)
	var definitions := {}
	for row in binding.clips: definitions[row.id] = row
	if not motion.configure(visual.get_node("PlaybackTree"),definitions,{},binding.root_motion): push_error("Root binding rejected"); get_tree().quit(2); return
	motor = RootMotor.new()
	if not motor.configure(motion,actor,skeleton): get_tree().quit(3); return
	motion.select(&"idle")
	motion.marker.connect(func(a,g,n): events.append({"case":current_case(),"t":case_time,"action":a,"run":g,"kind":"marker","name":n}))
	motion.ended.connect(func(a,g,n): events.append({"case":current_case(),"t":case_time,"action":a,"run":g,"kind":"ended","name":n}))
	camera = Camera3D.new(); add_child(camera); camera.current = true
	var canvas := CanvasLayer.new(); add_child(canvas); label = Label.new(); label.position = Vector2(20,20); label.add_theme_font_size_override("font_size",20); canvas.add_child(label)
	next_case()

func current_case() -> String:
	return CASES[case_index] if case_index >= 0 and case_index < CASES.size() else "interactive"
func next_case() -> void:
	case_index += 1; case_time = 0; steps.clear(); paused = false; motor.cancel(); motion.set_rate(1)
	actor.position = Vector3.ZERO; actor.velocity = Vector3.ZERO; actor.rotation = Vector3.ZERO
	var name := current_case()
	if name.contains("diagonal"): actor.rotation.y = -PI / 4
	wall.collision_layer = 1 if name.begins_with("wall") else 0; wall.visible = wall.collision_layer != 0
func once(key: String, at: float, call: Callable) -> void:
	if case_time >= at and not steps.has(key): steps[key] = true; call.call()
func start(action: StringName = &"dash", restart := false) -> void:
	var ok := motor.start(action,restart)
	events.append({"case":current_case(),"t":case_time,"kind":"request","action":action,"ok":ok,"restart":restart})
func normalize(v: Vector3) -> Array: return [-v.z,v.x,v.y]
func _physics_process(delta: float) -> void:
	if motor == null: return
	elapsed += delta; case_time += delta
	motor.prepare_step()
	var name := current_case()
	if not output.is_empty():
		once("start",.2,func():
			motion.set_rate(.5 if name == "slow" else 2.0 if name == "fast" else 1.0)
			start(&"roll" if name == "roll" else &"dash"))
		if name == "variable":
			once("rate",.5,func(): motion.set_rate(.5)); once("rate2",1.1,func(): motion.set_rate(2))
		if name == "pause":
			once("pause",.5,func(): motion.set_rate(0)); once("resume",1.0,func(): motion.set_rate(1))
		if name in ["cancel","reentry"]: once("cancel",.55,func(): motor.cancel())
		if name == "reentry": once("again",.85,func(): start())
		if name == "restart": once("restart",.55,func(): start(&"dash",true))
		if name.begins_with("wall"): once("wall_off",1.6,func(): wall.collision_layer = 0; wall.visible = false)
	else:
		if Input.is_physical_key_pressed(KEY_E) and not motor.active: start()
		if Input.is_physical_key_pressed(KEY_F) and not motor.active: start(&"roll")
		if Input.is_physical_key_pressed(KEY_Q): motor.cancel()
	var wish := Vector3.ZERO
	if not output.is_empty():
		if motor.active: wish = Vector3(0,0,-3) # deliberately competing controller input
		elif name == "controller_takeover" and case_time >= 1.5 and case_time < 2.0: wish = Vector3(0,0,-1)
		elif name == "root_takeover" and case_time < .2: wish = Vector3(0,0,-1)
	else: wish = Vector3(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),0,float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W))).normalized()
	if not motor.active: motion.select(&"walk" if wish.length() > 0 else &"idle")
	motor.step(delta,wish)
	var bones := {}
	for role in observed:
		var pose := skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone(observed[role])); bones[role] = normalize(pose.origin)
	rows.append({"case":name,"t":case_time,"dt":delta,"actor":normalize(actor.position),"requested":normalize(motor.requested),"actual":normalize(motor.actual),"active":motor.active,"state":motion.current,"clock":motion.position_s,"rate":motion.rate,"generation":motion.generation,"bones":bones})
	var offset := Vector3(4,2.7,4)
	if view == "side": offset = Vector3(4,1.4,0)
	if view == "front": offset = Vector3(0,1.4,-4)
	camera.position = actor.position + offset; camera.look_at(actor.position + Vector3(0,.85,0))
	label.text = "Root motion | " + name + "\nE dash / F roll / Q cancel / WASD move\nowner: " + ("animation" if motor.active else "controller") + "  clock %.2f  rate %.1f\nactual %.3f m / extracted %.3f m" % [motion.position_s,motion.rate,motor.actual.length(),motor.requested.length()]
	if not capture.is_empty() and frame_index % 12 == 0: capture_frame.call_deferred(frame_index)
	frame_index += 1
	if not output.is_empty() and case_time >= 3.0:
		if case_index + 1 == CASES.size():
			FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify({"schema":"oagd.root-runtime/1","engine":Engine.get_version_info().string,"frames":rows,"events":events},"\t")); get_tree().quit()
		else: next_case()
func capture_frame(index: int) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(capture.path_join("frame_%05d.png" % index))
