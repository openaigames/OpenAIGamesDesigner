class_name OAGDSession
extends Node
signal restarted(generation: int)
signal state_changed(state: StringName)
var generation := 0
var state: StringName = &"playing"

func set_state(value: StringName) -> void:
	if state != value:
		state = value
		state_changed.emit(state)

func restart() -> void:
	generation += 1
	set_state(&"playing")
	restarted.emit(generation)
