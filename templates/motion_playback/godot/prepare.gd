extends SceneTree
func _initialize() -> void:
	call_deferred("build")
func build() -> void:
	var binding_path := "res://bindings.pending.json" if FileAccess.file_exists("res://bindings.pending.json") else "res://bindings.json"
	var definition: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(binding_path))
	var scene_path := "res://" + str(definition.get("character_scene", "character.tscn"))
	if FileAccess.file_exists(scene_path):
		printerr("Character already exists; use a new project/revision"); quit(2); return
	var character: Node3D
	var destination: AnimationPlayer
	var library := AnimationLibrary.new()
	var graph := AnimationNodeStateMachine.new()
	var index := 0
	for row in definition.clips:
		var doc := GLTFDocument.new()
		var state := GLTFState.new()
		if doc.append_from_file("res://" + str(definition.get("source_directory", "motion")) + "/" + row.clip + ".glb", state) != OK: quit(3); return
		var sample_fps := 60.0 if str(row.id).begins_with("turn_") and definition.has("turning") else 30.0
		var model := doc.generate_scene(state, sample_fps, false, false)
		var players := model.find_children("*", "AnimationPlayer", true, false)
		if players.size() != 1: quit(4); return
		var player: AnimationPlayer = players[0]
		var animation: Animation
		for name in player.get_animation_list():
			if name != "RESET": animation = player.get_animation(name).duplicate(true)
		if animation == null or absf(animation.length - float(row.duration_s)) > 0.001: quit(5); return
		animation.loop_mode = Animation.LOOP_LINEAR if row.loop else Animation.LOOP_NONE
		library.add_animation(row.id, animation)
		var node := AnimationNodeAnimation.new()
		node.animation = row.id
		graph.add_node(row.id, node, Vector2(220 * (index % 3), 140 * (index / 3)))
		index += 1
		if character == null:
			character = model
			destination = player
		else: model.free()
	for name in destination.get_animation_library_list(): destination.remove_animation_library(name)
	destination.add_animation_library("", library)
	var locomotion: Dictionary = definition.get("locomotion", {})
	if not locomotion.is_empty():
		var blend := AnimationNodeBlendTree.new()
		var row_index := 0
		for clip in ["idle", "walk", "run"]:
			var sequence := AnimationNodeAnimation.new(); sequence.animation = clip
			blend.add_node(clip, sequence, Vector2(-700, row_index * 200)); row_index += 1
		for clip in ["walk", "run"]:
			blend.add_node(clip + "_rate", AnimationNodeTimeScale.new(), Vector2(-450, 200 if clip == "walk" else 400))
			blend.connect_node(clip + "_rate", 0, clip)
		for name in ["gait", "move"]:
			var node := AnimationNodeBlend2.new(); node.sync = true
			blend.add_node(name, node, Vector2(-200, 300) if name == "gait" else Vector2(50, 100))
		blend.connect_node("gait", 0, "walk_rate"); blend.connect_node("gait", 1, "run_rate")
		blend.connect_node("move", 0, "idle"); blend.connect_node("move", 1, "gait")
		blend.connect_node("output", 0, "move")
		graph.add_node("locomotion", blend)
	var states: Array = []
	for row in definition.clips: states.append(row.id)
	if not locomotion.is_empty(): states.append("locomotion")
	for a in states:
		for b in states:
			if a == b: continue
			var transition := AnimationNodeStateMachineTransition.new()
			transition.xfade_time = 0.0 if definition.has("root_motion") else float(locomotion.get("transition_s", 0.12))
			transition.reset = true
			graph.add_transition(a, b, transition)
	var tree := AnimationTree.new()
	tree.name = "PlaybackTree"
	character.add_child(tree)
	tree.owner = character
	tree.anim_player = tree.get_path_to(destination)
	if definition.has("layers"):
		var layered := make_layers(graph, library, character, destination, definition)
		if layered == null: quit(8); return
		tree.tree_root = layered
	else: tree.tree_root = graph
	if definition.has("root_motion"):
		var root_track := NodePath()
		for animation_name in library.get_animation_list():
			var anim := library.get_animation(animation_name)
			var found := false
			for track in range(anim.get_track_count()):
				var path := anim.track_get_path(track)
				if anim.track_get_type(track) == Animation.TYPE_POSITION_3D and path.get_subname_count() == 1 and path.get_subname(0) == definition.root_bone:
					if not root_track.is_empty() and root_track != path: quit(9); return
					root_track = path; found = true
			if not found: printerr("Missing native root track"); quit(9); return
		tree.root_motion_track = root_track
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	tree.active = true
	var packed := PackedScene.new()
	if packed.pack(character) != OK or ResourceSaver.save(packed, scene_path) != OK: quit(6); return
	var evidence := {"ok": true, "revision": definition.revision, "binding_sha256": FileAccess.get_sha256(binding_path), "scene_sha256": FileAccess.get_sha256(scene_path), "engine": Engine.get_version_info().string, "clips": definition.clips.size(), "method": "GLTFDocument -> shared skeleton AnimationLibrary -> editable AnimationTree -> saved PackedScene"}
	FileAccess.open(scene_path + ".import-report.json", FileAccess.WRITE).store_string(JSON.stringify(evidence, "\t"))
	character.free()
	quit()

