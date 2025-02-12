import os
import bpy

def map_range(value, from_start=0, from_end=1, to_start=0, to_end=127, clamp=False, precision=6):
	mapped_value = to_start + (to_end - to_start) * (value - from_start) / (from_end - from_start)
	mapped_value = round(mapped_value, precision)
	if precision == 0:
		mapped_value = int(mapped_value)
	if clamp:
		if to_start < to_end:
			mapped_value = max(min(mapped_value, to_end), to_start)
		else:
			mapped_value = max(min(mapped_value, to_start), to_end)
	return mapped_value


# Thanks EasyBPY!
def get_collection(ref = None):
	if ref is None:
		return bpy.context.view_layer.active_layer_collection.collection
	else:
		if isinstance(ref, str):
			if ref in bpy.data.collections:
				return bpy.data.collections[ref]
			else:
				return False
		else:
			return ref


# Thanks EasyBPY!
def set_active_collection(ref):
	colref = None
	if isinstance(ref, str):
		colref = get_collection(ref)
	else:
		colref = ref
	hir = bpy.context.view_layer.layer_collection
	search_layer_collection_in_hierarchy_and_set_active(colref, hir)


# Thanks EasyBPY!
def search_layer_collection_in_hierarchy_and_set_active(colref, hir):
	if isinstance(hir, bpy.types.LayerCollection):
		if hir.collection == colref:
			bpy.context.view_layer.active_layer_collection = hir
		else:
			for child in hir.children:
				search_layer_collection_in_hierarchy_and_set_active(colref, child)


def get_ba_data_path_from_filepath(filepath):
	path_parts = filepath.split(os.sep)
	try:
		ba_data_dir_index = path_parts.index('ba_data')
		return os.sep.join(path_parts[:ba_data_dir_index + 1])
	except ValueError:
		return None


# # Run this in blender's interactive console to get location/rotation data
# {
# 	ob.name: {
# 		'location': tuple(round(x, 5) for x in list(ob.matrix_world.to_translation())),
# 		'rotation': tuple(round(x, 5) for x in list(ob.matrix_world.to_euler())),
# 	}
# 	for ob in C.selected_objects
# }

character_part_metadata = {
	'Head': {
		'location': (0.000000, 0.000000, 0.942794),
		'rotation': (0, 0.000000, 0.000000),
		"location_exploded": (0.0, 0.0, 0.75866),
		'mirror': False,
	},
	'Torso': {
		'location': (0.000000, 0.000000, 0.496232),
		'rotation': (0, 0.000000, 0.000000),
		"location_exploded": (0.0, 0.0, 0.13636),
		'mirror': False,
	},
	'Pelvis': {
		'location': (0.000000, -0.03582, 0.361509),
		'rotation': (-0.21104, 0.000000, 0.000000),
		"location_exploded": (0.0, -0.05269, -0.213),
		'mirror': False,
	},
	'UpperArm': {
		'location': (-0.207339, 0.016968, 0.516395),
		'location_wide': (-0.30483, 0.01697, 0.54717),
		'rotation': (1.75531, 0.185005, 0.000000),
		'rotation_wide': (1.75531, 0.45408, 0.0),
		"location_exploded": (-0.86186, -0.02644, 0.34271),
		'mirror': True,
	},
	'ForeArm': {
		'location': (-0.199252, -0.013197, 0.372489),
		'location_wide': (-0.34297, -0.00887, 0.3871),
		'rotation': (1.09994, 0.000000, 0.000000),
		'rotation_wide': (1.09994, 0.12795, 0.0),
		"location_exploded": (-0.86246, -0.36209, 0.33985),
		'mirror': True,
	},
	'Hand': {
		'location': (-0.195932, -0.0641, 0.321099),
		'location_wide': (-0.34624, -0.05977, 0.33571),
		'rotation': (0.82205, 0.000000, 0.000000),
		'rotation_wide': (0.82205, 0.12795, 0.0),
		"location_exploded": (-0.8561, -0.61972, 0.36189),
		'mirror': True,
	},
	'UpperLeg': {
		'location': (-0.09192, -0.031631, 0.266533),
		'rotation': (1.37474, 0.000000, 0.000000),
		"location_exploded": (-0.50767, -0.01225, -0.34591),
		'mirror': True,
	},
	'LowerLeg': {
		'location': (-0.088037, -0.063052, 0.113304),
		'rotation': (1.5708, 0.000000, 0.000000),
		"location_exploded": (-0.50767, -0.37831, -0.31683),
		'mirror': True,
	},
	'Toes': {
		'location': (-0.086935, -0.11274, 0.069577),
		'rotation': (1.5708, 0.000000, 0.000000),
		"location_exploded": (-0.50034, -0.65128, -0.19831),
		'mirror': True,
	},
}

