extends Node3D
var ring: MeshInstance3D
var material: StandardMaterial3D

func _init() -> void:
	ring = MeshInstance3D.new(); ring.mesh = TorusMesh.new()
	ring.mesh.inner_radius = .65; ring.mesh.outer_radius = .8
	material = StandardMaterial3D.new(); material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring.material_override = material; add_child(ring)

func sample(age: float, strength: float, color: Color) -> void:
	var phase := fmod(age, 1.0)
	ring.scale = Vector3.ONE * (1.0 + phase * 1.3) * maxf(.1, strength)
	ring.position.y = .12 + sin(age * 4) * .04
	material.albedo_color = color * (1.0 - phase * .45)
