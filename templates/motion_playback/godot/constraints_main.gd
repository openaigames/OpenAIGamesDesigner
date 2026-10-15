extends Node3D
const Playback = preload("res://addons/oagd_playback/oagd_playback.gd")
const Constraints = preload("res://addons/oagd_playback/oagd_constraints.gd")
const CASES = ["flat","slope","step_up","step_down","air_land","swing","no_ground","steep","high_step","single_hand","two_hand","carry","turn","switch","cancel","drop","lost_target","unreachable","regrab","feet_only","grip_only","foot_reach"]
var actor: CharacterBody3D
var model: Node3D
var skeleton: Skeleton3D
var motion: Playback
var ik: Constraints
var floor_body: StaticBody3D
var platform: StaticBody3D
var prop: Node3D
var camera: Camera3D
var label: Label
var binding := {}
var output := ""
var capture := ""
var view := "game"
var fps := 60
var clock := 0.0
var case_index := -1
var frame_index := 0
var rows := []
var events := []
var steps := {}
var modified := {}
var main_q := []
var off_q := []
var original_support := Transform3D.IDENTITY
func box(at: Vector3,size: Vector3,color: Color,collide := true) -> StaticBody3D:
	var body := StaticBody3D.new();body.position=at;body.collision_layer=3 if collide else 0
	var collision:=CollisionShape3D.new();var shape:=BoxShape3D.new();shape.size=size;collision.shape=shape;body.add_child(collision)
	var mesh:=MeshInstance3D.new();var cube:=BoxMesh.new();cube.size=size;mesh.mesh=cube;var material:=StandardMaterial3D.new();material.albedo_color=color;mesh.material_override=material;body.add_child(mesh);add_child(body);return body
func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--report="):output=arg.trim_prefix("--report=")
		if arg.begins_with("--frames="):capture=arg.trim_prefix("--frames=")
		if arg.begins_with("--fps="):fps=int(arg.trim_prefix("--fps="))
		if arg.begins_with("--view="):view=arg.trim_prefix("--view=")
	Engine.physics_ticks_per_second=fps;Engine.max_fps=fps
	if not capture.is_empty():DirAccess.make_dir_recursive_absolute(capture)
	var light:=DirectionalLight3D.new();light.rotation_degrees=Vector3(-55,-25,0);light.light_energy=1.5;add_child(light)
	var world:=WorldEnvironment.new();world.environment=Environment.new();world.environment.background_mode=Environment.BG_COLOR;world.environment.background_color=Color("182332");world.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;world.environment.ambient_light_color=Color.WHITE;world.environment.ambient_light_energy=.7;add_child(world)
	floor_body=box(Vector3(0,-.1,0),Vector3(20,.2,20),Color("35445a"));platform=box(Vector3(1,.06,0),Vector3(2,.12,3),Color("776344"))
	actor=CharacterBody3D.new();actor.collision_mask=2;add_child(actor)
	var shape:=CollisionShape3D.new();var capsule:=CapsuleShape3D.new();capsule.radius=.35;capsule.height=1.8;shape.shape=capsule;shape.position.y=.9;actor.add_child(shape)
	binding=JSON.parse_string(FileAccess.get_file_as_string("res://bindings.json"));model=load("res://"+binding.get("character_scene","character.tscn")).instantiate();actor.add_child(model);model.rotation.y=PI
	skeleton=model.find_children("*","Skeleton3D",true,false)[0];skeleton.modifier_callback_mode_process=Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_MANUAL
	motion=Playback.new();add_child(motion);var clips:={}
	for row in binding.clips:clips[row.id]=row
	if not motion.configure(model.get_node("PlaybackTree"),clips):get_tree().quit(2);return
	ik=Constraints.new();skeleton.add_child(ik)
	if not ik.configure(actor,binding.constraints,[actor.get_rid()]):get_tree().quit(3);return
	ik.modification_processed.connect(observe_pose)
	original_support=ik.support_offset
	for kind in ["missing_bone","broken_chain","zero_blend","bad_socket"]:
		var bad: Dictionary=binding.constraints.duplicate(true)
		if (kind=="bad_socket" and not bad.has("grip")) or (kind!="bad_socket" and not bad.has("feet")):continue
		if kind=="missing_bone":bad.feet.pelvis="absent"
		if kind=="broken_chain":bad.feet.left.reverse()
		if kind=="zero_blend":bad.feet.blend_s=0
		if kind=="bad_socket":bad.grip.sockets.godot.main.rotation_xyzw=[0,0,0,2]
		var test:=Constraints.new();skeleton.add_child(test);var rejected:=not test.configure(actor,bad,[actor.get_rid()]);test.queue_free();events.append({"kind":"config_rejected","name":kind,"ok":rejected})
	events.append({"kind":"missing_request_rejected","ok":not ik.take(null)})
	camera=Camera3D.new();camera.current=true;camera.fov=50;add_child(camera);var canvas:=CanvasLayer.new();add_child(canvas);label=Label.new();label.position=Vector2(20,20);label.add_theme_font_size_override("font_size",19);canvas.add_child(label)
	next_case()
