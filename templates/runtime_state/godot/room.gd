extends Node3D
@export var room_id := "a"

func _init() -> void:
	# Real physics/visual nodes exist while detached, so validation precedes commit.
	var floor_body := StaticBody3D.new()
	floor_body.name = "Floor"
	floor_body.position.y = -0.5
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	shape.shape.size = Vector3(20, 1, 20)
	floor_body.add_child(shape)
	var mesh := MeshInstance3D.new()
	mesh.mesh = BoxMesh.new()
	mesh.mesh.size = Vector3(20, 1, 20)
	floor_body.add_child(mesh)
	add_child(floor_body)
	var door := StaticBody3D.new()
	door.name = "Door"
	door.position = Vector3(0, 1.5, -4)
	var door_shape := CollisionShape3D.new()
	door_shape.shape = BoxShape3D.new()
	door_shape.shape.size = Vector3(3, 3, 0.4)
	door.add_child(door_shape)
	var door_mesh := MeshInstance3D.new()
	door_mesh.mesh = BoxMesh.new()
	door_mesh.mesh.size = Vector3(3, 3, 0.4)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.85, 0.45, 0.13)
	door_mesh.material_override = material
	door.add_child(door_mesh)
	add_child(door)

func apply_state(objects: Dictionary) -> String:
	var id := "door-" + room_id
	if not objects.has(id) or not objects[id] is bool: return "missing stable door id: " + id
	var door := get_node("Door") as StaticBody3D
	door.visible = not objects[id]
	door.collision_layer = 0 if objects[id] else 1
	return ""
