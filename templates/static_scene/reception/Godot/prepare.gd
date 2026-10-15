extends SceneTree
const R=preload("scene_replacement.gd")
var checks:=[]
var failures:=[]
func check(ok:bool,name:String):
	checks.append(name)
	if not ok:failures.append(name)
func _initialize():
	var root:Node3D=load("res://baseline.scn").instantiate()
	var plan:Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://replacement-plan.json"))
	var assets:Dictionary={};for id in plan.assets:assets[id]=load("res://native/"+id+".scn")
	var before:=R.fingerprint(root)
	# The last asset is deliberately wrong after earlier groups have staged.
	var bad:=assets.duplicate();bad.clockhill=assets.door
	check(not R.apply(root,plan,bad).ok,"late staged asset mismatch refused")
	check(R.fingerprint(root)==before,"staging failure leaves scene identical")
	check(R.apply(root,plan,assets).ok,"apply after staging failure")
	var packed:=PackedScene.new();packed.pack(root)
	check(ResourceSaver.save(packed,"res://absent_directory/cannot_save.scn")!=OK,"save failure detected")
	check(R.rollback(root).ok,"rollback after failed save")
	check(R.fingerprint(root)==before,"save failure recovery restores baseline")
	check(R.apply(root,plan,assets).ok,"reapply after recovery")
	var receipt:Dictionary=root.get_meta("oagd_replacement_receipt");var bad_receipt:=receipt.duplicate(true)
	bad_receipt.roots[plan.replacements[0].id]="wrong"
	root.set_meta("oagd_replacement_receipt",bad_receipt)
	check(not R.rollback(root).ok,"wrong receipt refused")
	root.set_meta("oagd_replacement_receipt",receipt)
	var nodes:=R.lookup(root);nodes.Unrelated.position.x+=.75
	packed=PackedScene.new();check(packed.pack(root)==OK,"pack combined scene");check(ResourceSaver.save(packed,"res://applied.scn")==OK,"save combined scene")
	root.free();var f:=FileAccess.open("res://prepare-report.json",FileAccess.WRITE);f.store_string(JSON.stringify({"checks":checks,"failures":failures},"\t"));f.close();quit(0 if failures.is_empty() else 1)
