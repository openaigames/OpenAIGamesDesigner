class_name OAGDActor
extends CharacterBody3D
## Optional motor. Game supplies wishes; no combat, inventory or quest rules.
@export var speed := 5.0
@export var jump_speed := 5.0
@export var gravity := 16.0
var move_wish := Vector2.ZERO
var enabled := true
var jump_requested := false

func request_jump() -> void:
	jump_requested = true

func _physics_process(delta: float) -> void:
	var wish := move_wish.limit_length()
	velocity.x = wish.x * speed if enabled else 0.0
	velocity.z = wish.y * speed if enabled else 0.0
	if not is_on_floor():
		velocity.y -= gravity * delta
	elif jump_requested and enabled:
		velocity.y = jump_speed
	jump_requested = false
	move_and_slide()

func reset_motor(at: Vector3) -> void:
	global_position = at
	velocity = Vector3.ZERO
	move_wish = Vector2.ZERO
	jump_requested = false
	enabled = true
