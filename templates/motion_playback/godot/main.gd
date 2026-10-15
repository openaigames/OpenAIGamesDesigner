extends Node3D
## Example-owned input, state selection and interaction. No toolkit game rules.
const Motor = preload("res://addons/oagd/oagd_actor.gd")
const Playback = preload("res://addons/oagd_playback/oagd_playback.gd")
const Session = preload("res://addons/oagd/oagd_session.gd")
var actor: CharacterBody3D
var visual: Node3D
var skeleton: Skeleton3D
var motion: Node
var session: Node
var label: Label
var camera: Camera3D
var action_id := "action"
var action_locked := false
var was_air := false
var landed_until := 0.0
var elapsed := 0.0
var events: Array = []
var frames: Array = []
var transitions: Array = []
var last_state := ""
var testing := false
var output := ""
var completed_runs := 0
var marker_count := 0
var replacement := false
var recorder_every := 0
var capture_dir := ""
var capture_index := 0
var steps := {}
var failures: Array = []
var max_fps := 60
var asset_revision := ""
var review_view := "game"
var observed_bones := {}
var movement_speeds := {"walk":1.0,"run":2.5}
var locomotion_policy := {}
var scenario := "legacy"
var variable_fps := false
var paused := false
var smooth_velocity := Vector2.ZERO
var transition_at := 0.0
var turning_enabled := false
var turn_phase := "none"
var turn_clock := 0.0
var turn_angle := 0.0
var turn_start_yaw := 0.0
var turn_clip := ""
var layer_requests: Array = []
var layer_events: Array = []
var callback_cancel := false

