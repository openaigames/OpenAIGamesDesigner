class_name OAGDFocus
extends RefCounted
## Project decides menu visibility; this helper restores the previous live Control.
var _stack: Array = []
func push(target: Control) -> void:
	var previous := target.get_viewport().gui_get_focus_owner()
	_stack.append(weakref(previous) if previous else null)
	target.grab_focus()
func pop() -> void:
	if _stack.is_empty(): return
	var previous: Variant = _stack.pop_back()
	if previous != null:
		var control: Variant = previous.get_ref()
		if is_instance_valid(control) and control.is_visible_in_tree(): control.grab_focus()
func clear() -> void:
	_stack.clear()
