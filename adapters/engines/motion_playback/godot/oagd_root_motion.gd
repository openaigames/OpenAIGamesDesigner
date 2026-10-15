class_name OAGDRootMotion
extends RefCounted
## Single physics-step consumer. Configure an unlayered planar_v1 AnimationTree.
const Playback = preload("res://addons/oagd_playback/oagd_playback.gd")
var playback: Playback
var body: CharacterBody3D
var root_space: Node3D
var active := false
var requested := Vector3.ZERO
var actual := Vector3.ZERO

func configure(player: Playback, character: CharacterBody3D, skeleton: Skeleton3D) -> bool:
	if not player.root_enabled or not is_instance_valid(character) or not is_instance_valid(skeleton): return false
	playback = player; body = character; root_space = skeleton
	return true

func start(action: StringName, restart := false) -> bool:
	if playback == null or not playback.bindings.has(action) or playback.bindings[action].get("motion_owner") != "animation": return false
	if active and playback.current == action and not restart: return true
	if restart: playback.reset(action)
	elif not playback.select(action): return false
	body.velocity.x = 0; body.velocity.z = 0
	active = true; requested = Vector3.ZERO
	return true

func cancel() -> void:
	if playback == null: return
	active = false; requested = Vector3.ZERO
	body.velocity.x = 0; body.velocity.z = 0
	playback.reset(&"idle") # discards the old tree delta; actor transform never rewinds

func prepare_step() -> void:
	if playback == null: return
	# Completion is released on the next step, after the last animation delta moved.
	if active and (playback.finished or playback.bindings[playback.current].get("motion_owner") != "animation"): cancel()

func step(delta: float, controller_velocity: Vector3, gravity := 16.0) -> void:
	if playback == null or not is_finite(delta) or delta <= 0: return
	prepare_step()
	var owns := active
	var token := playback.generation
	playback.advance(delta)
	requested = Vector3.ZERO
	if owns and active and token == playback.generation:
		# Root track values live in Skeleton3D space, including imported object scale/axes.
		requested = root_space.global_basis * playback.tree.get_root_motion_position()
		requested.y = 0
	var velocity := requested / delta if owns else controller_velocity
	body.velocity.x = velocity.x; body.velocity.z = velocity.z
	body.velocity.y = -0.1 if body.is_on_floor() else body.velocity.y - gravity * delta
	var before := body.global_position
	body.move_and_slide() # exactly one native collision step; blocked delta is discarded
	actual = body.global_position - before
