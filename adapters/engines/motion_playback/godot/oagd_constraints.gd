extends SkeletonModifier3D
## Optional feet and prop constraints, after the animated source pose. World units: metres.
## Call prepare before Skeleton3D.advance; read bones in modification_processed.
var feet := {}
var grip := {}
var actor: Node3D
var excluded: Array[RID] = []
var contacts := Vector2.ONE
var grounded := true
var holding := false
var two_handed := false
var contact := false
var prop: Node3D
var support_offset := Transform3D.IDENTITY
var main_offset := Transform3D.IDENTITY
var weights := Vector2.ZERO
var grip_weight := 0.0
var pelvis_offset := 0.0
var feet_status := ["disabled","disabled"]
var grip_status := "released"
var goals: Array[Vector3] = [Vector3.ZERO,Vector3.ZERO]
var support_goal := Transform3D.IDENTITY
var indices := {}
var dt := 0.0
var valid := false
var grip_requested := false

static func transform(row: Dictionary) -> Transform3D:
	var p: Array = row.position; var q: Array = row.rotation_xyzw
	return Transform3D(Basis(Quaternion(q[0],q[1],q[2],q[3])),Vector3(p[0],p[1],p[2]))
func configure(owner_node: Node3D, settings: Dictionary, exclude: Array[RID] = []) -> bool:
	valid = false; actor = owner_node; excluded = exclude
	var s := get_skeleton()
	if s == null or actor == null or settings.get("mode") != "contacts_v1": return false
	feet = settings.get("feet",{}).duplicate(true); grip = settings.get("grip",{}).duplicate(true); indices.clear()
	if feet.is_empty() and grip.is_empty(): return false
	if not feet.is_empty():
		for rule in [["sole_offset_m",0,.2],["probe_up_m",.01,1],["probe_down_m",.01,1],["max_step_m",.01,.4],["max_slope_deg",1,60],["max_pelvis_m",0,.3],["blend_s",.02,1]]:
			var value = feet.get(rule[0])
			if not (value is float or value is int) or not is_finite(value) or value < rule[1] or value > rule[2]: return false
		if feet.max_step_m > minf(feet.probe_up_m,feet.probe_down_m): return false
		if not feet.get("knee_pole") is Array or feet.knee_pole.size()!=3 or Vector3(feet.knee_pole[0],feet.knee_pole[1],feet.knee_pole[2]).length()<.1:return false
	if not grip.is_empty():
		if not grip.has("blend_s") or not is_finite(grip.blend_s) or grip.blend_s<.02 or grip.blend_s>1:return false
		if not grip.get("elbow_pole") is Array or grip.elbow_pole.size()!=3 or Vector3(grip.elbow_pole[0],grip.elbow_pole[1],grip.elbow_pole[2]).length()<.1:return false
		if not grip.has("sockets") or not grip.sockets.has("godot"):return false
		for key in ["main","support"]:
			var socket: Dictionary=grip.sockets.godot.get(key,{})
			if not socket.get("position") is Array or socket.position.size()!=3 or not socket.get("rotation_xyzw") is Array or socket.rotation_xyzw.size()!=4:return false
			var norm:=0.0
			for n in socket.position+socket.rotation_xyzw:
				if not (n is int or n is float) or not is_finite(n):return false
			for n in socket.rotation_xyzw:norm+=n*n
			if absf(norm-1)>.001:return false
	for pair in [["left",feet.get("left",[])],["right",feet.get("right",[])],["offhand",grip.get("offhand",[])]]:
		if pair[1].is_empty(): continue
		var ids: Array[int] = []
		for n in pair[1]: ids.append(s.find_bone(n))
		if ids.size() != 3 or ids.min() < 0 or s.get_bone_parent(ids[1]) != ids[0] or s.get_bone_parent(ids[2]) != ids[1]: return false
		indices[pair[0]] = ids
	if not feet.is_empty():
		indices.pelvis = s.find_bone(feet.pelvis)
		if indices.pelvis < 0: return false
		for chain_name in ["left","right"]:
			var parent: int=indices[chain_name][0]
			while parent>=0 and parent!=indices.pelvis:parent=s.get_bone_parent(parent)
			if parent<0:return false
	if not grip.is_empty():
		indices.main = s.find_bone(grip.main_hand)
		if indices.main < 0 or indices.offhand.has(indices.main): return false
		main_offset = transform(grip.sockets.godot.main); support_offset = transform(grip.sockets.godot.support)
	reset(); valid = true; return true
func reset() -> void:
	release(); weights = Vector2.ZERO; pelvis_offset = 0; contacts = Vector2.ONE; feet_status=["disabled","disabled"]
func take(target: Node3D, both := true) -> bool:
	if not valid or grip.is_empty() or not is_instance_valid(target): grip_status = "missing_target"; return false
	release(); prop = target; holding = true; two_handed = both; grip_status = "attached"; return true
func release() -> void:
	# The prop remains at its last world transform: no snap on drop or cancel.
	holding = false; contact = false; grip_weight = 0; prop = null; grip_status = "released"
func prepare(delta: float, on_ground: bool, stance: Vector2, support_contact: bool) -> void:
	dt = maxf(0,delta); grounded = on_ground; contacts = stance.clamp(Vector2.ZERO,Vector2.ONE); contact = support_contact
