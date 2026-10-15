extends Node3D
const Nav = preload("res://addons/oagd/oagd_navigation.gd")
const Motor = preload("res://addons/oagd/oagd_actor.gd")
const Router = preload("res://addons/oagd/oagd_input.gd")
const Behavior = preload("res://npc_behavior.gd")
var nav: Node3D
var actor: CharacterBody3D
var target: CharacterBody3D
var region: NavigationRegion3D
var blocker: StaticBody3D
var router: Node
var brain = Behavior.new()
var label: Label
var profile: Dictionary
var testing := false
var report := "user://navigation.json"
var events: Array = []
var checks: Array = []
var failures: Array = []
var automatic := true
var frozen := false
var max_detour := 0.0
var serial := 0
var callback_mode := false
var callback_rejected := false
const HOME = Vector3(-5,.9,-3)
const DEST = Vector3(5,0,-3)

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for a in OS.get_cmdline_user_args():
		if a == "--self-test": testing = true
		if a.begins_with("--report="): report = a.trim_prefix("--report=")
	var parsed = JSON.parse_string(FileAccess.get_file_as_string("res://navigation-profile.json"))
	if not valid_profile(parsed): get_tree().quit(2); return
	profile = parsed
	nav = Nav.new(); add_child(nav); nav.lifecycle.connect(on_event)
	if not nav.configure(profile.speed_mps,profile.arrival_m,profile.blocked_seconds,profile.deadline_seconds,profile.repath_seconds): get_tree().quit(2); return
	router = Router.new(); add_child(router)
	if router.configure(JSON.parse_string(FileAccess.get_file_as_string("res://input-profile.json"))) != "": get_tree().quit(2); return
	router.action_changed.connect(on_action)
	router.pause_changed.connect(func(p: bool): nav.set_suspended(p); actor.move_wish = Vector2.ZERO; actor.velocity = Vector3.ZERO; get_tree().paused = p)
	region = NavigationRegion3D.new(); add_child(region)
	box(region,Vector3(0,-.5,0),Vector3(20,1,16),Color(.2,.27,.32))
	box(region,Vector3(0,1,0),Vector3(1,2,8),Color(.5,.3,.15))
	box(region,Vector3(14,-.5,0),Vector3(4,1,4),Color(.3,.3,.4))
	var mesh := NavigationMesh.new(); mesh.cell_size = .25; mesh.region_min_size = 1; mesh.region_merge_size = 0; mesh.agent_radius = .5; mesh.agent_height = 2.0; mesh.cell_height = .25; mesh.agent_max_climb = .25; mesh.agent_max_slope = 40
	mesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS; region.navigation_mesh = mesh
	region.bake_navigation_mesh(false)
	actor = character(HOME,Color(.05,.7,1)); target = character(Vector3(-7,.9,5),Color(1,.75,.1)); target.set_meta("detectable",not testing)
	brain.setup(nav,actor,target,profile)
	var cam := Camera3D.new(); cam.position = Vector3(10,16,15); cam.fov = 60; add_child(cam); cam.look_at(Vector3(2,0,0))
	var light := DirectionalLight3D.new(); light.rotation_degrees = Vector3(-70,-20,0); add_child(light)
	var canvas := CanvasLayer.new(); add_child(canvas); label = Label.new(); label.position = Vector2(18,16); label.add_theme_font_size_override("font_size",19); canvas.add_child(label)
	var row := HBoxContainer.new(); row.position = Vector2(18,135); canvas.add_child(row)
	for title in ["Start patrol", "Toggle blocker", "Reset NPC", "Pause / resume", "Quit"]:
		var button := Button.new(); button.text = title; row.add_child(button); button.pressed.connect(func(): choose(title))
	if testing: automatic = false; call_deferred("run_tests")
	else: await get_tree().physics_frame; await get_tree().physics_frame; brain.start()

func valid_profile(p) -> bool:
	if not p is Dictionary or p.get("schema") != 1: return false
	for k in ["speed_mps","arrival_m","blocked_seconds","deadline_seconds","repath_seconds","detection_m","loss_seconds","search_seconds"]:
		if not (p.get(k) is int or p.get(k) is float) or not is_finite(p[k]) or p[k] <= 0: return false
	if not p.get("patrol_points") is Array or p.patrol_points.is_empty() or p.patrol_points.size() > 64: return false
	for v in p.patrol_points:
		if not v is Array or v.size() != 3: return false
		for n in v:
			if not (n is int or n is float) or not is_finite(n): return false
	return true
func box(parent: Node3D, pos: Vector3, size: Vector3, color: Color) -> StaticBody3D:
	var b := StaticBody3D.new(); parent.add_child(b); b.position = pos
	var c := CollisionShape3D.new(); c.shape = BoxShape3D.new(); c.shape.size = size; b.add_child(c)
	var m := MeshInstance3D.new(); m.mesh = BoxMesh.new(); m.mesh.size = size; var material := StandardMaterial3D.new(); material.albedo_color = color; m.material_override = material; b.add_child(m)
	return b
