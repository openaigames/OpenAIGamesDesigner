class_name OAGDQuery
extends RefCounted
## Nearest visible physical hit. The caller decides whether/how it can interact.
static func ray(world: World3D, origin: Vector3, direction: Vector3, distance: float, exclude: Array[RID] = []) -> Dictionary:
	if distance <= 0 or direction.length_squared() < 0.0001:
		return {}
	var query := PhysicsRayQueryParameters3D.create(origin, origin + direction.normalized() * distance, 1, exclude)
	return world.direct_space_state.intersect_ray(query)
