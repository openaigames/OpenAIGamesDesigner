extends Node3D
const Router=preload("res://addons/oagd/oagd_input.gd")
const Store=preload("res://addons/oagd/oagd_store.gd")
const Scenes=preload("res://addons/oagd/oagd_scene.gd")
const Feedback=preload("res://addons/oagd/oagd_feedback.gd")
const Interaction=preload("res://addons/oagd/oagd_interaction.gd")
const Target=preload("res://addons/oagd/oagd_interactable.gd")
const Nav=preload("res://addons/oagd/oagd_navigation.gd")
const Playback=preload("res://addons/oagd_playback/oagd_playback.gd")
const Constraints=preload("res://addons/oagd_playback/oagd_constraints.gd")
var router: Router
var store: Store
var scenes: Scenes
var feedback: Feedback
var interaction: Interaction
var nav: Nav
var motion: Playback
var ik: Constraints
var actor: CharacterBody3D
var npc: CharacterBody3D
var model: Node3D
var skeleton: Skeleton3D
var prop: Node3D
var target: Target
var camera: Camera3D
var label: Label
var binding: Dictionary
var room:="a"
var serial:=0
var held:=false
var patrol:=true
var patrol_side:=false
var report:=""
var mode:="exercise"
var save_dir:="user://combined"
var message:=""
var events:=[]
var checks:=[]
var failures:=[]
var snapshots:=[]
var test_wish:=Vector2.ZERO
var frame_count:=0

func unique(kind: String) -> String:serial+=1;return kind+":"+str(serial)
func box(parent: Node3D,at: Vector3,size: Vector3,color: Color) -> Node3D:
	var mesh:=MeshInstance3D.new();mesh.position=at;var shape:=BoxMesh.new();shape.size=size;mesh.mesh=shape
	var material:=StandardMaterial3D.new();material.albedo_color=color;mesh.material_override=material;parent.add_child(mesh);return mesh
func body(at: Vector3) -> CharacterBody3D:
	var value:=CharacterBody3D.new();value.position=at;value.collision_layer=2;value.collision_mask=1;add_child(value)
	var c:=CollisionShape3D.new();var shape:=CapsuleShape3D.new();shape.radius=.35;shape.height=1.8;c.shape=shape;c.position.y=.9;value.add_child(c);return value
func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--report="):report=arg.trim_prefix("--report=")
		if arg.begins_with("--mode="):mode=arg.trim_prefix("--mode=")
		if arg.begins_with("--save-dir="):save_dir=arg.trim_prefix("--save-dir=")
	Engine.max_fps=60
	NavigationServer3D.map_set_cell_size(get_world_3d().navigation_map,.1);NavigationServer3D.map_set_cell_height(get_world_3d().navigation_map,.05)
	var config: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://project-config.json"))
	store=Store.new(save_dir,config.id,1)
	router=Router.new();add_child(router);check(router.configure(JSON.parse_string(FileAccess.get_file_as_string("res://input-profile.json")))=="","input profile configured")
	router.action_changed.connect(action);router.pause_changed.connect(pause_changed)
	scenes=Scenes.new();add_child(scenes)
	feedback=Feedback.new();add_child(feedback);var audio:={}
	for id in ["door","ui","action","zone"]:
		var sound=load("res://audio/"+id+".wav").duplicate()
		if id=="zone":sound.loop_mode=AudioStreamWAV.LOOP_FORWARD;sound.loop_end=roundi(sound.get_length()*sound.mix_rate)
		audio[id]=sound
	check(feedback.configure(JSON.parse_string(FileAccess.get_file_as_string("res://feedback-profile.json")),audio,{"pulse":preload("res://pulse.tscn")})=="","feedback resources configured")
	feedback.lifecycle.connect(func(handle,event,cue,state):events.append({"kind":"feedback","handle":handle,"event":event,"cue":cue,"state":state}))
	interaction=Interaction.new();add_child(interaction);interaction.configure(2.5,65)
	interaction.lifecycle.connect(func(request,id,state,why):events.append({"kind":"interaction","request":request,"id":id,"state":state,"reason":why}))
	nav=Nav.new();add_child(nav);nav.configure(.7,.25,2,20)
	nav.lifecycle.connect(func(request,state,why):events.append({"kind":"navigation","request":request,"state":state,"reason":why}))
	actor=body(Vector3(-8,.03,0));npc=body(Vector3(-9,.03,1));box(npc,Vector3(0,.65,0),Vector3(.5,1.3,.5),Color("3bb6c4"))
	binding=JSON.parse_string(FileAccess.get_file_as_string("res://bindings.json"));model=load("res://"+binding.get("character_scene","character.tscn")).instantiate();actor.add_child(model);model.rotation.y=PI
	skeleton=model.find_children("*","Skeleton3D",true,false)[0];skeleton.modifier_callback_mode_process=Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_MANUAL
	motion=Playback.new();add_child(motion);var clips:={}
	for clip in binding.clips:clips[clip.id]=clip
	check(motion.configure(model.get_node("PlaybackTree"),clips),"native animation configured")
	ik=Constraints.new();skeleton.add_child(ik);check(ik.configure(actor,binding.constraints,[actor.get_rid(),npc.get_rid()]),"native contact solver configured")
	var light:=DirectionalLight3D.new();light.rotation_degrees=Vector3(-60,-25,0);light.light_energy=1.5;add_child(light)
	var world:=WorldEnvironment.new();world.environment=Environment.new();world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;world.environment.ambient_light_color=Color.WHITE;world.environment.ambient_light_energy=.8;add_child(world)
	camera=Camera3D.new();camera.current=true;camera.fov=55;add_child(camera)
	var canvas:=CanvasLayer.new();add_child(canvas);label=Label.new();label.position=Vector2(18,18);label.add_theme_font_size_override("font_size",18);canvas.add_child(label)
	check(transition({"room":"a","position":[-8,0.03,0],"held":false})=="","initial native scene committed")
	if not report.is_empty():run_tests.call_deferred()
