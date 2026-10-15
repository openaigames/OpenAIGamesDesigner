extends SceneTree
func _initialize() -> void: call_deferred("build")
func own(node: Node, top: Node) -> void:
	for child in node.get_children():
		child.owner=top
		# Preserve nested PackedScene ownership. Re-owning its descendants creates duplicate serialized nodes.
		if child.scene_file_path.is_empty():own(child,top)
func build() -> void:
	for room in ["a","b"]:
		var path: String="res://room_"+room+".tscn"
		if FileAccess.file_exists(path):push_error("Existing room is project-owned");quit(1);return
		var top:=Node3D.new();top.name="Room_"+room;root.add_child(top)
		NavigationServer3D.map_set_cell_size(top.get_world_3d().navigation_map,.1);NavigationServer3D.map_set_cell_height(top.get_world_3d().navigation_map,.05)
		var region:=NavigationRegion3D.new();top.add_child(region)
		region.add_child(load("res://static_scene.tscn").instantiate())
		var nav:=NavigationMesh.new();nav.cell_size=.1;nav.cell_height=.05;nav.agent_radius=.5;nav.agent_height=1.9;nav.agent_max_climb=.25;nav.agent_max_slope=35;nav.region_min_size=1;nav.region_merge_size=0
		nav.geometry_parsed_geometry_type=NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
		region.navigation_mesh=nav;region.bake_navigation_mesh(false)
		if nav.get_polygon_count()==0:push_error("Empty navigation");quit(1);return
		own(top,top);var packed:=PackedScene.new();packed.pack(top)
		if ResourceSaver.save(packed,path)!=OK:quit(1);return
		top.free()
	quit()