func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--report="): output = arg.trim_prefix("--report="); testing = true
		if arg == "--replacement": replacement = true
		if arg.begins_with("--fps="): max_fps = int(arg.trim_prefix("--fps="))
		if arg.begins_with("--frames="): capture_dir = arg.trim_prefix("--frames=")
		if arg.begins_with("--scenario="): scenario = arg.trim_prefix("--scenario=")
		if arg == "--variable-fps": variable_fps = true
	Engine.physics_ticks_per_second = max_fps
	Engine.max_fps = max_fps
	if replacement: action_id = "action_v2"
	for pair in [["forward",KEY_W],["back",KEY_S],["left",KEY_A],["right",KEY_D],["run",KEY_SHIFT],["jump",KEY_SPACE],["action",KEY_E],["full_action",KEY_F],["cancel",KEY_Q],["restart",KEY_R],["pause",KEY_P]]:
		InputMap.add_action(pair[0])
		var key := InputEventKey.new(); key.physical_keycode = pair[1]; InputMap.action_add_event(pair[0],key)
	var light := DirectionalLight3D.new(); light.rotation_degrees = Vector3(-55,-25,0); light.light_energy = 1.5; add_child(light)
	var world := WorldEnvironment.new(); world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_COLOR; world.environment.background_color = Color("182332")
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR; world.environment.ambient_light_color = Color.WHITE; world.environment.ambient_light_energy = 0.55; add_child(world)
	var ground := StaticBody3D.new(); var shape := CollisionShape3D.new(); var box := BoxShape3D.new(); box.size = Vector3(80,.2,80); shape.shape = box; ground.position.y = -.1; ground.add_child(shape); add_child(ground)
	var floor_mesh := MeshInstance3D.new(); var mesh := BoxMesh.new(); mesh.size = box.size; floor_mesh.mesh = mesh
	var mat := StandardMaterial3D.new(); mat.albedo_color = Color("35445a"); floor_mesh.material_override = mat; ground.add_child(floor_mesh)
	for x in range(-9,10):
		for z in range(-9,10):
			if (x+z)%2 == 0:
				var tile := MeshInstance3D.new(); var tile_mesh := BoxMesh.new(); tile_mesh.size = Vector3(1,.01,1); tile.mesh = tile_mesh; tile.position = Vector3(x,.006,z)
				var tile_mat := StandardMaterial3D.new(); tile_mat.albedo_color = Color("40516a"); tile.material_override = tile_mat; add_child(tile)
	actor = Motor.new(); actor.name = "Player"; actor.speed = 1.0; actor.jump_speed = 4.5; actor.gravity = 16
	var capsule := CollisionShape3D.new(); var capsule_shape := CapsuleShape3D.new(); capsule_shape.radius = .3; capsule_shape.height = 1.8; capsule.shape = capsule_shape; capsule.position.y = .9; actor.add_child(capsule)
	add_child(actor)
	# Main owns simulation order so animation always sees the completed physics step.
	actor.set_physics_process(false)
	var binding: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://bindings.json"))
	asset_revision = binding.revision
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--view="): review_view = arg.trim_prefix("--view=")
	if not replacement: action_id = binding.get("default_action", "action")
	replacement = action_id == "action_v2"
	visual = load("res://" + str(binding.get("character_scene", "character.tscn"))).instantiate(); actor.add_child(visual)
	visual.rotation.y = PI # Authored Blender -Y forward imports as glTF +Z.
	skeleton = visual.find_children("*", "Skeleton3D", true, false)[0]
	for role in ["dst_root","dst_foot_L","dst_foot_R","dst_hand_R","dst_upperarm_R","dst_forearm_R","dst_spine","dst_head","dst_upperarm_L","dst_forearm_L","dst_hand_L"]:
		var name: String = binding.get("observation_bones", {}).get(role, role)
		if skeleton.find_bone(name) < 0: push_error("Missing observed bone: " + name); get_tree().quit(7); return
		observed_bones[role] = name
	for role in binding.get("turn_observation_bones", {}):
		var name: String = binding.turn_observation_bones[role]
		if skeleton.find_bone(name) < 0: push_error("Missing turn observation bone"); get_tree().quit(7); return
		observed_bones[role] = name
	movement_speeds = binding.get("movement_speeds_mps", movement_speeds)
	locomotion_policy = binding.get("locomotion", {})
	turning_enabled = binding.has("turning")
	motion = Playback.new(); add_child(motion)
	var definitions := {}
	for row in binding.clips: definitions[row.id] = row
	if not motion.configure(visual.get_node("PlaybackTree"), definitions, binding.get("layers", {})): push_error("Invalid bindings"); get_tree().quit(2); return
	if motion.layers != null: motion.layers.event.connect(_layer_event)
	if not locomotion_policy.is_empty() and not motion.configure_locomotion(movement_speeds): push_error("Invalid locomotion"); get_tree().quit(2); return
	motion.marker.connect(_marker); motion.ended.connect(_ended); motion.select("locomotion" if motion.locomotion_enabled else "idle")
	session = Session.new(); add_child(session); session.restarted.connect(_reset)
	camera = Camera3D.new(); camera.position = Vector3(4,3.1,5); add_child(camera); camera.look_at(Vector3(0,.9,0)); camera.current = true
	var layer := CanvasLayer.new(); add_child(layer); label = Label.new(); label.position = Vector2(22,20); label.add_theme_font_size_override("font_size",22); layer.add_child(label)
	if not capture_dir.is_empty(): DirAccess.make_dir_recursive_absolute(capture_dir)

func _marker(action: StringName, run: int, name: StringName) -> void:
	# Actual gameplay feedback: one completed gesture lights the counter once.
	if action == action_id and action_locked and name == &"pulse": marker_count += 1
	events.append({"t":elapsed,"action":action,"run":run,"name":name,"kind":"marker","position_s":motion.position_s})
func _ended(action: StringName, run: int, reason: StringName) -> void:
	events.append({"t":elapsed,"action":action,"run":run,"name":reason,"kind":"ended","position_s":motion.position_s})
	if action == action_id:
		action_locked = false
		if reason == &"completed": completed_runs += 1
func _reset(_generation: int) -> void:
	action_locked = false; actor.reset_motor(Vector3.ZERO); visual.rotation = Vector3(0,PI,0)
	paused = false; callback_cancel = false; smooth_velocity = Vector2.ZERO
	turn_phase = "none"; turn_clock = 0; turn_angle = 0
	if motion.locomotion_enabled: motion.set_locomotion_speed(0)
	motion.reset("locomotion" if motion.locomotion_enabled else "idle"); was_air = false; landed_until = 0
