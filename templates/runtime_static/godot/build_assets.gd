extends SceneTree
const Static = preload("res://addons/oagd/oagd_static_assets.gd")
const Geometry = preload("res://addons/oagd/oagd_geometry.gd")
var checks: Array = []
var failures: Array = []
func check(ok: bool, name: String) -> void:
	checks.append(name)
	if not ok: failures.append(name)
func _initialize() -> void: call_deferred("build")
func own(node: Node, top: Node) -> void:
	for child in node.get_children(): child.owner=top; own(child,top)
func build() -> void:
	var plan: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://generated/static/plan.json"))
	var baseline: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://generated/static/baseline.json"))
	if FileAccess.file_exists("res://static_scene.tscn") or DirAccess.dir_exists_absolute("res://static-resources"): push_error("Existing derived resources are project-owned"); quit(1); return
	DirAccess.make_dir_recursive_absolute("res://static-resources")
	var resources := []
	for asset in plan.assets:
		var result := Static.prepare_asset("res://generated/static/"+asset.source,"res://static-resources/"+asset.id+".res")
		check(result.ok,"native asset generated: "+asset.id); resources.append(result)
		if not result.ok: quit(1); return
	var top := Node3D.new(); top.name="StaticScene"; root.add_child(top)
	var lookup := Geometry.load_scene("res://generated/static/baseline.json",top)
	var bad := plan.duplicate(true); bad.replacements[0].targets[0]="missing"
	check(not Static.apply(bad,baseline,lookup,top,"res://static-resources").ok and top.get_child_count()==baseline.meshes.size(),"missing target leaves scene untouched")
	var target: MeshInstance3D = lookup[plan.replacements[0].targets[0]]; target.position.x=.1
	check(not Static.apply(plan,baseline,lookup,top,"res://static-resources").ok and target.visible,"edited target rejected before mutation")
	target.position.x=0
	var receipt := Static.apply(plan,baseline,lookup,top,"res://static-resources")
	check(receipt.ok,"apply succeeds")
	if not receipt.ok: push_error(str(receipt)); quit(1); return
	check(not Static.apply(plan,baseline,lookup,top,"res://static-resources").ok,"duplicate application rejected")
	Static.rollback(receipt)
	check(target.visible and not target.get_child(0).get_child(0).disabled and top.get_child_count()==baseline.meshes.size(),"rollback restores visibility collision and object count")
	receipt=Static.apply(plan,baseline,lookup,top,"res://static-resources")
	check(receipt.ok,"reapply after rollback")
	own(top,top); var packed := PackedScene.new(); check(packed.pack(top)==OK,"native scene packed")
	check(ResourceSaver.save(packed,"res://static_scene.tscn")==OK,"native scene saved")
	var out := FileAccess.open("res://static-build.json",FileAccess.WRITE)
	out.store_string(JSON.stringify({"checks":checks,"failures":failures,"resources":resources,"plan_id":plan.plan_id},"  ")); out.close()
	quit(0 if failures.is_empty() else 1)