func current_case() -> String:return CASES[case_index] if case_index>=0 and case_index<CASES.size() else "interactive"
func next_case() -> void:
	case_index+=1;clock=0;steps.clear();ik.reset();ik.support_offset=original_support
	if is_instance_valid(prop):prop.queue_free()
	prop=box(Vector3(0,1,-.5),Vector3(.38,.06,.08),Color("d59b39"),false)
	actor.position=Vector3(0,.03,0);actor.rotation=Vector3.ZERO;actor.velocity=Vector3.ZERO;floor_body.rotation=Vector3.ZERO;floor_body.collision_layer=3;platform.collision_layer=0;platform.visible=false;platform.rotation=Vector3.ZERO;platform.position=Vector3(1,.06,0)
	var name:=current_case()
	if name=="slope":floor_body.rotation.z=deg_to_rad(12)
	if name=="steep":floor_body.collision_layer=2;platform.collision_layer=1;platform.visible=true;platform.position=Vector3(0,-.1,0);platform.rotation.z=deg_to_rad(55)
	if name in ["step_up","step_down","high_step"]:
		platform.visible=true;platform.collision_layer=1;platform.position.y=.06 if name!="high_step" else .34
		if name=="step_down":actor.position.y=.15
	motion.select(&"idle");motion.set_rate(1)
	# Explicit per-case capability gates also exercise independent installation.
	ik.feet=binding.constraints.get("feet",{}).duplicate(true) if name!="grip_only" else {}
	ik.grip=binding.constraints.get("grip",{}).duplicate(true) if name!="feet_only" else {}
	if name=="foot_reach" and not ik.feet.is_empty():ik.feet.max_pelvis_m=0
func once(key: String,at: float,call: Callable) -> void:
	if clock>=at and not steps.has(key):steps[key]=true;call.call()
func normalize(v: Vector3) -> Array:return [-v.z,v.x,v.y]
func observe_pose() -> void:
	modified.clear()
	for i in skeleton.get_bone_count():modified[str(skeleton.get_bone_name(i))]=normalize((skeleton.global_transform*skeleton.get_bone_global_pose(i)).origin)
	if ik.indices.has("main"):
		var q:=ik.world_pose(ik.indices.main).basis.get_rotation_quaternion();main_q=[q.x,q.y,q.z,q.w]
		q=ik.world_pose(ik.indices.offhand[2]).basis.get_rotation_quaternion();off_q=[q.x,q.y,q.z,q.w]
func take(both := true) -> void:
	var ok:=ik.take(prop,both);events.append({"case":current_case(),"t":clock,"kind":"take","ok":ok})