func trigger() -> void:
	if motion.layers != null:
		if not paused: layer_request("upper", "upper_wave")
		return
	if not paused and turn_phase == "none" and not action_locked and actor.is_on_floor(): action_locked = true; motion.select(action_id)
func cancel() -> void:
	if motion.layers != null:
		motion.layers.cancel("upper"); motion.layers.cancel("full"); return
	if action_locked: motion.select("locomotion" if motion.locomotion_enabled else "idle"); action_locked = false
func once(key: String, at: float, callback: Callable) -> void:
	if elapsed >= at and not steps.has(key): steps[key] = true; callback.call()

func _physics_process(delta: float) -> void:
	if not is_instance_valid(motion): return
	if scenario.contains("hitch") and elapsed >= 17 and not steps.has("hitch"):
		steps["hitch"] = true; Engine.physics_ticks_per_second = 1
	elif scenario.contains("hitch") and delta > .5: Engine.physics_ticks_per_second = max_fps
	elapsed += delta
	var wish := Input.get_vector("left","right","forward","back")
	var fast := Input.is_action_pressed("run")
	if testing and scenario.begins_with("layers"):
		var command := layer_input(); wish = command.wish; fast = command.fast
	elif testing and scenario in ["locomotion", "turning"]:
		var command := turning_input() if scenario == "turning" else locomotion_input()
		wish = command.wish; fast = command.fast
	elif testing:
		wish = Vector2.ZERO
		if elapsed >= 1 and elapsed < 2.8: wish = Vector2(0,-1)
		if elapsed >= 2.8 and elapsed < 4.2: wish = Vector2(1,0); fast = true
		once("jump",4.4,func():actor.request_jump())
		once("complete",5.7,trigger)
		once("cancel_start",7.3,trigger)
		once("cancel",7.55,cancel)
		once("replay",8.1,trigger)
		once("pause",8.4,func():motion.set_rate(0))
		once("resume",8.8,func():motion.set_rate(2))
		once("normal",9.6,func():motion.set_rate(1))
		once("reset_active",10.0,trigger)
		once("restart",10.2,func():session.restart())
		once("after_reset",10.7,trigger)
	else:
		if not action_locked and turn_phase == "none" and Input.is_action_just_pressed("jump"): actor.request_jump()
		if Input.is_action_just_pressed("action"): trigger()
		if Input.is_action_just_pressed("full_action") and motion.layers != null and not paused: layer_request("full", "upper_alt", 5)
		if Input.is_action_just_pressed("cancel"): cancel()
		if Input.is_action_just_pressed("restart"): session.restart()
		if Input.is_action_just_pressed("pause"): paused = not paused
	if motion.layers != null: action_locked = motion.layers.channels.full.active or motion.layers.channels.full.weight > .000001
	actor.move_wish = Vector2.ZERO if action_locked else wish
	if turning_enabled and not paused: update_turn(wish, delta)
	if turn_phase != "none": actor.move_wish = Vector2.ZERO
	actor.speed = float(movement_speeds.run if fast else movement_speeds.walk)
	if not paused:
		if motion.locomotion_enabled:
			var target: Vector2 = actor.move_wish.limit_length() * actor.speed
			# Keep the motor ceiling stable while decelerating from run to walk.
			actor.speed = float(movement_speeds.run)
			var acceleration: float = locomotion_policy.deceleration_mps2 if target.length() < smooth_velocity.length() or target.dot(smooth_velocity) < 0 else locomotion_policy.acceleration_mps2
			smooth_velocity = smooth_velocity.move_toward(target, acceleration * delta)
			actor.move_wish = smooth_velocity / actor.speed
		actor._physics_process(delta)
		if motion.locomotion_enabled:
			smooth_velocity = Vector2(actor.velocity.x, actor.velocity.z)
			motion.set_locomotion_speed(smooth_velocity.length())
			if turn_phase == "none" and smooth_velocity.length() > .02: visual.rotation.y = rotate_toward(visual.rotation.y, PI + atan2(-smooth_velocity.x,-smooth_velocity.y), deg_to_rad(float(locomotion_policy.turn_speed_deg_s)) * delta)
		elif wish.length() > .01 and not action_locked:
			visual.rotation.y = lerp_angle(visual.rotation.y, PI + atan2(-wish.x,-wish.y), minf(1,delta*12))
	if not action_locked and not paused and turn_phase != "pivot":
		if not actor.is_on_floor():
			motion.select("jump" if actor.velocity.y > 0 else "fall"); was_air = true
		else:
			if was_air: landed_until = elapsed + .3; was_air = false
			if elapsed < landed_until: motion.select("land")
			elif motion.locomotion_enabled: motion.select("locomotion")
			elif wish.length() > .01: motion.select("run" if fast else "walk")
			else: motion.select("idle")
	if not paused: motion.advance(delta)
	if turn_phase == "pivot" and not paused:
		visual.rotation.y = turn_start_yaw - deg_to_rad(turn_angle * turn_fraction(motion.position_s))
	if last_state != motion.current:
		transitions.append({"t":elapsed,"from":last_state,"to":motion.current}); last_state = motion.current; transition_at = elapsed
	label.text = "OAGD / GODOT / PLAYABLE MOTION\nWASD move   Shift run   Space jump   E upper   F full   Q cancel   R reset   P pause\nState: %s   Clip: %.2fs   Events: %d   Revision: %s\nFront = character face / toes" % [motion.current,motion.position_s,marker_count,asset_revision]
	if motion.layers != null: label.text += "\nUpper: %.2f  Full: %.2f  Layer events: %d" % [motion.layers.channels.upper.weight,motion.layers.channels.full.weight,layer_events.size()]
	camera.position = actor.position + Vector3(4,3.1,5); camera.look_at(actor.position+Vector3(0,.9,0))
	var forward := (visual.global_basis * Vector3.BACK).normalized()
	if review_view in ["side", "front"]:
		camera.position = actor.position + (forward.cross(Vector3.UP) if review_view == "side" else forward) * 3.4 + Vector3.UP * 1.1
		camera.look_at(actor.position + Vector3.UP * .95)
	if testing:
		var bones := {}
		for name in observed_bones:
			var pose := skeleton.global_transform*skeleton.get_bone_global_pose(skeleton.find_bone(observed_bones[name])); var q := pose.basis.get_rotation_quaternion()
			bones[name] = {"p":[pose.origin.x,pose.origin.y,pose.origin.z],"q":[q.x,q.y,q.z,q.w]}
		frames.append({"t":elapsed,"dt":delta,"paused":paused,"turn_phase":turn_phase,"turn_angle_deg":turn_angle,"wish":[wish.x,wish.y],"speed_mps":Vector2(actor.velocity.x,actor.velocity.z).length(),"move_weight":motion.move_weight,"run_weight":motion.run_weight,"cycle_hz":motion.cycle_hz,"clip_times":motion.locomotion_times(),"transition_age_s":elapsed-transition_at,"state":motion.current,"position_s":motion.position_s,"rate":motion.rate,"actor":[actor.position.x,actor.position.y,actor.position.z],"forward":[forward.x,forward.y,forward.z],"floor":actor.is_on_floor(),"bones":bones})
		if motion.layers != null: frames[-1]["layers"] = motion.layers.snapshot()
		if not capture_dir.is_empty() and Engine.get_physics_frames() % maxi(1,max_fps/15) == 0: capture.call_deferred()
		if variable_fps: Engine.physics_ticks_per_second = 30 if int(elapsed*2)%2 == 0 else 60; Engine.max_fps = Engine.physics_ticks_per_second
		if elapsed >= (40.0 if scenario == "turning" or scenario.begins_with("layers") else 22.0 if scenario == "locomotion" else 12.4):
			set_physics_process(false); finish.call_deferred()

