extends Node2D
## Public engineering fixture, not finished game art. Shapes and tone are original.
var recorder: Node
var hero: CharacterBody2D
var target: StaticBody2D
var label: Label
var sound: AudioStreamPlayer
var sustain: AudioStreamPlayer
var speed := 180.0
var cleanup_delay := 0.075
var state := "idle"
var phase := 0.0
var effect_active := false
var automated := false
var output_path := ""
var hp := 2
var travel := 0.0
var generation := 0
var capture_media := false
var media: Array = []
var audio_record: AudioEffectRecord
var audio_started := 0.0
var restart_button: Button
var restarted := false
var settings: Dictionary

func shape(body: CollisionObject2D, geometry: Shape2D, offset := Vector2.ZERO) -> void:
	var c := CollisionShape2D.new()
	c.shape = geometry
	c.position = offset
	body.add_child(c)

func rectangle(size: Vector2) -> RectangleShape2D:
	var geometry := RectangleShape2D.new()
	geometry.size = size
	return geometry

func _ready() -> void:
	Engine.max_fps = 120
	settings = JSON.parse_string(FileAccess.get_file_as_string("res://settings.json"))
	speed = float(settings.movement.speed)
	cleanup_delay = float(settings.combat.cleanup_delay)
	for arg in OS.get_cmdline_user_args():
		if arg == "--automated": automated = true
		if arg == "--capture-media": capture_media = true
		if arg.begins_with("--output="): output_path = arg.trim_prefix("--output=")
		if arg.begins_with("--cleanup-delay="): cleanup_delay = arg.trim_prefix("--cleanup-delay=").to_float()
	recorder = load("res://OAGDObservation.gd").new()
	add_child(recorder)
	hero = CharacterBody2D.new()
	hero.name = "Hero"
	hero.position = Vector2(180,270)
	add_child(hero)
	var circle := CircleShape2D.new()
	circle.radius = 18
	shape(hero,circle)
	target = StaticBody2D.new()
	target.name = "Target"
	target.position = Vector2(470,270)
	add_child(target)
	shape(target,rectangle(Vector2(settings.arena.target_width,settings.arena.target_height)))
	var floor := StaticBody2D.new()
	floor.name = "Floor"
	add_child(floor)
	shape(floor,rectangle(Vector2(820,30)),Vector2(480,360))
	var camera := Camera2D.new()
	camera.name = "ReviewCamera"
	camera.position = Vector2(480,270)
	add_child(camera)
	var ui := CanvasLayer.new()
	add_child(ui)
	label = Label.new()
	label.position = Vector2(24,22)
	label.add_theme_font_size_override("font_size",22)
	ui.add_child(label)
	var reset := Button.new()
	restart_button = reset
	reset.text = "Restart"
	reset.position = Vector2(24,116)
	reset.pressed.connect(restart)
	ui.add_child(reset)
	sound = AudioStreamPlayer.new()
	add_child(sound)
	var wave := AudioStreamWAV.new()
	wave.format = AudioStreamWAV.FORMAT_16_BITS
	wave.mix_rate = 22050
	var samples := PackedByteArray()
	samples.resize(4410)
	for i in range(2205): samples.encode_s16(i*2,int(sin(TAU*160*i/22050.0)*6500*(1.0-i/2205.0)))
	wave.data = samples
	sound.stream = wave
	sustain = AudioStreamPlayer.new()
	add_child(sustain)
	var loop := AudioStreamWAV.new()
	loop.format = AudioStreamWAV.FORMAT_16_BITS
	loop.mix_rate = 22050
	loop.loop_mode = AudioStreamWAV.LOOP_FORWARD
	# Use the last valid frame and a real interpolation guard. Some engine
	# versions mix one sample at the forward-loop boundary inclusively.
	loop.loop_end = 2204
	var texture := PackedByteArray()
	texture.resize(4414)
	for i in range(2207): texture.encode_s16(i*2,int((sin(TAU*400*i/22050.0)+0.25*sin(TAU*800*i/22050.0))*1400))
	loop.data = texture
	sustain.stream = loop
	if capture_media:
		audio_record = AudioEffectRecord.new()
		AudioServer.add_bus_effect(0,audio_record)
		audio_record.set_recording_active(true)
		audio_started = recorder.game_seconds
		capture_frames()
	recorder.register_object("hero",hero,"player")
	recorder.register_object("target",target,"encounter")
	recorder.sample_parameter("hero",self,"speed","world_units/s","res://settings.json#/movement/speed")
	recorder.sample_parameter("hero",self,"cleanup_delay","seconds","res://settings.json#/combat/cleanup_delay plus explicit command override")
	if automated:
		travel = 1
		await get_tree().create_timer(0.8).timeout
		travel = 0
		await get_tree().create_timer(0.2).timeout
		attack()
		await get_tree().create_timer(0.3).timeout
		cancel_attack()
		await get_tree().create_timer(0.7).timeout
		attack()
		await get_tree().create_timer(0.8).timeout
		travel = 1
		await get_tree().create_timer(0.8).timeout
		travel = 0
		# Exercise the actual focused UI control, not a direct restart() call.
		restart_button.grab_focus()
		var press := InputEventAction.new()
		press.action = "ui_accept"
		press.pressed = true
		Input.parse_input_event(press)
		await get_tree().process_frame
		press = InputEventAction.new()
		press.action = "ui_accept"
		press.pressed = false
		Input.parse_input_event(press)
		await get_tree().create_timer(0.3).timeout
		if capture_media:
			audio_record.set_recording_active(false)
			var recording := audio_record.get_recording()
			var audio_path := output_path.get_base_dir()+"/mix.wav"
			var audio_error := recording.save_to_wav(audio_path)
			if audio_error != OK:
				push_error("Audio capture failed")
				get_tree().quit(2)
				return
			media.append({"path":relative_path(audio_path),"kind":"audio","clock":"game","anchors":[[audio_started,0]],"description":"Actual master bus mix; start anchor is estimated at record enable, no hardware latency measurement","audio_coverage":"included"})
		var context := {"project":ProjectSettings.globalize_path("res://").trim_suffix("/"),"build":"source-fixture",
			"input_mode":"mixed","method":"real Godot physics, hit ray, cancel, recovery and focused UI restart",
			"conditions":["automated gameplay handlers","audio trigger does not prove audible output","display="+DisplayServer.get_name(),"cleanup_delay="+str(cleanup_delay)]}
		var capture: Dictionary = recorder.capture(self,context)
		capture.media = media
		var file := FileAccess.open(output_path,FileAccess.WRITE)
		var error := FileAccess.get_open_error()
		if file != null:
			file.store_string(JSON.stringify(capture,"\t"))
			file.close()
		var checks := [
			{"name":"target defeated before retry","passed":recorder.events.filter(func(e): return e.event == "victory").size() == 1},
			{"name":"two real ray hits","passed":recorder.events.filter(func(e): return e.event == "hit").size() == 2},
			{"name":"focused UI restart","passed":restarted and hp == 2},
			{"name":"restored idle and effects","passed":state == "idle" and not effect_active and not sound.playing and not sustain.playing},
			{"name":"capture written","passed":error == OK}]
		var failed := checks.filter(func(c): return not c.passed).size()
		var test_file := FileAccess.open(output_path.get_base_dir()+"/test-results.json",FileAccess.WRITE)
		test_file.store_string(JSON.stringify({"tests":checks.size(),"failed":failed,"errors":0,"checks":checks},"\t"))
		test_file.close()
		print(JSON.stringify({"observation_saved":error == OK,"path":output_path,"hp":hp,"effect_active":effect_active,"state":state,"error":error}))
		get_tree().quit(0 if failed == 0 else 1)

