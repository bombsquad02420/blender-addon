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


# Run this in blender's interactive console to get location/rotation data
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
		'mirror': False,
	},
	'Torso': {
		'location': (0.000000, 0.000000, 0.496232),
		'rotation': (0, 0.000000, 0.000000),
		'mirror': False,
	},
	'Pelvis': {
		'location': (0.000000, -0.03582, 0.361509),
		'rotation': (-0.21104, 0.000000, 0.000000),
		'mirror': False,
	},
	'UpperArm': {
		'location': (-0.207339, 0.016968, 0.516395),
		'rotation': (1.75531, 0.185005, 0.000000),
		'mirror': True,
	},
	'ForeArm': {
		'location': (-0.199252, -0.013197, 0.372489),
		'rotation': (1.09994, 0.000000, 0.000000),
		'mirror': True,
	},
	'Hand': {
		'location': (-0.195932, -0.0641, 0.321099),
		'rotation': (0.82205, 0.000000, 0.000000),
		'mirror': True,
	},
	'UpperLeg': {
		'location': (-0.09192, -0.031631, 0.266533),
		'rotation': (1.37474, 0.000000, 0.000000),
		'mirror': True,
	},
	'LowerLeg': {
		'location': (-0.088037, -0.063052, 0.113304),
		'rotation': (1.5708, 0.000000, 0.000000),
		'mirror': True,
	},
	'Toes': {
		'location': (-0.086935, -0.11274, 0.069577),
		'rotation': (1.5708, 0.000000, 0.000000),
		'mirror': True,
	},
}


def get_character_part_name(fullname):
	for part in character_part_metadata:
		if fullname.endswith(part):
			return part
	return None