func capture() -> void:
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	image.save_png(capture_dir.path_join("frame_%05d.png" % capture_index)); capture_index += 1
func finish() -> void:
	var report := {"engine":"godot","scenario":scenario,"variable_fps":variable_fps,"engine_version":Engine.get_version_info().string,"fps":max_fps,"revision":asset_revision,"action_id":action_id,"view":review_view,"observation_bones":observed_bones,"movement_speeds_mps":movement_speeds,"input":"scripted movement wishes and project action handlers; not human play","method":"natural AnimationTree advance + CharacterBody3D physics; no seek","events":events,"transitions":transitions,"frames":frames,"marker_count":marker_count,"completed_runs":completed_runs,"generation":session.generation,"capture_count":capture_index}
	if motion.layers != null:
		report["layer_events"] = layer_events; report["layer_requests"] = layer_requests; report["layer_faults"] = motion.layers.faults
		report["method"] = "native AnimationTree base and filtered upper/full blend nodes; bank reset only on accepted request"
	FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify(report))
	get_tree().quit()

func _layer_event(data: Dictionary) -> void:
	var e := data.duplicate(true); e["t"] = elapsed; layer_events.append(e)
	if callback_cancel and data.channel == "upper" and data.kind == "marker" and data.name == "pulse":
		callback_cancel = false; motion.layers.cancel("upper", "callback_cancelled")

