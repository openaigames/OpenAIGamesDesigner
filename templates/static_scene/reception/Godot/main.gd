extends Node3D
const R=preload("scene_replacement.gd")
const I=preload("static_scene.gd")
var checks:=[]
var failures:=[]
var probes:Dictionary={}
var report:="user://runtime.json"
var view:="applied"
func check(ok:bool,name:String):
	checks.append(name)
	if not ok:failures.append(name)
func probe(name:String,a:Vector3,b:Vector3,r:float,h:float,clear:bool):
	var p:=R.passage(get_world_3d(),a,b,r,h);probes[name]=p;check(p.ok and p.clear==clear,name)
func point(d:Dictionary,p:Vector3)->Vector3:
	return Vector3(d.origin[0],d.origin[1],d.origin[2])+Basis(Vector3.UP,d.yaw)*p*d.scale
func _ready():
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--report="):report=arg.trim_prefix("--report=")
		if arg.begins_with("--view="):view=arg.trim_prefix("--view=")
	var spec:Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://case.json"))
	var root:Node3D=load("res://"+view+".scn").instantiate();add_child(root)
	var originals:=R.lookup(root);var groups:Dictionary={}
	for row in spec.mapping.replacements:
		check(root.get_node_or_null(row.id)!=null,"replacement exists "+row.id)
		check(not originals[row.targets[0]].visible,"graybox hidden "+row.id)
		var nodes:Dictionary={};I.collect(root.get_node(row.id),nodes);groups[row.id]=nodes
	check(is_equal_approx(originals.Unrelated.position.x,10.75),"manual unrelated edit preserved")
	check(root.has_meta("oagd_replacement_receipt"),"persistent receipt present")
	check(groups.BuildingA[25].mesh==groups.BuildingB[25].mesh,"building instances share geometry")
	check(groups.DoorA[5].mesh==groups.DoorB[5].mesh,"doors share geometry with independent transforms")
	await get_tree().physics_frame
	await get_tree().physics_frame
	var a:Dictionary=spec.doors[0];var b:Dictionary=spec.doors[1]
	var a0:=point(a,Vector3(.6,1.05,-1.5));var a1:=point(a,Vector3(.6,1.05,1.5));var b0:=point(b,Vector3(.6,1.05,-1.5));var b1:=point(b,Vector3(.6,1.05,1.5))
	for door in spec.doors:
		check(groups[door.id][0].global_position.distance_to(Vector3(door.origin[0],door.origin[1],door.origin[2]))<.001,"planned root position "+door.id)
		probe("closed "+door.id,point(door,Vector3(.6,1.05,-1.5)),point(door,Vector3(.6,1.05,1.5)),.25,1.8,false)
	# Fault injection: leave A's collider behind while the visible leaf opens.
	var leaf:Node3D=groups.DoorA[5];var hinge:Node3D=groups.DoorA[4]
	var proxy:Node3D=leaf.find_children("*","AnimatableBody3D",true,false)[0];var local_before:=proxy.transform
	proxy.reparent(root,true);hinge.rotate_y(-PI/2)
	await get_tree().physics_frame
	await get_tree().physics_frame
	probe("detector catches orphaned door collision",a0,a1,.25,1.8,false)
	proxy.reparent(leaf,false);proxy.transform=local_before
	await get_tree().physics_frame
	await get_tree().physics_frame
	probe("A opens after proxy recovery",a0,a1,.25,1.8,true)
	probe("B remains independently closed",b0,b1,.25,1.8,false)
	groups.DoorB[4].rotate_y(-PI/2)
	await get_tree().physics_frame
	await get_tree().physics_frame
	probe("rotated scaled B opens",b0,b1,.25,1.8,true)
	probe("scaled B rejects oversized capsule",b0,b1,.75,1.8,false)
	probe("retained box collision",Vector3(-3,1.5,-2),Vector3(-3,1.5,2),.15,.4,false)
	probe("triangle box collision",Vector3(4,.5,-5),Vector3(4,.5,-1),.15,.6,false)
	probe("building A wall",Vector3(-20,1.05,10),Vector3(-3,1.05,10),.25,1.8,false)
	probe("building B wall",Vector3(6,1.05,10),Vector3(22,1.05,10),.25,1.8,false)
	probe("outside street",Vector3(0,1.05,-5),Vector3(8,1.05,-5),.25,1.8,true)
	var body:=CharacterBody3D.new();var shape:=CollisionShape3D.new();var cap:=CapsuleShape3D.new();cap.radius=.25;cap.height=1.8;shape.shape=cap;body.add_child(shape);add_child(body);body.global_position=a0
	await get_tree().physics_frame
	var route:=[a1,Vector3(2,1.05,2),b0,b1]
	for i in route.size():
		var hit:=body.move_and_collide(route[i]-body.global_position)
		check(hit==null and body.global_position.distance_to(route[i])<.01,"continuous character route leg "+str(i))
	body.free()
	groups.DoorA[4].rotate_y(PI/2)
	await get_tree().physics_frame
	await get_tree().physics_frame
	probe("A recloses",a0,a1,.25,1.8,false);probe("B stays open after A closes",b0,b1,.25,1.8,true)
	groups.DoorA[4].rotate_y(-PI/3)
	var light:=DirectionalLight3D.new();add_child(light);light.rotation_degrees=Vector3(-40,-35,0);light.light_energy=2
	var env:=WorldEnvironment.new();env.environment=Environment.new();env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color(.09,.12,.17);env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_color=Color(.7,.76,.85);env.environment.ambient_light_energy=.65;add_child(env)
	var camera:=Camera3D.new();add_child(camera);camera.position=Vector3(12,7,-10);camera.look_at(Vector3(2,1,3));camera.current=true
	if DisplayServer.get_name()!="headless":
		await get_tree().create_timer(7).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(report+".png")
	var f:=FileAccess.open(report,FileAccess.WRITE);f.store_string(JSON.stringify({"checks":checks,"failures":failures,"probes":probes,"view":view},"\t"));f.close();get_tree().quit(0 if failures.is_empty() else 1)