func make_layers(base: AnimationNodeStateMachine, library: AnimationLibrary, character: Node3D, player: AnimationPlayer, definition: Dictionary) -> AnimationNodeBlendTree:
	var skeleton: Skeleton3D = character.find_children("*", "Skeleton3D", true, false)[0]
	var root := skeleton.find_bone(definition.layers.upper_root)
	if root < 0: printerr("Missing upper mask root"); return null
	var included: Array[int] = []
	for bone in range(skeleton.get_bone_count()):
		var parent := bone
		while parent >= 0:
			if parent == root: included.append(bone); break
			parent = skeleton.get_bone_parent(parent)
	for role in ["dst_upperarm_R","dst_forearm_R","dst_hand_R","dst_upperarm_L","dst_forearm_L","dst_hand_L","dst_head"]:
		if not included.has(skeleton.find_bone(definition.observation_bones[role])): printerr("Upper mask excludes " + role); return null
	for name in [definition.root_bone,definition.observation_bones.dst_foot_L,definition.observation_bones.dst_foot_R]:
		if included.has(skeleton.find_bone(name)): printerr("Upper mask includes lower body"); return null
	var graph := AnimationNodeBlendTree.new(); graph.add_node("base", base)
	var previous := "base"
	for channel in ["upper","full"]:
		for bank in [0,1]:
			var name: String = channel + str(bank)
			var sequence := AnimationNodeAnimation.new(); sequence.animation = definition.layers.clips[0]
			graph.add_node(name, sequence)
			graph.add_node(name + "_rate", AnimationNodeTimeScale.new()); graph.connect_node(name + "_rate", 0, name)
			graph.add_node(name + "_seek", AnimationNodeTimeSeek.new()); graph.connect_node(name + "_seek", 0, name + "_rate")
		var banks := AnimationNodeBlend2.new(); banks.sync = true
		graph.add_node(channel + "_banks", banks)
		graph.connect_node(channel + "_banks", 0, channel + "0_seek"); graph.connect_node(channel + "_banks", 1, channel + "1_seek")
		var layer := AnimationNodeBlend2.new(); layer.sync = true
		if channel == "upper":
			layer.filter_enabled = true
			var animation := library.get_animation(definition.layers.clips[0])
			for track in range(animation.get_track_count()):
				var path := animation.track_get_path(track)
				if path.get_subname_count() > 0 and included.has(skeleton.find_bone(path.get_subname(0))): layer.set_filter_path(path, true)
		graph.add_node(channel + "_weight", layer)
		graph.connect_node(channel + "_weight", 0, previous); graph.connect_node(channel + "_weight", 1, channel + "_banks")
		previous = channel + "_weight"
	graph.connect_node("output", 0, previous)
	return graph
