extends "res://main.gd"
## Separate continuous-motion scenario. Original main.gd/audio regression unchanged.
var dodge_active := false
var hurt_active := false

func dodge() -> void:
	recorder.mark_event("hero","input_request",{"action":"dodge"})
	cancel_attack()
	dodge_active = true
	travel = -2.0
	recorder.mark_event("hero","dodge_started")
	await get_tree().create_timer(0.12).timeout
	travel = 0
	dodge_active = false
	recorder.mark_event("hero","dodge_ended")

func receive_hit() -> void:
	generation += 1
	state = "idle"
	cleanup()
	hurt_active = true
	recorder.mark_event("hero","hit_interrupt",{"effect_active":effect_active,"audio_playing":sound.playing or sustain.playing})
	await get_tree().create_timer(0.2).timeout
	hurt_active = false
	recorder.mark_event("hero","hurt_recovered")

func _ready() -> void:
	super._ready()
	# Invoke this scene WITHOUT --automated; the base scene's shorter scenario
	# must not run concurrently. Calls here are labeled handler-driven evidence.
	if automated:
		push_error("Continuity scene requires its own sequence; omit --automated")
		get_tree().quit(2)
		return
	automated = true
	hp = 5
	travel = 1
	await get_tree().create_timer(0.8).timeout
	travel = 0
	recorder.mark_event("hero","movement_stopped")
	await get_tree().create_timer(0.2).timeout
	attack()
	await get_tree().create_timer(0.3).timeout
	dodge()
	await get_tree().create_timer(0.35).timeout
	# Recover the small dodge displacement using the native collision movement.
	travel = 1
	await get_tree().create_timer(0.24).timeout
	travel = 0
	attack()
	await get_tree().create_timer(0.25).timeout
	receive_hit()
	await get_tree().create_timer(0.3).timeout
	attack()
	await get_tree().create_timer(0.6).timeout
	recorder.mark_event("hero","combo_queued")
	while state != "idle": await get_tree().physics_frame
	recorder.mark_event("hero","combo_consumed")
	attack()
	await get_tree().create_timer(0.85).timeout
	var capture: Dictionary = recorder.capture(self,{"project":ProjectSettings.globalize_path("res://").trim_suffix("/"),"build":"source-fixture-continuity",
		"input_mode":"component_call","method":"continuous native movement, dodge, hit interruption and queued follow-up attack",
		"conditions":["automated handlers, not human input","original geometric character, not humanoid skeletal pose quality","base audio fixture unchanged; this scenario has no listening claim"]})
	capture.media = media
	var file := FileAccess.open(output_path,FileAccess.WRITE)
	file.store_string(JSON.stringify(capture,"\t"))
	file.close()
	var hits: int = recorder.events.filter(func(e): return e.event == "hit").size()
	var checks := [
		{"name":"four actual hits across interruption and combo","passed":hits==4},
		{"name":"dodge ended","passed":not dodge_active},
		{"name":"hurt recovered","passed":not hurt_active},
		{"name":"sequence restored idle and cleaned audio/FX","passed":state=="idle" and not effect_active and not sound.playing and not sustain.playing}]
	var failed := checks.filter(func(c): return not c.passed).size()
	var report := FileAccess.open(output_path.get_base_dir()+"/test-results.json",FileAccess.WRITE)
	report.store_string(JSON.stringify({"tests":checks.size(),"failed":failed,"errors":0,"checks":checks},"\t"))
	report.close()
	get_tree().quit(0 if failed==0 else 1)

func _draw() -> void:
	super._draw()
	if hero != null and (dodge_active or hurt_active):
		draw_circle(hero.position,23,Color(1,0.3,0.5) if hurt_active else Color(0.5,0.7,1),false,3)