def get_character_part_name(fullname):
	for part in character_part_metadata:
		if fullname.endswith(part):
			return part
	return None

def get_character_name(bob_name):
	for part_name in character_part_metadata:
		if bob_name.endswith(part_name):
			return bob_name.removesuffix(part_name)
	return None

def get_possible_texture_file_names(bob_name):
	return [
		bob_name + '.dds',
		bob_name + 'Color.dds',
	]


"""
importing and exporting other types will work
but they may not be sensibly mapped in blender

To get a complete list of all location types,
run `cat data/maps/*.json | jq -r '.locations | keys.[]' | sort | uniq` in the ba_data folder.


{ 'size_represents': 'DIAMETER' }

these were known as boxes in previous versions of the game.
for boxes, the size represents the overall dimension (diameter).
otherwise, size is the distance of the edges of the box from the center (radius).

see: get_def_bound_box and get_start_position in ballistica source code
or search for `boxes['` in thhe ballistica source code


{ 'draw': 'PLANE' }

bombsquad ignores the vertical size for these regions,
so we reduce the cube down to a plain
to make it easier to read in the 3d view,

see: get_start_position and RunaroundGame in ballistica source code

# TODO: see getmaps in _appsubsystem.py for location desctiptions.
"""
location_metadata = {
	'area_of_interest_bounds': {
		'draw': 'CUBE', 'size_represents': 'DIAMETER',
		'description': "The region of the map that the player can normally access. This is used to position the camera. Only 1 per map is allowed.",
		'default_center': (0, 0, 0), 'default_size': (10, 10, 10),
	},
	'b': {
		'draw': 'CUBE', 'size_represents': 'DIAMETER',
		'description': "TODO.",
		'default_center': (0, 0, 0), 'default_size': (1, 1, 1),
	},
	'edge_box': {
		'draw': 'CUBE', 'size_represents': 'DIAMETER',
		'description': "TODO.",
		'default_center': (0, 0, 0), 'default_size': (1, 1, 1),
	},
	'ffa_spawn': {
		'draw': 'PLANE', 'size_represents': 'RADIUS',
		'description': "The spawn region in free-for-all game mode.",
		'default_center': (0, 0, 0), 'default_size': (0.5, 0.5, 0.5),
	},
	'flag': {
		'draw': 'POINT', 'size_represents': None,
		'description': "TODO.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'flag_default': {
		'draw': 'POINT', 'size_represents': None,
		'description': "The location of the main flag in gae modes like king-of-the-hill and choosen-one. Only 1 per map is allowed.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'goal': {
		'draw': 'CUBE', 'size_represents': 'DIAMETER',
		'description': "TODO.",
		'default_center': (0, 0, 0), 'default_size': (1, 1, 1),
	},
	'map_bounds': {
		'draw': 'CUBE', 'size_represents': 'DIAMETER',
		'description': "The maximum region of the map. Actors outside this region will be despawned be the game immediately. Keep the ceiling sufficiently high so that bombs do not go outside the bounds while throwing. Only 1 per map is allowed.",
		'default_center': (0, 0, 0), 'default_size': (10, 10, 10),
	},
	'powerup_region': {
		'draw': 'PLANE', 'size_represents': 'DIAMETER',
		'description': "TODO.",
		'default_center': (0, 0, 0), 'default_size': (1, 1, 1),
	},
	'powerup_spawn': {
		'draw': 'POINT', 'size_represents': None,
		'description': "Exact points where powerups will be spawned.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'race_mine': {
		'draw': 'POINT', 'size_represents': None,
		'description': "Exact points where mines and bombs will be spawned in race mode.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'race_point': {
		'draw': 'CUBE', 'size_represents': 'RADIUS',
		'description': "Regions which measure the progression in the race.",
		'default_center': (0, 0, 0), 'default_size': (1, 1, 1),
	},
	'score_region': {
		'draw': 'CUBE', 'size_represents': 'DIAMETER',
		'description': "TODO.",
		'default_center': (0, 0, 0), 'default_size': (1, 1, 1),
	},
	'shadow_lower_bottom': {
		'draw': 'POINT', 'size_represents': None,
		'description': "TODO. Only the vertical height is used by bombsquad.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'shadow_lower_top': {
		'draw': 'POINT', 'size_represents': None,
		'description': "TODO. Only the vertical height is used by bombsquad.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'shadow_upper_bottom': {
		'draw': 'POINT', 'size_represents': None,
		'description': "TODO. Only the vertical height is used by bombsquad.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'shadow_upper_top': {
		'draw': 'POINT', 'size_represents': None,
		'description': "TODO. Only the vertical height is used by bombsquad.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'spawn': {
		'draw': 'PLANE', 'size_represents': 'RADIUS',
		'description': "Spawn regions for the teams. Make sure they are in teh correct otder. Only 2 per map are allowed.",
		'default_center': (0, 0, 0), 'default_size': (0.5, 0.5, 0.5),
	},
	# FIXME: cragCastle defines spawn_by_flag as POINT
	'spawn_by_flag': {
		'draw': 'PLANE', 'size_represents': 'RADIUS',
		'description': "TODO",
		'default_center': (0, 0, 0), 'default_size': (0.5, 0.5, 0.5),
	},
	'tnt': {
		'draw': 'POINT', 'size_represents': None,
		'description': "The location of TNT.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
	'tnt_loc': {
		'draw': 'POINT', 'size_represents': None,
		'description': "The location of TNT in the runaround game mode.",
		'default_center': (0, 0, 0), 'default_size': None,
	},
}

known_location_type_items = tuple([
	(key, bpy.path.display_name(key), metadata['description']) for key, metadata in location_metadata.items()
])

custom_location_type_items = (
	('CUBE', 'Cube', ''),
	# ('PLANE', 'Plane', ''),
	('POINT', 'Point', ''),
)


def add_point(context, name, center=None):
	empty = bpy.data.objects.new(name, None)
	empty.empty_display_type = 'PLAIN_AXES'
	empty.empty_display_size = 0.25
	if center:
		empty.location = center
	empty.lock_rotation[0] = True
	empty.lock_rotation[1] = True
	empty.lock_rotation[2] = True
	context.collection.objects.link(empty)
	empty.show_name = True
	return empty

def add_cube(context, name, center=None, size=None):
	empty = bpy.data.objects.new(name, None)
	empty.empty_display_type = 'CUBE'
	empty.empty_display_size = 1
	if center:
		empty.location = center
	if size:
		empty.scale = size
	empty.lock_rotation[0] = True
	empty.lock_rotation[1] = True
	empty.lock_rotation[2] = True
	context.collection.objects.link(empty)
	empty.show_name = True
	return empty

def add_plane(context, name, center=None, size=None):
	empty = bpy.data.objects.new(name, None)
	empty.empty_display_type = 'CUBE'
	empty.empty_display_size = 1
	if center:
		empty.location = center
	if size:
		empty.scale = size
	empty.scale[2] = 0.01
	empty.lock_scale[2] = True
	empty.lock_rotation[0] = True
	empty.lock_rotation[1] = True
	empty.lock_rotation[2] = True
	context.collection.objects.link(empty)
	empty.show_name = True
	return empty

