class_name ActionSequencePlayer
extends RefCounted

signal sequence_signal(value: Dictionary)
var data: Dictionary
var running := false
var time := 0.0
var _signals: Array[Dictionary] = []
var _active: Dictionary = {}
var _cursor := 0
var _windows: Dictionary = {}

func _number(value: Variant, minimum := 0.0, maximum := 120.0) -> bool:
	return (value is float or value is int) and is_finite(value) and value >= minimum and value <= maximum

func _add(t: float, kind: String, id: String, clip: Dictionary, order: int) -> void:
	_signals.append({"time":t,"kind":kind,"id":id,"clip":clip,"order":order,"index":_signals.size()})

func load_sequence(value: Dictionary) -> bool:
	stop()
	_signals.clear()
	if value.get("schema") != "action-sequence/1" or not _number(value.get("duration_s"),0.01):
		return false
	data = value.duplicate(true)
	var assets := {}
	var ids := {}
	for a in data.get("assets",[]):
		assets[a.id] = a
	for c in data.get("clips",[]):
		if ids.has(c.id) or not assets.has(c.asset): return false
		ids[c.id] = true
		for key in ["start_s","source_in_s","source_out_s","blend_in_s","blend_out_s"]:
			if not _number(c.get(key)): return false
		if not _number(c.get("rate"),0.1,4.0) or not _number(c.get("volume"),0.0,2.0): return false
		c["source"] = assets[c.asset]
		c["end_s"] = c.start_s + (c.source_out_s-c.source_in_s)/c.rate
		if c.source_out_s <= c.source_in_s or c.source_out_s > c.source.duration_s+0.0001 or c.end_s > data.duration_s+0.0001 or c.blend_in_s+c.blend_out_s > c.end_s-c.start_s+0.0001: return false
		_add(c.start_s,"clip_start",c.id,c,3)
		if c.blend_out_s > 0: _add(c.end_s-c.blend_out_s,"clip_exit",c.id,c,4)
		_add(c.end_s,"clip_end",c.id,c,0)
	for e in data.get("events",[]):
		if ids.has(e.id) or not _number(e.get("time_s"),0.0,data.duration_s): return false
		ids[e.id] = true
		_add(e.time_s,"event",e.id,{},2)
	for w in data.get("windows",[]):
		if ids.has(w.id) or not _number(w.get("start_s")) or not _number(w.get("end_s"),0.0,data.duration_s) or w.end_s <= w.start_s: return false
		ids[w.id] = true
		_add(w.start_s,"window_open",w.id,{},1)
		_add(w.end_s,"window_close",w.id,{},0)
	_signals.sort_custom(func(a,b): return a.time < b.time if a.time != b.time else (a.order < b.order if a.order != b.order else a.index < b.index))
	return true

func start_sequence() -> void:
	stop()
	_cursor = 0
	time = 0.0
	running = true
	advance(0.0)

func advance(elapsed: float) -> void:
	if not running or not is_finite(elapsed) or elapsed < time: return
	time = elapsed
	while running and _cursor < _signals.size() and _signals[_cursor].time <= elapsed+0.0000001:
		var s := _signals[_cursor]
		_cursor += 1
		if s.kind == "window_open": _windows[s.id] = true
		if s.kind == "window_close": _windows.erase(s.id)
		if s.kind == "clip_start": _active[s.id] = s.clip
		if s.kind == "clip_end": _active.erase(s.id)
		sequence_signal.emit(s)
	if elapsed >= data.duration_s: running = false

func stop() -> void:
	running = false
	for id in _windows.keys():
		sequence_signal.emit({"time":time,"kind":"window_cancel","id":id,"clip":{}})
	_windows.clear()
	for id in _active.keys():
		sequence_signal.emit({"time":time,"kind":"clip_cancel","id":id,"clip":_active[id]})
	_active.clear()
	running = false
