extends SceneTree
## Run Godot 4 --headless --path PROJECT --script THIS_SCRIPT -- JOB_JSON.
## Imports a processed GLB into a new PackedScene and samples actual Skeleton3D poses.
var job: Dictionary
var stage: Node

func fail(message: String) -> void:
	printerr(message)
	quit(2)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		fail("Expected one motion job JSON"); return
	job = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if job.has("sha256") and FileAccess.get_sha256(job.glb) != job.sha256:
		fail("GLB changed before import"); return
	if FileAccess.file_exists(job.report):
		fail("Capture destination already exists"); return
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(job.glb, state) != OK:
		fail("GLB import failed"); return
	stage = doc.generate_scene(state, float(job.fps), false, false)
	if stage == null:
		fail("No generated scene"); return
	root.add_child(stage)
	await process_frame
	var players := stage.find_children("*", "AnimationPlayer", true, false)
	var skeletons := stage.find_children("*", "Skeleton3D", true, false)
	if players.size() != 1 or skeletons.size() != 1:
		fail("Expected one AnimationPlayer and one Skeleton3D"); return
	var player: AnimationPlayer = players[0]
	var skeleton: Skeleton3D = skeletons[0]
	var names: Array[String] = []
	for n in player.get_animation_list():
		if n != "RESET": names.append(n)
	if names.size() != 1:
		fail("Expected exactly one exported clip"); return
	if FileAccess.file_exists(job.scene):
		fail("Destination scene exists; choose a new revision"); return
	var packed := PackedScene.new()
	if packed.pack(stage) != OK or ResourceSaver.save(packed, job.scene) != OK:
		fail("Cannot save imported scene"); return
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play(names[0])
	var frames: Array = []
	for index in range(int(job.frames)):
		var t := float(index) / float(job.fps)
		player.seek(t, true)
		player.advance(0)
		skeleton.force_update_all_bone_transforms()
		var bones := {}
		for i in range(skeleton.get_bone_count()):
			var pose: Transform3D = skeleton.global_transform * skeleton.get_bone_global_pose(i)
			var q := pose.basis.get_rotation_quaternion()
			bones[skeleton.get_bone_name(i)] = {"p": [pose.origin.x, pose.origin.y, pose.origin.z], "q": [q.x,q.y,q.z,q.w]}
		frames.append({"t": t, "bones": bones})
	var skins := 0
	for mesh in stage.find_children("*", "MeshInstance3D", true, false):
		if mesh.skin != null and mesh.skin.get_bind_count() > 0: skins += 1
	var report := {"ok": skins > 0, "engine": "godot", "engine_version": Engine.get_version_info().string,
		"method": "AnimationPlayer seek and evaluate; actual Skeleton3D global pose", "coordinates": "RH_Y_UP_METRES",
		"animation": names[0], "length_s": player.get_animation(names[0]).length, "skinned_meshes": skins, "frames": frames,
		"source_sha256": FileAccess.get_sha256(job.glb), "root_bones": []}
	for i in range(skeleton.get_bone_count()):
		if skeleton.get_bone_parent(i) == -1: report.root_bones.append(skeleton.get_bone_name(i))
	var file := FileAccess.open(job.report, FileAccess.WRITE)
	if file == null:
		fail("Cannot write capture"); return
	file.store_string(JSON.stringify(report, "\t")); file.close()
	quit(0 if report.ok else 2)