func layer_request(channel: String, action: String, priority := 0, weight := 1.0, speed := 1.0, restart := true) -> void:
	if scenario.ends_with("baseline"): return
	var allowed: bool = channel != "full" or (turn_phase == "none" and actor.is_on_floor() and Vector2(actor.velocity.x,actor.velocity.z).length() < .02)
	var accepted: bool = allowed and motion.layers.play(channel, action, priority, weight, speed, restart)
	layer_requests.append({"t":elapsed,"op":"play","channel":channel,"action":action,"priority":priority,"weight":weight,"rate":speed,"restart":restart,"accepted":accepted,"reason":motion.layers.rejection if allowed else "project_motion","run":motion.layers.channels[channel].run})

func layer_change(op: String, channel: String, value := 0.0) -> void:
	if scenario.ends_with("baseline"): return
	var accepted := false
	if op == "rate": accepted = motion.layers.set_rate(channel, value)
	elif op == "weight": accepted = motion.layers.set_weight(channel, value)
	elif op == "cancel": accepted = motion.layers.cancel(channel)
	layer_requests.append({"t":elapsed,"op":op,"channel":channel,"value":value,"accepted":accepted,"run":motion.layers.channels[channel].run})

func locomotion_input() -> Dictionary:
	var wish := Vector2.ZERO; var fast := false
	if elapsed >= 1 and elapsed < 5.5: wish = Vector2(0,-1); fast = elapsed >= 3
	elif elapsed >= 5.5 and elapsed < 6.4: wish = Vector2(0,-.65); fast = true
	elif elapsed >= 7.4 and elapsed < 8.4: wish = Vector2(0,-1)
	elif elapsed >= 8.4 and elapsed < 9.2: wish = Vector2(0,1)
	elif elapsed >= 9.2 and elapsed < 9.5: wish = Vector2(1,0)
	elif elapsed >= 9.5 and elapsed < 9.8: wish = Vector2(-1,0)
	elif elapsed >= 9.8 and elapsed < 10.4: wish = Vector2(0,-1)
	elif elapsed >= 11.4 and elapsed < 13.3: wish = Vector2(1,-1).normalized(); fast = true
	elif elapsed >= 13.3 and elapsed < 15: wish = Vector2(0,-1)
	elif elapsed >= 18 and elapsed < 19: wish = Vector2(0,-1); fast = int(elapsed*10)%2 == 0
	once("jump",11.6,func():actor.request_jump())
	once("pause",14.0,func():paused=true)
	once("resume",14.5,func():paused=false)
	once("complete",16.0,trigger)
	once("cancel_start",17.4,trigger)
	once("cancel",17.65,cancel)
	once("restart",19.3,func():session.restart())
	once("after_reset",20.0,trigger)
	return {"wish":wish,"fast":fast}