func relative_path(path: String) -> String:
	return path.replace("\\","/").trim_prefix(ProjectSettings.globalize_path("res://").replace("\\","/"))

func capture_frames() -> void:
	if DisplayServer.get_name() == "headless": return
	while is_inside_tree() and media.size() < 40:
		await get_tree().create_timer(0.2).timeout
		await RenderingServer.frame_post_draw
		var path := output_path.get_base_dir()+"/frame-%03d.png" % media.size()
		var error := get_viewport().get_texture().get_image().save_png(path)
		if error == OK:
			media.append({"path":relative_path(path),"kind":"image","clock":"game","anchors":[[recorder.game_seconds,0]],"description":"Actual rendered fixture frame; readback adds overhead","audio_coverage":"not_included"})

func restart() -> void:
	restarted = true
	generation += 1
	hp = 2
	hero.position = Vector2(180,270)
	state = "idle"
	effect_active = false
	sound.stop()
	sustain.stop()
	restart_button.release_focus()
	recorder.mark_event("hero","restart",{"hp":hp})

func attack() -> void:
	recorder.mark_event("hero","input_request",{"action":"attack"})
	if state != "idle" or hp <= 0:
		recorder.mark_event("hero","input_rejected",{"state":state,"hp":hp})
		return
	generation += 1
	state = "windup"
	phase = 0
	recorder.mark_event("hero","action_started")