func action(id: String,value: float) -> void:
	events.append({"kind":"input","action":id,"value":value,"frame":frame_count})
	if value<=0:
		if id=="act":interaction.cancel("released")
		return
	match id:
		"pause":router.set_pause("menu",not router._pauses.has("menu"))
		"act":interaction.begin(unique("take"))
		"cancel":cancel()
		"save":message=save_game()
		"load":message=load_game()
		"restart":restart()
		"scene":message=transition({"room":"b" if room=="a" else "a","position":[-8,.03,0],"held":false})
func pause_changed(value: bool) -> void:
	feedback.set_game_paused(value);interaction.set_suspended(value);nav.set_suspended(value)
	router.set_context("ui" if value else "game")
	actor.velocity=Vector3.ZERO;npc.velocity=Vector3.ZERO
func cancel() -> void:
	interaction.cancel("project-cancel");nav.cancel("project-cancel");feedback.stop_scope("action");ik.release();held=false;motion.reset(&"idle")
	if is_instance_valid(prop):prop.position=actor.position+Vector3(0,1,-1)
func reset_target() -> void:
	if is_instance_valid(target):target.free()
	if is_instance_valid(prop):prop.free()
	prop=box(self,Vector3(-8,1,-1),Vector3(.38,.06,.08),Color("d59b39"))
	target=Target.new();prop.add_child(target);target.stable_id="carry-tool";target.prompt="Hold E: carry tool";target.hold_seconds=.4
	target.condition=func(_a):return {"allowed":not held,"reason":"already held" if held else ""}
	target.commit=func(_a):return take()
	interaction.register_target(target)
func take() -> bool:
	if router.paused() or held:return false
	motion.select(&"hold")
	if not ik.take(prop,true):return false
	held=true;feedback.play("door",unique("pickup"),actor,Vector3.ZERO,true,"scene",.4);feedback.play("zone",unique("carry"),actor,Vector3.ZERO,true,"action",.5);return true
func valid_state(value: Dictionary) -> bool:
	if not value.get("room") in ["a","b"] or not value.get("held") is bool or not value.get("position") is Array or value.position.size()!=3:return false
	for component in value.position:
		if not (component is float or component is int) or not is_finite(component):return false
	return value.position[0]>=-10.5 and value.position[0]<=-5.5 and value.position[1]>=0 and value.position[1]<=2 and absf(value.position[2])<=2.5
func state() -> Dictionary:return {"room":room,"position":[actor.position.x,maxf(0,actor.position.y),actor.position.z],"held":held}
func transition(value: Dictionary) -> String:
	if not valid_state(value):return "invalid project state"
	var error:=scenes.stage("res://room_"+value.room+".tscn")
	if error!="":return error
	# Stage succeeds before any current world mutation. Transient operations never cross a scene boundary.
	interaction.clear();nav.clear();feedback.clear();ik.reset();held=false;motion.reset(&"idle")
	error=scenes.commit()
	if error!="":return error
	room=value.room;actor.position=Vector3(value.position[0],value.position[1],value.position[2]);actor.velocity=Vector3.ZERO;actor.rotation=Vector3.ZERO
	npc.position=Vector3(-9,.03,1);npc.velocity=Vector3.ZERO;reset_target()
	if value.held:
		# Restore stable ownership while paused too; no transient feedback is replayed from a save.
		motion.select(&"hold");held=ik.take(prop,true)
	return ""