func world_pose(bone: int) -> Transform3D:
	return get_skeleton().global_transform * get_skeleton().get_bone_global_pose(bone)
func set_world(bone: int, pose: Transform3D) -> void:
	get_skeleton().set_bone_global_pose(bone,get_skeleton().global_transform.affine_inverse() * pose)
func direction(values: Array) -> Vector3:
	return actor.global_basis * Vector3(values[1],values[2],-values[0])
func solve(chain: Array, target: Vector3, pole: Vector3, weight: float, end_basis: Basis) -> bool:
	var a := world_pose(chain[0]); var b := world_pose(chain[1]); var c := world_pose(chain[2])
	var l1 := a.origin.distance_to(b.origin); var l2 := b.origin.distance_to(c.origin)
	var distance := a.origin.distance_to(target)
	if distance > l1+l2-.0001 or distance < absf(l1-l2)+.0001 or minf(l1,l2) < .0001: return false
	if weight <= 0: return true
	var aim := (target-a.origin).normalized(); var bend := pole - aim*pole.dot(aim)
	if bend.length_squared() < .000001: bend = b.origin-a.origin-aim*(b.origin-a.origin).dot(aim)
	if bend.length_squared() < .000001: return false
	var x := (l1*l1-l2*l2+distance*distance)/(2*distance)
	var knee := a.origin+aim*x+bend.normalized()*sqrt(maxf(0,l1*l1-x*x))
	var qa := Quaternion((b.origin-a.origin).normalized(),(knee-a.origin).normalized())
	var a_new := a; a_new.basis = Basis(Quaternion.IDENTITY.slerp(qa,weight))*a.basis; set_world(chain[0],a_new)
	var now_b := world_pose(chain[1]); var now_c := world_pose(chain[2])
	var qb := Quaternion((now_c.origin-now_b.origin).normalized(),(target-now_b.origin).normalized())
	now_b.basis = Basis(Quaternion.IDENTITY.slerp(qb,weight))*now_b.basis; set_world(chain[1],now_b)
	var end := world_pose(chain[2]); end.basis = Basis(end.basis.get_rotation_quaternion().slerp(end_basis.get_rotation_quaternion(),weight)).scaled(end.basis.get_scale()); set_world(chain[2],end)
	return true
func _process_modification_with_delta(_delta: float) -> void:
	if not valid: return
	var raw: Array[Transform3D] = []
	if not feet.is_empty():
		var normals: Array[Vector3] = [Vector3.UP,Vector3.UP]; var wanted := Vector2.ZERO; var shift := 0.0
		for i in range(2):
			var chain: Array = indices["left" if i == 0 else "right"]; var foot := world_pose(chain[2]); raw.append(foot)
			goals[i] = foot.origin; feet_status[i] = "airborne" if not grounded else "swing"
			if not grounded or contacts[i] <= 0: continue
			var query := PhysicsRayQueryParameters3D.create(foot.origin+Vector3.UP*float(feet.probe_up_m),foot.origin-Vector3.UP*float(feet.probe_down_m),1,excluded)
			var hit := get_world_3d().direct_space_state.intersect_ray(query)
			if hit.is_empty(): feet_status[i] = "no_ground"; continue
			var n: Vector3 = hit.normal; var target: Vector3 = hit.position+n*float(feet.sole_offset_m)
			if n.dot(Vector3.UP) < cos(deg_to_rad(feet.max_slope_deg)): feet_status[i] = "slope_limit"; continue
			if absf(target.y-foot.origin.y) > float(feet.max_step_m): feet_status[i] = "step_limit"; continue
			goals[i] = target; normals[i] = n; wanted[i] = contacts[i]; feet_status[i] = "contact"
			shift = minf(shift,(target.y-foot.origin.y)*contacts[i])
		for i in range(2): weights[i] = move_toward(weights[i],wanted[i],dt/float(feet.blend_s))
		pelvis_offset = move_toward(pelvis_offset,clampf(shift,-feet.max_pelvis_m,feet.max_pelvis_m),dt*float(feet.max_pelvis_m)/float(feet.blend_s))
		var pelvis := world_pose(indices.pelvis); pelvis.origin.y += pelvis_offset; set_world(indices.pelvis,pelvis)
		for i in range(2):
			var chain: Array = indices["left" if i == 0 else "right"]
			var goal := goals[i] if wanted[i] > 0 else raw[i].origin+Vector3.UP*pelvis_offset
			if not solve(chain,goal,direction(feet.knee_pole),weights[i],Basis(Quaternion(Vector3.UP,normals[i]))*raw[i].basis): weights[i]=0; feet_status[i] = "unreachable"
	if not grip.is_empty():
		if holding and not is_instance_valid(prop): release(); grip_status = "missing_target"
		if holding:
			var hand := world_pose(indices.main); hand.basis = hand.basis.orthonormalized()
			prop.global_transform = hand*main_offset
			support_goal = prop.global_transform*support_offset
			grip_status = "single_hand" if not two_handed else "window_closed" if not contact else "contact"
			var wanted := 1.0 if two_handed and contact else 0.0
			grip_weight = move_toward(grip_weight,wanted,dt/float(grip.blend_s))
			if grip_weight > 0 and not solve(indices.offhand,support_goal.origin,direction(grip.elbow_pole),grip_weight,support_goal.basis): grip_weight = 0; grip_status = "unreachable"
