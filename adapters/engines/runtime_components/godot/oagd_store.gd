class_name OAGDStore
extends RefCounted
## Single-writer local journal. Game data is validated by the project before write/apply.
const LIMIT := 2097152
var root: String
var project_id: String
var data_version: int

func _init(directory: String, identity: String, version: int = 1) -> void:
	root = directory
	project_id = identity
	data_version = version

func valid_id(value: String) -> bool:
	if value.is_empty() or value.length() > 64: return false
	for c in value:
		if not (c >= "a" and c <= "z" or c >= "0" and c <= "9" or c == "_" or c == "-"): return false
	return true

func path(slot: String, generation: int) -> String:
	return root.path_join(slot + "." + str(generation) + ".json")

func _decode(file: String) -> Dictionary:
	var f := FileAccess.open(file, FileAccess.READ)
	if f == null or f.get_length() > LIMIT: return {}
	var parser := JSON.new()
	if parser.parse(f.get_as_text()) != OK: return {}
	var envelope = parser.data
	if not envelope is Dictionary or not envelope.get("body") is String or not envelope.get("sha1") is String: return {}
	if envelope.body.sha1_text() != envelope.sha1: return {}
	if parser.parse(envelope.body) != OK: return {}
	var body = parser.data
	if not body is Dictionary or not body.get("data") is Dictionary: return {}
	if not body.get("seq") is float or body.seq < 1 or body.seq != floor(body.seq) or body.seq > 9007199254740990.0: return {}
	return body

func read_slot(slot: String) -> Dictionary:
	if not valid_id(slot): return {"error": "invalid slot id"}
	var found: Array = []
	var damaged := false
	for i in 2:
		if not FileAccess.file_exists(path(slot, i)): continue
		var value := _decode(path(slot, i))
		if value.is_empty(): damaged = true
		else: value["generation"] = i; found.append(value)
	if found.is_empty(): return {"error": "corrupt slot" if damaged else "slot not found"}
	found.sort_custom(func(a, b): return a.seq > b.seq)
	var latest: Dictionary = found[0]
	if latest.get("schema") != 1 or latest.get("project") != project_id or latest.get("version") != data_version:
		return {"error": "incompatible schema, project or data version"}
	return {"error": "", "data": latest.data, "seq": int(latest.seq), "generation": latest.generation, "recovered": damaged}

func write_slot(slot: String, data: Dictionary) -> String:
	if not valid_id(slot) or project_id.is_empty() or data_version < 1: return "invalid store identity"
	var previous := read_slot(slot)
	# Never replace an incompatible or wholly damaged slot implicitly.
	if previous.error != "" and previous.error != "slot not found": return previous.error
	var seq := int(previous.get("seq", 0)) + 1
	var generation := 1 - int(previous.get("generation", 1))
	var body := JSON.stringify({"schema": 1, "project": project_id, "version": data_version, "seq": seq, "data": data})
	var encoded := JSON.stringify({"body": body, "sha1": body.sha1_text()})
	if encoded.to_utf8_buffer().size() > LIMIT: return "save exceeds 2 MiB"
	if DirAccess.make_dir_recursive_absolute(root) != OK: return "cannot create save directory"
	var temp := path(slot, generation) + ".tmp"
	var f := FileAccess.open(temp, FileAccess.WRITE)
	if f == null: return "cannot open save staging file"
	f.store_string(encoded)
	f.flush()
	var err := f.get_error()
	f.close()
	if err != OK or _decode(temp).is_empty(): return "staged save readback failed"
	# Only the older generation is replaced; the last valid generation survives.
	if DirAccess.rename_absolute(temp, path(slot, generation)) != OK: return "cannot commit save generation"
	return ""