func save_game() -> String:
	var value:=state()
	if not valid_state(value):return "player outside this example's save region"
	return store.write_slot("slot1",value)
func load_game() -> String:
	var result:=store.read_slot("slot1")
	if result.error!="":return result.error
	return transition(result.data)
func restart() -> void:message=transition({"room":"a","position":[-8,.03,0],"held":false})
func _physics_process(delta: float) -> void:
	if ik==null:return
	frame_count+=1
	if not router.paused():
		var wish:=test_wish if not report.is_empty() else Vector2(router.strength("right")-router.strength("left"),router.strength("back")-router.strength("forward"))
		actor.velocity.x=wish.x*.35;actor.velocity.z=wish.y*.35
		if not actor.is_on_floor():actor.velocity.y-=9.8*delta
		actor.move_and_slide()
		if wish.length()>.01:actor.rotation.y=atan2(-wish.x,-wish.y)
		interaction.update_query(actor,actor.position+Vector3(0,1,0),-actor.global_basis.z,delta)
		if patrol and not nav.busy() and nav.ready_map():
			patrol_side=not patrol_side;nav.request(unique("patrol"),npc,Vector3(-7 if patrol_side else -9,0,1))
		nav.step(delta);npc.velocity.x=nav.desired_velocity.x;npc.velocity.z=nav.desired_velocity.z
		if not npc.is_on_floor():npc.velocity.y-=9.8*delta
		npc.move_and_slide()
		motion.select(&"carry" if held and wish.length()>.01 else &"hold" if held else &"walk" if wish.length()>.01 else &"idle")
		var stance:=Vector2.ONE
		if motion.current in [&"walk",&"carry"]:
			var phase:=fmod(motion.position_s,1);stance=Vector2(1 if phase>.1 and phase<.4 else 0,1 if phase>.6 and phase<.9 else 0)
		ik.prepare(delta,actor.is_on_floor(),stance,held);motion.advance(delta);skeleton.advance(delta)
	camera.position=actor.position+Vector3(3,4,4);camera.look_at(actor.position+Vector3(0,.7,0));camera.rotation_degrees+=feedback.camera_offset
	label.text="Combined example | Godot | Room "+room+" | "+("PAUSED" if router.paused() else "PLAYING")+"\nWASD move / hold E take / Q cancel / Esc pause\nK save / L load / Tab room / R restart\n"+interaction.prompt+" | NPC: "+nav.state+" | held: "+str(held)+"\n"+message
func check(ok: bool,name: String) -> void:
	checks.append(name)
	if not ok:failures.append(name);push_error(name)
func wait(seconds: float) -> void:
	# The exercise advances physics consumers; frame timers can outrun physics during shader stalls.
	var until:=frame_count+ceili(seconds*Engine.physics_ticks_per_second)
	while frame_count<until:await get_tree().physics_frame
func snap(name: String) -> void:
	snapshots.append({"name":name,"state":state(),"clock":motion.position_s,"npc":[npc.position.x,npc.position.y,npc.position.z],"feedback":feedback.active.size(),"grip":ik.grip_status,"weight":ik.grip_weight,"feet":ik.feet_status.duplicate(),"navigation":nav.state})
	if DisplayServer.get_name()!="headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(report+"-"+name+".png")