func character(pos: Vector3,color: Color) -> CharacterBody3D:
	var a = Motor.new(); a.process_mode = Node.PROCESS_MODE_PAUSABLE; a.speed = profile.speed_mps
	var c := CollisionShape3D.new(); c.shape = CapsuleShape3D.new(); c.shape.radius = .35; c.shape.height = 1.8; a.add_child(c)
	var m := MeshInstance3D.new(); m.mesh = CapsuleMesh.new(); m.mesh.radius = .35; m.mesh.height = 1.8; var mat := StandardMaterial3D.new(); mat.albedo_color = color; m.material_override = mat; a.add_child(m)
	add_child(a); a.reset_motor(pos); return a
func choose(title: String) -> void:
	if title == "Quit": get_tree().quit()
	elif title == "Pause / resume": router.set_pause("menu",not router.paused())
	elif title == "Toggle blocker": toggle_blocker()
	elif title == "Reset NPC": nav.clear(); actor.reset_motor(HOME); brain.setup(nav,actor,target,profile); brain.start(); automatic = true
	elif title == "Start patrol": nav.clear(); brain.start(); automatic = true
func toggle_blocker() -> void:
	if is_instance_valid(blocker): blocker.free(); blocker = null
	else: blocker = box(self,actor.global_position+Vector3(1,0,0),Vector3(.25,3,4),Color(.8,.1,.1))
func on_action(id: String,value: float) -> void:
	if value < .5: return
	if id == "pause": choose("Pause / resume")
	if id == "act": choose("Start patrol")
func _input(event: InputEvent) -> void:
	if router and router.handle_event(event): get_viewport().set_input_as_handled()
func _physics_process(delta: float) -> void:
	if not is_instance_valid(actor):
		nav.step(delta); return
	if not router.paused():
		if is_instance_valid(target): target.move_wish = Vector2(router.strength("right")-router.strength("left"),router.strength("back")-router.strength("forward"))
		if automatic: brain.tick(delta)
		nav.step(delta); actor.move_wish = Vector2(nav.desired_velocity.x,nav.desired_velocity.z)/profile.speed_mps if not frozen else Vector2.ZERO
	max_detour = maxf(max_detour,absf(actor.global_position.z))
	label.text = "Navigation | Godot | Blue NPC: %s | Navigation: %s %s\nWASD moves yellow target | Space starts patrol | Esc pauses\nNPC (%.1f, %.1f) | path points %d | %s" % [brain.state,nav.state,nav.reason,actor.position.x,actor.position.z,nav.path.size(),"PAUSED" if router.paused() else "Ground navigation + real collision"]
func on_event(id: String,state: String,reason: String) -> void:
	events.append({"request":id,"state":state,"reason":reason})
	if state == "started" and callback_mode:
		callback_mode = false; callback_rejected = not nav.request("nested",actor,DEST); nav.clear()
func check(ok: bool,name: String) -> void:
	checks.append(name)
	if not ok: failures.append(name)
func request(id: String,dest: Vector3 = DEST,follow: Node3D = null) -> void: check(nav.request(id,actor,dest,follow,Vector3(0,-.9,0),Vector3(0,-.9,0)),"accepted: "+id)
func delay(seconds: float) -> void: await get_tree().create_timer(seconds,true,false,true).timeout
func until_idle(seconds: float) -> void:
	var elapsed := 0.0
	while nav.busy() and elapsed < seconds: await delay(.05); elapsed += .05
func reset() -> void:
	nav.clear(); nav.configure(profile.speed_mps,profile.arrival_m,profile.blocked_seconds,profile.deadline_seconds,profile.repath_seconds); actor.reset_motor(HOME); frozen = false