func turn_fraction(time: float) -> float:
	var count := absf(turn_angle) / 45.0
	var u := (time - .2) / .6
	if u <= 0: return 0.0
	if u >= count: return 1.0
	var step := floorf(u)
	return (step + smoothstep(.1, .9, u-step)) / count

func update_turn(wish: Vector2, delta: float) -> void:
	if turn_phase == "pivot":
		var u: float = (motion.position_s - .2) / .6
		var at_step: bool = u > .92 and absf(u-roundf(u)) < .075
		var intended_yaw := turn_start_yaw - deg_to_rad(turn_angle)
		var changed := wish.length() <= .1 or absf(rad_to_deg(wrapf(intended_yaw - (PI + atan2(-wish.x,-wish.y)), -PI, PI))) > 30
		if motion.finished or (at_step and changed): turn_phase = "recover"; turn_clock = 0; motion.select("locomotion")
		return
	if turn_phase == "recover":
		turn_clock += delta
		if turn_clock >= .2: turn_phase = "none"
		return
	if action_locked or not actor.is_on_floor(): turn_phase = "none"; return
	var error := rad_to_deg(wrapf(visual.rotation.y - (PI + atan2(-wish.x,-wish.y)), -PI, PI)) if wish.length() > .1 else 0.0
	if absf(error) < 30: turn_phase = "none"; turn_clock = 0; return
	if turn_phase == "none": turn_phase = "brake"; turn_clock = 0
	if smooth_velocity.length() > .005: turn_clock = 0; return
	turn_phase = "settle"; turn_clock += delta
	if turn_clock < .2: return
	var magnitude := 180 if absf(error) >= 135 else 90 if absf(error) >= 67.5 else 45
	turn_angle = magnitude * (1 if error > 0 else -1)
	turn_start_yaw = visual.rotation.y
	turn_clip = "turn_%s_%d" % ["r" if turn_angle > 0 else "l", magnitude]
	turn_phase = "pivot"; motion.select(turn_clip)

func turning_input() -> Dictionary:
	var wish := Vector2.ZERO; var fast := false
	if elapsed >= 1 and elapsed < 3: wish = Vector2(0,-1)
	elif elapsed >= 3 and elapsed < 7: wish = Vector2(1,0)
	elif elapsed >= 7 and elapsed < 11: wish = Vector2(0,-1); fast = true
	elif elapsed >= 11 and elapsed < 16: wish = Vector2(0,1); fast = true
	elif elapsed >= 16 and elapsed < 21: wish = Vector2(0,-1)
	elif elapsed >= 21 and elapsed < 24: wish = Vector2(1,-1).normalized()
	elif elapsed >= 24 and elapsed < 28: wish = Vector2(0,-1)
	elif elapsed >= 28 and elapsed < 28.4: wish = Vector2(0,1)
	elif elapsed >= 28.4 and elapsed < 28.7: wish = Vector2(1,0)
	elif elapsed >= 28.7 and elapsed < 29: wish = Vector2(-1,0)
	elif elapsed >= 29 and elapsed < 34: wish = Vector2(0,-1)
	once("pause",12.0,func():paused=true)
	once("resume",12.5,func():paused=false)
	once("gesture",35,trigger)
	once("restart",37,func():session.restart())
	once("after_reset",38,trigger)
	return {"wish":wish,"fast":fast}