func run_tests() -> void:
	await wait(1)
	if mode=="resume":
		check(load_game()=="","separate process loads saved state");await wait(.6)
		check(room=="b" and held and ik.holding,"separate process restores room and actual grip")
		check(ik.grip_weight>.9,"separate process native grip evaluated");check(feedback.active.is_empty(),"load does not replay transient feedback")
		await snap("resumed");finish();return
	check(nav.ready_map() and nav.busy(),"native navigation active on generated replacement scene")
	check(scenes.current.find_child("curve_a_portal",true,false)!=null,"native static replacement present")
	var oldnpc:=npc.position;await wait(.5);check(npc.position.distance_to(oldnpc)>.15,"NPC moves through collision motor")
	check(interaction.focused_id()=="carry-tool","real spatial query focuses stable interaction")
	router.feed("E",1);await wait(.12);check(interaction.holding(),"hold request in progress")
	router.set_pause("menu",true);router.set_pause("modal",true)
	check(not interaction.holding() and not held,"pause cancels incomplete interaction")
	router.set_pause("menu",false);check(router.paused(),"nested pause remains active")
	var time:=motion.position_s;var position:=actor.position;oldnpc=npc.position;await wait(.4)
	check(is_equal_approx(time,motion.position_s) and actor.position==position and npc.position==oldnpc,"pause freezes player NPC and native animation")
	router.set_pause("modal",false);await wait(.5);check(not held,"held input cannot resume cancelled interaction")
	router.feed("E",0);router.feed("E",1);await wait(.7);router.feed("E",0)
	check(held and ik.holding and ik.grip_weight>.9,"interaction commits to real two-hand grip")
	check(feedback.active.size()>0,"committed interaction owns native feedback")
	await snap("holding")
	router.set_pause("menu",true);time=motion.position_s;var prop_position:=prop.global_position
	var ages:=[]
	for item in feedback.active.values():ages.append(item.age)
	await wait(.3);var index:=0;var frozen:=true
	for item in feedback.active.values():frozen=frozen and is_equal_approx(item.age,ages[index]);index+=1
	check(frozen and is_equal_approx(time,motion.position_s) and prop.global_position==prop_position,"pause freezes feedback age animation and attached prop")
	check(feedback.play("action",unique("paused"),actor)==-1,"paused game cue rejected")
	router.set_pause("menu",false);test_wish=Vector2(0,-1);await wait(.6);test_wish=Vector2.ZERO
	check(actor.position.distance_to(position)>.15 and held,"carrying moves through native motor")
	check(motion.current==&"carry","carry animation selected while moving")
	patrol=false;cancel();await wait(.2)
	check(not held and not ik.holding and ik.grip_weight==0,"cancel releases native hand constraint")
	check(feedback.active.is_empty() and not interaction.holding() and not nav.busy(),"cancel clears cross-module transient work")
	var prior:=scenes.current;check(transition({"room":"missing","position":[0,0,0],"held":false})!="" and scenes.current==prior,"invalid destination leaves current scene intact")
	check(scenes.stage("res://missing.tscn")!="" and scenes.current==prior,"missing native scene leaves current scene intact")
	check(scenes.stage("res://room_b.tscn")=="","scene candidate prepared");scenes.cancel();check(scenes.staged==null and scenes.current==prior,"staged scene cancellation preserves current world")
	restart();await wait(.3);router.feed("E",1);await wait(.6);router.feed("E",0)
	check(held,"interaction can restart after cancellation")
	check(transition({"room":"b","position":[-8,.03,0],"held":false})=="","native scene switch commits")
	await wait(.4);check(not is_instance_valid(prior) and room=="b","previous native scene freed")
	check(not held and not ik.holding and feedback.active.is_empty() and not interaction.holding(),"scene switch releases grip feedback and pending interaction")
	check(interaction.focused_id()=="carry-tool","new scene re-registers stable target")
	router.feed("E",1);await wait(.7);router.feed("E",0);check(save_game()=="","project state written to local journal")
	check(held and room=="b","saved state contains room and stable held state")
	restart();await wait(.3);check(room=="a" and not held and feedback.active.is_empty(),"restart returns clean project defaults")
	check(load_game()=="","saved state applied through scene transaction");await wait(.6)
	check(room=="b" and held and ik.grip_weight>.9,"load restores room and evaluated grip")
	check(feedback.active.is_empty() and not interaction.holding(),"load excludes transient feedback and requests")
	check(load_game()=="","repeated load accepted");await wait(.4)
	check(feedback.active.is_empty() and held,"repeated load has no duplicate cue")
	check(store.write_slot("bad",{"room":"unknown","position":[0,0,0],"held":false})=="","invalid project payload fixture saved separately")
	prior=scenes.current;check(transition(store.read_slot("bad").data)!="" and scenes.current==prior and held,"invalid saved project payload rejected before mutation")
	patrol=true;await wait(.5);check(nav.busy(),"NPC resumes patrol after load")
	await snap("restored");finish()
func finish() -> void:
	set_physics_process(false);interaction.clear();nav.clear();feedback.clear();ik.reset();scenes.cancel()
	if is_instance_valid(scenes.current):scenes.current.free();scenes.current=null
	await get_tree().process_frame
	await get_tree().process_frame
	check(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT)==0,"scene lifecycle leaves no orphan nodes")
	FileAccess.open(report,FileAccess.WRITE).store_string(JSON.stringify({"schema":"oagd.combined-runtime/1","engine":Engine.get_version_info().string,"mode":mode,"checks":checks,"failures":failures,"snapshots":snapshots,"events":events,"human_playtest":false},"  "))
	get_tree().quit(0 if failures.is_empty() else 1)
