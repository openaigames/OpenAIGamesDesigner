extends SceneTree
const R=preload("scene_replacement.gd")
func _initialize():
	var root:Node3D=load("res://applied.scn").instantiate()
	var plan:Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://replacement-plan.json"))
	var nodes:=R.lookup(root);var unrelated:=R.fingerprint(nodes.Unrelated);var checks:=[]
	assert(R.rollback(root).ok);checks.append("restart rollback")
	for id in plan.baseline.objects:
		assert(R.fingerprint(nodes[id])==plan.baseline.objects[id].fingerprint,id);checks.append("baseline restored "+id)
	assert(R.fingerprint(nodes.Unrelated)==unrelated);checks.append("unrelated edit preserved")
	assert(not R.rollback(root).ok);checks.append("duplicate rollback rejected")
	var assets:Dictionary={};for id in plan.assets:assets[id]=load("res://native/"+id+".scn")
	assert(R.apply(root,plan,assets).ok);checks.append("restart reapply")
	var packed:=PackedScene.new();packed.pack(root);assert(ResourceSaver.save(packed,"res://recovered.scn")==OK)
	var f:=FileAccess.open("res://rollback-report.json",FileAccess.WRITE);f.store_string(JSON.stringify({"checks":checks,"failures":[]},"\t"));f.close();root.free();quit()