# Layer scripted cases: generated from the recorded layer-case.json.
func layer_input() -> Dictionary:
	var wish := Vector2.ZERO; var fast := false
	if (elapsed >= 1 and elapsed < 10) or (elapsed >= 15 and elapsed < 21): wish = Vector2(0,-1); fast = elapsed >= 4 and elapsed < 7
	elif elapsed >= 21 and elapsed < 25: wish = Vector2(1,0)
	once("layer_0",1.6,func():layer_request("upper","upper_wave",1,1,1,true))
	once("layer_1",3.2,func():layer_request("upper","upper_loop",1,0.35,1,true))
	once("layer_2",4.0,func():layer_change("weight","upper",1))
	once("layer_3",4.7,func():layer_change("rate","upper",2))
	once("layer_4",5.6,func():paused=true)
	once("layer_5",6.1,func():paused=false)
	once("layer_6",6.4,func():layer_change("rate","upper",0))
	once("layer_7",6.9,func():layer_change("rate","upper",0.5))
	once("layer_8",7.5,func():layer_change("rate","upper",4))
	once("layer_9",8.3,func():layer_change("cancel","upper",0))
	once("layer_10",8.55,func():layer_request("upper","upper_wave",1,1,4,true))
	once("layer_11",9.0,func():layer_request("upper","upper_alt",1,1,4,true))
	once("layer_12",9.1,func():layer_request("upper","upper_alt",1,1,4,false))
	once("layer_13",9.4,func():layer_request("upper","upper_wave",3,1,1,true))
	once("layer_14",9.43,func():layer_request("upper","upper_alt",5,1,1,true))
	once("layer_15",9.6,func():layer_request("upper","upper_alt",1,1,1,true))
	once("layer_16",9.8,func():layer_request("upper","upper_alt",4,1,1,true))
	once("layer_17",10.8,func():layer_request("upper","upper_loop",4,1,1,true))
	once("layer_18",11.4,func():layer_request("full","upper_alt",5,1,1,true))
	once("layer_19",11.7,func():layer_request("upper","upper_wave",20,1,1,true))
	once("layer_20",13.0,func():layer_request("full","upper_wave",5,1,0.5,true))
	once("layer_21",13.4,func():layer_change("cancel","full",0))
	once("layer_22",13.45,func():layer_request("upper","upper_wave",20,1,1,true))
	once("layer_23",13.7,func():layer_request("upper","upper_wave",1,1,1,true))
	once("layer_24",14.0,func():session.restart())
	once("layer_25",14.3,func():layer_request("upper","upper_wave",1,1,1,true))
	once("layer_26",15.2,func():layer_request("upper","upper_loop",1,1,1,true))
	once("layer_27",16.0,func():layer_change("weight","upper",0))
	once("layer_28",16.5,func():layer_request("upper","upper_loop",1,1,4,true))
	once("layer_29",18.5,func():layer_change("cancel","upper",0))
	once("layer_30",19.0,func():callback_cancel=true)
	once("layer_31",19.0,func():layer_request("upper","upper_wave",1,1,1,true))
	once("layer_32",21.4,func():layer_request("upper","upper_wave",1,1,1,true))
	once("layer_33",22.0,func():layer_request("full","upper_alt",5,1,1,true))
	once("layer_34",25.5,func():actor.request_jump())
	once("layer_36",25.7,func():layer_request("upper","upper_wave",1,1,1,true))
	once("layer_37",25.8,func():layer_request("full","upper_alt",5,1,1,true))
	once("layer_38",27.8,func():layer_request("upper","upper_loop",1,1,1,true))
	once("layer_39",28.0,func():session.restart())
	once("layer_40",29.0,func():layer_request("upper","upper_wave",1,0.5,1,true))
	once("layer_41",30.0,func():layer_change("weight","upper",1))
	once("layer_42",30.4,func():layer_request("upper","upper_alt",1,1,4,true))
	once("layer_43",31.2,func():layer_request("full","upper_wave",1,1,1,true))
	once("layer_44",31.45,func():layer_request("full","upper_alt",2,1,1,true))
	once("layer_45",31.5,func():layer_request("full","upper_wave",1,1,1,true))
	once("layer_46",32.7,func():layer_change("cancel","full",0))
	once("layer_47",33.0,func():layer_request("upper","upper_loop",1,0.35,2,true))
	once("layer_48",34.0,func():session.restart())
	once("layer_49",35.0,func():layer_request("upper","upper_wave",1,1,1,true))
	once("layer_50",36.8,func():layer_request("full","full_tuck",2,1,0.5,true))
	return {"wish":wish,"fast":fast}
