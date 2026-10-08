class_name ActionPreviewConsumer
extends Node

# Optional test-scene consumer. Each animation binding is "track:animation_name".
# Projects with AnimationTree, IK, root motion or complex rules should implement
# the same host methods around their real consumer instead of adopting this one.
var animation_players: Dictionary = {}
var rest_animations: Dictionary = {}
var audio_streams: Dictionary = {}
var cameras: Dictionary = {}
var bridge: Node
var after_pose: Callable
var scheduler = preload("action_sequence_player.gd").new()
var _sequence: Dictionary = {}
var _audio: Dictionary = {}
var _time := 0.0
var _paused := false
var _speed := 1.0
var _complete := false
var _windows: Dictionary = {}
var _logic_events: Array[String] = []

func _ready() -> void:
	scheduler.sequence_signal.connect(_signal)
	for player: AnimationPlayer in animation_players.values():
		player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL

func preview_load(sequence: Dictionary) -> Dictionary:
	preview_cancel()
	for asset in sequence.assets:
		if asset.kind == "animation":
			var parts: PackedStringArray = str(asset.binding).split(":", true, 1)
			if parts.size()!=2 or not animation_players.has(parts[0]) or not animation_players[parts[0]].has_animation(parts[1]):
				return {"ok":false,"error":"AnimationPlayer binding is unavailable: "+str(asset.binding)}
		elif not audio_streams.has(asset.binding):
			return {"ok":false,"error":"Audio binding is unavailable: "+str(asset.binding)}
	for a in sequence.clips:
		for b in sequence.clips:
			if a.id != b.id and a.track == b.track and a.start_s < b.start_s + (b.source_out_s-b.source_in_s)/b.rate and b.start_s < a.start_s + (a.source_out_s-a.source_in_s)/a.rate:
				return {"ok":false,"error":"This example consumer does not support overlapping clips on one track"}
	if not scheduler.load_sequence(sequence): return {"ok":false,"error":"Sequence validation failed"}
	_sequence = sequence.duplicate(true)
	_time = 0.0
	_complete = false
	_paused = false
	_windows.clear()
	_logic_events.clear()
	for track in animation_players:
		var player: AnimationPlayer = animation_players[track]
		if rest_animations.has(track):
			player.play(rest_animations[track],0)
			player.seek(0.0,true)
	scheduler.start_sequence()
	_pose()
	return {"ok":true,"sequence":_sequence.duplicate(true)}

func preview_advance(delta: float) -> void:
	if _complete or _sequence.is_empty(): return
	var dt := minf(delta, maxf(0.0, float(_sequence.duration_s)-_time))
	for player: AnimationPlayer in animation_players.values(): player.advance(dt)
	_time += dt
	scheduler.advance(_time)
	for item in _audio.values():
		var clip: Dictionary = item.clip
		var incoming := minf(1.0,(_time-clip.start_s)/clip.blend_in_s) if clip.blend_in_s > 0 else 1.0
		var outgoing := minf(1.0,(clip.end_s-_time)/clip.blend_out_s) if clip.blend_out_s > 0 else 1.0
		item.player.volume_linear = maxf(0.0, clip.volume*minf(incoming,outgoing))
	_pose()
	_complete = _time >= float(_sequence.duration_s)-0.000001

func _pose() -> void:
	for player: AnimationPlayer in animation_players.values(): player.advance(0.0)
	if after_pose.is_valid(): after_pose.call()

func _signal(event: Dictionary) -> void:
	var clip: Dictionary = event.get("clip",{})
	if event.kind == "window_open": _windows[event.id] = true
	elif event.kind in ["window_close","window_cancel"]: _windows.erase(event.id)
	elif event.kind == "event": _logic_events.append(str(event.id))
	if clip and clip.source.kind == "animation":
		var parts: PackedStringArray = str(clip.source.binding).split(":",true,1)
		var player: AnimationPlayer = animation_players[parts[0]]
		if event.kind == "clip_start":
			player.play(parts[1],clip.blend_in_s,clip.rate)
			player.seek(clip.source_in_s+maxf(0.0,_time-clip.start_s)*clip.rate,true)
		elif event.kind == "clip_exit" and rest_animations.has(parts[0]):
			player.play(rest_animations[parts[0]],clip.blend_out_s)
		elif event.kind in ["clip_end","clip_cancel"] and clip.blend_out_s == 0:
			player.pause()
	elif clip and clip.source.kind == "audio":
		if event.kind == "clip_start":
			var player := AudioStreamPlayer.new()
			player.stream = audio_streams[clip.source.binding]
			player.pitch_scale = clip.rate*_speed
			player.volume_linear = 0.0 if clip.blend_in_s > 0 else clip.volume
			add_child(player)
			player.play(clip.source_in_s+maxf(0.0,_time-clip.start_s)*clip.rate)
			player.stream_paused = _paused
			_audio[event.id] = {"player":player,"clip":clip}
		elif event.kind in ["clip_end","clip_cancel"] and _audio.has(event.id):
			_audio[event.id].player.stop()
			_audio[event.id].player.queue_free()
			_audio.erase(event.id)
	if is_instance_valid(bridge): bridge.record_event("consumer",str(event.id)+"_"+str(event.kind))

func preview_state() -> Dictionary:
	var players := {}
	var audio := {}
	for key in animation_players:
		var player: AnimationPlayer = animation_players[key]
		players[key] = {"animation":str(player.current_animation),"position_s":player.current_animation_position}
	for key in _audio:
		var player: AudioStreamPlayer = _audio[key].player
		audio[key] = {"playing":player.playing,"paused":player.stream_paused,"volume":player.volume_linear,"pitch_scale":player.pitch_scale,"position_s":player.get_playback_position()}
	return {"elapsed_s":_time,"duration_s":_sequence.get("duration_s",0.0),"complete":_complete,"animation_players":players,"active_audio":_audio.size(),"audio_players":audio,"open_windows":_windows.keys(),"logic_events":_logic_events}

func preview_cancel() -> void:
	scheduler.stop()
	for item in _audio.values():
		item.player.stop()
		item.player.queue_free()
	_audio.clear()
	for player: AnimationPlayer in animation_players.values(): player.pause()

func preview_view(view: String) -> bool:
	if not cameras.has(view): return false
	cameras[view].make_current()
	return true

func preview_transport(paused: bool, speed: float) -> void:
	_paused = paused
	_speed = speed
	for item in _audio.values():
		item.player.stream_paused = paused
		item.player.pitch_scale = item.clip.rate*speed
