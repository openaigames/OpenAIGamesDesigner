class_name OAGDCamera
extends SpringArm3D
## Independent optional follow camera: game owns input mapping and mode selection.
@export var distance := 5.0
var camera: Camera3D

func _ready() -> void:
	spring_length = distance
	collision_mask = 1
	margin = 0.15
	camera = Camera3D.new()
	add_child(camera)
	camera.current = true
	if get_parent() is CollisionObject3D:
		add_excluded_object(get_parent().get_rid())

func orbit(delta: Vector2) -> void:
	rotation.y -= delta.x
	rotation.x = clampf(rotation.x - delta.y, -1.1, 0.35)