func screenshot(suffix: String) -> void:
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(report+"-"+suffix+".png")
func run_tests() -> void:
	await delay(.2)
	check(region.navigation_mesh.get_polygon_count()>0 and nav.ready_map(),"native geometry bake synchronized")
	check(not nav.configure(NAN,.35,1,20),"invalid configuration rejected")
	request("detour"); check(nav.path.size()>=4,"native path bends around wall")
	check(not nav.request("busy",actor,DEST),"concurrent request rejected")
	await delay(1); await screenshot("route"); await until_idle(20)
	check(nav.state=="arrived" and actor.position.distance_to(DEST+Vector3(0,.9,0))<.65,"collision motor reaches checked destination")
	check(max_detour>4.2,"actual trajectory detours around static wall")
	check(nav.desired_velocity==Vector3.ZERO,"arrival releases steering")
	check(not nav.request("detour",actor,DEST),"completed request ID cannot restart")
	check(not nav.request("outside",actor,Vector3(100,0,0)),"outside navigation rejected")
	var island_projection := NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map,Vector3(14,0,0))
	check(Vector2(island_projection.x-14,island_projection.z).length()<=.1 and absf(island_projection.y)<=.6,"isolated platform has native navigation surface")
	check(not nav.request("island",actor,Vector3(14,0,0),null,Vector3(0,-.9,0)) and nav.last_error=="unreachable","disconnected island cannot succeed via partial path")
	reset(); request("cancel"); nav.cancel(); nav.cancel(); check(nav.state=="cancelled" and nav.desired_velocity==Vector3.ZERO,"cancel is idempotent and stops steering")
	request("pause"); var key := InputEventKey.new(); key.keycode=KEY_ESCAPE; key.pressed=true; Input.parse_input_event(key); await delay(.1)
	check(router.paused() and not nav.busy(),"native pause input cancels movement")
	check(not nav.request("paused",actor,DEST),"paused navigator rejects requests")
	key = InputEventKey.new(); key.keycode=KEY_ESCAPE; Input.parse_input_event(key); router.set_pause("menu",false); await delay(.1)
	check(not nav.busy(),"resume does not revive cancelled movement")
	reset(); request("blocker",Vector3(-1,0,-3)); blocker = box(self,Vector3(-3.5,1,-3),Vector3(.25,3,4),Color.RED)
	await until_idle(5); check(nav.state=="failed" and nav.reason=="blocked" and actor.position.x < -3.5,"dynamic collision blocks motor and fails bounded request"); blocker.free(); blocker=null
	reset(); nav.configure(3,.35,10,.2); request("deadline"); await until_idle(1); check(nav.reason=="timeout","request deadline is bounded")
	reset(); nav.configure(3,1.0,1,20); target.reset_motor(Vector3(-2,.9,-3)); request("moving-target",Vector3.ZERO,target); target.reset_motor(Vector3(-2,.9,1)); await delay(.6)
	check(nav.goal.distance_to(target.position+Vector3(0,-.9,0))<.1 and nav.path.size()>0,"moving target updates native path")
	await until_idle(6); check(nav.state=="arrived","moving target can be reached")
	reset(); target.reset_motor(Vector3(-2,.9,-3)); request("target-unreachable",Vector3.ZERO,target); target.reset_motor(Vector3(14,.9,0)); await until_idle(2); check(nav.state=="failed" and nav.reason=="unreachable","moving target crossing to disconnected surface fails")
	reset(); target.reset_motor(Vector3(-2,.9,-3)); request("target-lost",Vector3.ZERO,target); target.free(); await delay(.1); check(nav.reason=="target_lost" and not nav.busy(),"destroyed target fails without stale steering")
	target = character(Vector3(-7,.9,5),Color.YELLOW); target.set_meta("detectable",false)
	reset(); callback_mode=true; request("callback-clear"); check(callback_rejected and not nav.busy(),"callback cannot reenter and may clear")
	request("clear"); nav.clear(); check(nav.state=="idle" and nav.path.is_empty() and nav.desired_velocity==Vector3.ZERO,"scene cleanup clears request and path")
	request("destroy-mover"); actor.free(); await delay(.1); check(nav.reason=="mover_lost","destroyed mover fails safely")
	actor = character(HOME,Color(.05,.7,1)); reset(); brain.setup(nav,actor,target,profile); brain.start(); automatic=true; await delay(.3)
	check(brain.state=="patrol" and nav.busy(),"project patrol issues native move")
	target.reset_motor(actor.position+Vector3(-1,0,1)); target.set_meta("detectable",true); await delay(.2)
	check(brain.state=="chase","visible nearby target switches to chase")
	target.set_meta("detectable",false); await delay(.75); check(brain.state=="search","lost target enters bounded search")
	await delay(.6); check("return" in brain.transitions,"search expires into return")
	await delay(4); check(brain.state=="patrol" and "return" in brain.transitions,"NPC returns home and resumes patrol")
	await screenshot("patrol"); frozen=true; await delay(1.5); check(brain.state=="blocked" and not nav.busy(),"behavior stops on failed movement without endless retry")
	reset(); brain.start(); await delay(.2); check(brain.state=="patrol" and nav.busy(),"explicit retry starts patrol after blocked state")
	brain.stop(); automatic=false; nav.clear()
	var paired := true; var by_request := {}
	for e in events:
		if not by_request.has(e.request): by_request[e.request]=[]
		by_request[e.request].append(e.state)
	for states in by_request.values():
		if states.size()!=2 or states[0]!="started" or states[1] not in ["arrived","failed","cancelled"]: paired=false
	check(paired,"every accepted request has exactly one terminal event")
	var f := FileAccess.open(report,FileAccess.WRITE); f.store_string(JSON.stringify({"engine":Engine.get_version_info().string,"checks":checks,"failures":failures,"events":events,"behavior_transitions":brain.transitions,"max_detour_m":max_detour,"input":"native software events; no human or physical device claim"},"  ")); f.close()
	get_tree().quit(0 if failures.is_empty() else 1)
