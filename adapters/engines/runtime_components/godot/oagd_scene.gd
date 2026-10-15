class_name OAGDScene
extends Node
## Passive scene chunks. Persistent player/UI live outside this owner.
var current: Node
var staged: Node

func stage(resource_path: String) -> String:
	if staged != null: return "transition busy"
	if not ResourceLoader.exists(resource_path, "PackedScene"): return "scene resource missing"
	var resource = load(resource_path)
	if not resource is PackedScene: return "resource is not a PackedScene"
	staged = resource.instantiate()
	if staged == null: return "scene instantiation failed"
	return ""

func cancel() -> void:
	if staged != null: staged.free(); staged = null

func commit() -> String:
	if staged == null: return "no staged scene"
	# The project has validated IDs and applied state to the detached candidate.
	var previous := current
	current = staged
	staged = null
	if previous != null: remove_child(previous)
	add_child(current)
	if previous != null: previous.queue_free()
	return ""
