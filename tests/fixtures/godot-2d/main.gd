extends Node2D
## Toolchain fixture, not an approved design for the user's game.

const SPEED: float = 240.0
const SHOT_SPEED: float = 600.0
const COOLDOWN: float = 0.25
var player: Vector2 = Vector2(120, 330)
var target: Vector2 = Vector2(700, 310)
var bullets: Array[Vector2] = []
var cooldown: float = 0.0
var hits: int = 0
var facing: float = 1.0

func _ready() -> void:
	var label := Label.new()
	label.text = "OpenAIGamesDesigner | ENGINE WORKFLOW TEST\nArrows / A D: move    Space: shoot    R: reset\nPlaceholder geometry; not final game design or art."
	label.position = Vector2(32, 24)
	label.add_theme_font_size_override("font_size", 20)
	add_child(label)

func reset_simulation() -> void:
	player = Vector2(120, 330)
	bullets.clear()
	cooldown = 0.0
	hits = 0
	facing = 1.0

func step(delta: float, movement: float, shooting: bool) -> void:
	player.x = clampf(player.x + movement * SPEED * delta, 32.0, 928.0)
	if movement != 0.0:
		facing = signf(movement)
	cooldown = maxf(0.0, cooldown - delta)
	if shooting and cooldown <= 0.0:
		# Bullet y stores its horizontal direction through a separate model below.
		bullets.append(Vector2(player.x, facing))
		cooldown = COOLDOWN
	for index in range(bullets.size() - 1, -1, -1):
		var old_x: float = bullets[index].x
		bullets[index].x += SHOT_SPEED * bullets[index].y * delta
		var new_x: float = bullets[index].x
		# Swept interval avoids passing through the target on a long frame.
		if minf(old_x, new_x) <= target.x + 22.0 and maxf(old_x, new_x) >= target.x - 22.0:
			hits += 1
			bullets.remove_at(index)
		elif new_x < 0.0 or new_x > 960.0:
			bullets.remove_at(index)

func _physics_process(delta: float) -> void:
	if Input.is_physical_key_pressed(KEY_R):
		reset_simulation()
	var movement := Input.get_axis("ui_left", "ui_right")
	if Input.is_physical_key_pressed(KEY_A):
		movement = -1.0
	elif Input.is_physical_key_pressed(KEY_D):
		movement = 1.0
	step(delta, movement, Input.is_physical_key_pressed(KEY_SPACE))
	queue_redraw()

func _draw() -> void:
	draw_rect(Rect2(0, 352, 960, 188), Color("26344d"))
	draw_line(Vector2(0, 352), Vector2(960, 352), Color("3875ff"), 4)
	draw_rect(Rect2(player - Vector2(18, 30), Vector2(36, 50)), Color("ff872a"))
	draw_line(player + Vector2(0, -20), player + Vector2(facing * 34, -20), Color("fff3dc"), 8)
	draw_circle(target, 25, Color("3875ff"))
	draw_circle(target, 10, Color("fff3dc"))
	for bullet in bullets:
		draw_circle(Vector2(bullet.x, 310), 5, Color("ffcc55"))
	draw_string(ThemeDB.fallback_font, Vector2(32, 460), "Hits: %d" % hits, HORIZONTAL_ALIGNMENT_LEFT, -1, 24, Color.WHITE)