func cleanup() -> void:
	effect_active = false
	sound.stop()
	sustain.stop()
	recorder.mark_event("hero","cleanup",{"effect_active":effect_active,"audio_playing":sound.playing or sustain.playing})

func cancel_attack() -> void:
	recorder.mark_event("hero","input_request",{"action":"cancel"})
	if state == "idle": return
	state = "idle"
	recorder.mark_event("hero","cancel",{"effect_active":effect_active})
	var current_generation := generation
	if cleanup_delay > 0: await get_tree().create_timer(cleanup_delay).timeout
	if current_generation == generation: cleanup()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept"): attack()
	if event.is_action_pressed("ui_cancel"): cancel_attack()

func _physics_process(delta: float) -> void:
	if hero == null: return
	hero.velocity = Vector2(speed*(travel if automated else Input.get_axis("ui_left","ui_right")),0)
	hero.move_and_slide()
	if state != "idle": phase += delta
	if state == "windup" and phase >= float(settings.combat.windup):
		state = "active"
		effect_active = true
		sustain.play()
		recorder.mark_event("hero","rule_commit")
		recorder.mark_event("hero","vfx_start",{"effect_active":effect_active})
		var result: Dictionary = recorder.ray_query("hero","attack",hero.global_position,hero.global_position+Vector2(settings.combat.range,0),1,"actual hit query",[hero.get_rid()])
		if result.get("hit_object","") == str(target.get_path()):
			hp = maxi(0,hp-1)
			recorder.mark_event("hero","hit",{"target":str(target.get_path()),"hp":hp})
			sound.play()
			recorder.mark_event("hero","audio_trigger",{"playing":sound.playing})
			if hp == 0: recorder.mark_event("target","victory",{"hp":hp})
		else: recorder.mark_event("hero","miss")
	if state == "active" and phase >= 0.52:
		state = "recovery"
		recorder.mark_event("hero","recovery")
		cleanup()
	if state == "recovery" and phase >= 0.72:
		state = "idle"
		recorder.mark_event("hero","ready")
	if Engine.get_physics_frames()%12 == 0:
		recorder.ray_query("hero","forward",hero.global_position,Vector2(700,270),1,"visibility at actual position",[hero.get_rid()])
	label.text = "OBSERVATION FIXTURE | Target HP: %d\nArrow keys: move | Space: attack | Esc: cancel\n%s" % [hp,"TARGET CLEARED — Restart to repeat" if hp == 0 else state.to_upper()]
	queue_redraw()

func _draw() -> void:
	draw_rect(Rect2(70,345,820,30),Color(0.1,0.2,0.3))
	if target != null:
		var target_size := Vector2(settings.arena.target_width,settings.arena.target_height)
		draw_rect(Rect2(target.position-target_size/2,target_size),Color(0.75,0.25,0.2) if hp>0 else Color(0.2,0.3,0.3))
	if hero != null:
		draw_circle(hero.position,18,Color(0.2,0.8,0.85))
		if effect_active: draw_arc(hero.position,float(settings.combat.range),-0.4,0.4,24,Color(1,0.65,0.2),4)
