extends SceneTree
const R=preload("scene_replacement.gd")
const I=preload("static_scene.gd")
func _initialize():
	var spec:Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://case.json"))
	DirAccess.make_dir_recursive_absolute("res://native")
	for id in spec.assets:
		var imported:=I.prepare("res://revisions/"+id,"res://native/"+id+".scn")
		assert(imported.ok,str(imported))
	var root:=Node3D.new();root.name="Scene";var ids:=[]
	for row in spec.grayboxes:
		var n:=MeshInstance3D.new();n.name=row.id;n.set_meta("stable_id",row.id)
		var mesh:=BoxMesh.new();mesh.size=Vector3(row.size[0],row.size[1],row.size[2]);n.mesh=mesh
		n.position=Vector3(row.center[0],row.center[1],row.center[2]);n.rotation.y=deg_to_rad(row.yaw)
		root.add_child(n)
		var body:=StaticBody3D.new();n.add_child(body);var shape:=CollisionShape3D.new();var box:=BoxShape3D.new();box.size=mesh.size;shape.shape=box;body.add_child(shape);R.own(n,root)
		if row.managed:ids.append(row.id)
	var baseline:=R.capture(root,ids);assert(baseline.has("objects"),str(baseline))
	var f:=FileAccess.open("res://baseline.json",FileAccess.WRITE);f.store_string(JSON.stringify(baseline,"\t"));f.close()
	var packed:=PackedScene.new();assert(packed.pack(root)==OK);assert(ResourceSaver.save(packed,"res://baseline.scn")==OK);root.free();quit()
