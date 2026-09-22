extends SceneTree

var checks: int = 0
var failures: int = 0

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func _initialize() -> void:
	var model = load("res://main.gd").new()
	model.step(0.5, 1.0, false)
	check(is_equal_approx(model.player.x, 240.0), "Movement uses speed and delta")
	model.step(100.0, 1.0, false)
	check(is_equal_approx(model.player.x, 928.0), "Movement clamps to right edge")
	model.step(100.0, -1.0, false)
	check(is_equal_approx(model.player.x, 32.0), "Movement clamps to left edge")
	model.reset_simulation()
	model.step(0.0, 0.0, true)
	model.step(0.1, 0.0, true)
	check(model.bullets.size() == 1, "Cooldown prevents immediate repeated shot")
	model.step(0.15, 0.0, true)
	check(model.bullets.size() == 2, "Cooldown expires and allows another shot")
	model.reset_simulation()
	model.step(0.0, 0.0, true)
	model.step(1.0, 0.0, false)
	check(model.hits == 1 and model.bullets.is_empty(), "Swept projectile hits target and is removed")
	model.reset_simulation()
	model.step(0.0, -1.0, true)
	model.step(1.0, 0.0, false)
	check(model.hits == 0 and model.bullets.is_empty(), "Leftward shot leaves screen without hit")
	model.reset_simulation()
	check(model.hits == 0 and model.cooldown == 0.0 and model.player == Vector2(120, 330), "Reset restores simulation state")
	model.free()
	if failures == 0:
		print("OAGD_TEST_PASS count=%d" % checks)
	quit(0 if failures == 0 else 1)
