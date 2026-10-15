class_name OAGDInteractable
extends Node3D
## Project-owned condition and synchronous commit. Queries must have no side effects.
@export var stable_id := ""
@export var prompt := "Interact"
@export var hold_seconds := 0.0
@export var enabled := true
@export var anchor_offset := Vector3.ZERO
var condition: Callable
var commit: Callable

func offer(actor: Node3D) -> Dictionary:
	if not enabled: return {"allowed": false, "reason": "disabled"}
	if not condition.is_valid(): return {"allowed": true, "reason": ""}
	var value = condition.call(actor)
	if not value is Dictionary or not value.get("allowed") is bool or not value.get("reason") is String:
		return {"allowed": false, "reason": "invalid condition result"}
	return value

func execute(actor: Node3D) -> bool:
	if not commit.is_valid(): return false
	var result = commit.call(actor)
	return result is bool and result

func anchor() -> Vector3:
	return global_position + anchor_offset