func _physics_process(delta: float) -> void:
	if ik==null:return
	clock+=delta;var name:=current_case();var wish:=Vector3.ZERO
	var is_grip:=not ik.grip.is_empty() and CASES.find(name)>=9 and name not in ["feet_only","foot_reach"]
	if not output.is_empty():
		if is_grip:
			once("pose",.1,func():motion.select(&"hold"));once("take",.35,func():take(name!="single_hand"))
			if name=="carry":wish=Vector3(0,0,-.35);once("carry",.7,func():motion.select(&"carry"))
			if name=="turn":actor.rotation.y=clampf((clock-.7)*1.3,0,PI)
			if name=="switch":once("switch",.9,func():motion.select(&"carry"))
			if name in ["cancel","drop","regrab"]:once("drop",1.1,func():ik.release())
			if name=="regrab":once("regrab",1.45,func():take())
			if name=="lost_target":once("lost",1.1,func():prop.queue_free())
			if name=="unreachable":ik.support_offset.origin=original_support.origin+Vector3(5,0,0)
		if name=="air_land":once("jump",.5,func():actor.velocity.y=3.8)
		if name=="no_ground":floor_body.collision_layer=2
	else:
		wish=Vector3(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),0,float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W))).normalized()*.7
		if Input.is_physical_key_pressed(KEY_E) and not ik.holding:motion.select(&"hold");take()
		if Input.is_physical_key_pressed(KEY_Q):ik.release();motion.select(&"idle")
		if Input.is_physical_key_pressed(KEY_SPACE) and actor.is_on_floor():actor.velocity.y=3.8
	actor.velocity.x=wish.x;actor.velocity.z=wish.z
	if not actor.is_on_floor():actor.velocity.y-=9.8*delta
	actor.move_and_slide()
	if name=="step_down":actor.position.y=.12
	if name=="foot_reach":actor.position.y=.22
	var stance:=Vector2.ONE
	if name=="swing" and clock>.5 and clock<1.4:stance.x=0
	# Carry gait has explicit source stance windows; unconfigured clips do not infer contacts.
	if name in ["carry","switch"] and motion.current==&"carry":
		var phase:=fmod(motion.position_s,1.0);stance=Vector2(1 if phase>.1 and phase<.4 else 0,1 if phase>.6 and phase<.9 else 0)
	ik.prepare(delta,actor.is_on_floor() or name in ["step_down","foot_reach"],stance,clock>=.5 and clock<1.8)
	motion.advance(delta);skeleton.advance(delta)
	# Skeleton update emits the final pose; report is deferred until the modifier has run.
	finish_frame.call_deferred(delta)
func finish_frame(delta: float) -> void:
	var name:=current_case();var prop_p:=normalize(prop.global_position) if is_instance_valid(prop) else []
	rows.append({"case":name,"t":clock,"dt":delta,"actor":normalize(actor.position),"grounded":actor.is_on_floor(),"state":motion.current,"clock":motion.position_s,"bones":modified.duplicate(true),"feet_status":ik.feet_status.duplicate(),"weights":[ik.weights.x,ik.weights.y],"pelvis":ik.pelvis_offset,"goals":[normalize(ik.goals[0]),normalize(ik.goals[1])],"grip_status":ik.grip_status,"grip_weight":ik.grip_weight,"holding":ik.holding,"support":normalize(ik.support_goal.origin),"prop":prop_p})
	rows[-1]["main_quaternion_native"]=main_q
	rows[-1]["off_quaternion_native"]=off_q
	rows[-1]["forward"]=normalize(-actor.global_basis.z)
	var offset:=Vector3(3,2.0,3) if view=="game" else Vector3(3,1.3,0) if view=="side" else Vector3(0,1.3,-3)
	camera.position=actor.position+offset;camera.look_at(actor.position+Vector3(0,.85,0));label.text="Contacts | "+name+"\nE pick up / Q release / Space jump / WASD move\nfeet: "+str(ik.feet_status)+"  grip: "+ik.grip_status
	if not capture.is_empty() and frame_index%12==0:capture_frame.call_deferred(frame_index)
	frame_index+=1
	if not output.is_empty() and clock>=2.2:
		if case_index+1==CASES.size():FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify({"schema":"oagd.constraints-runtime/1","engine":Engine.get_version_info().string,"frames":rows,"events":events},"\t"));get_tree().quit()
		else:next_case()
func capture_frame(index: int) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(capture.path_join("frame_%05d.png"%index))
