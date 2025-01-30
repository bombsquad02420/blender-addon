import os
import json
import bpy
import bpy_extras
from mathutils import Vector

"""
importing and exporting other types will work
but they may not be sensibly mapped in blender


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
"""
location_metadata = {
	'area_of_interest_bounds':  { 'draw': 'CUBE',   'size_represents': 'DIAMETER',  'description': "The region of the map that the player can normally access. This is used to position the camera. Only 1 per map is allowed." },
	'b':                        { 'draw': 'CUBE',   'size_represents': 'DIAMETER',  'description': "TODO." },
	'edge_box':                 { 'draw': 'CUBE',   'size_represents': 'DIAMETER',  'description': "TODO." },
	'ffa_spawn':                { 'draw': 'PLANE',  'size_represents': 'RADIUS',    'description': "The spawn region in free-for-all game mode." },
	'flag':                     { 'draw': 'POINT',  'size_represents': 'NA',        'description': "TODO." },
	'flag_default':             { 'draw': 'POINT',  'size_represents': 'NA',        'description': "The location of the main flag in gae modes like king-of-the-hill and choosen-one. Only 1 per map is allowed." },
	'goal':                     { 'draw': 'CUBE',   'size_represents': 'DIAMETER',  'description': "TODO." },
	'map_bounds':               { 'draw': 'CUBE',   'size_represents': 'DIAMETER',  'description': "The maximum region of the map. Actors outside this region will be despawned be the game immediately. Keep the ceiling sufficiently high so that bombs do not go outside the bounds while throwing. Only 1 per map is allowed." },
	'powerup_region':           { 'draw': 'PLANE',  'size_represents': 'DIAMETER',  'description': "TODO." },
	'powerup_spawn':            { 'draw': 'POINT',  'size_represents': 'NA',        'description': "Exact points where powerups will be spawned." },
	'race_mine':                { 'draw': 'POINT',  'size_represents': 'NA',        'description': "Exact points where mines and bombs will be spawned in race mode." },
	'race_point':               { 'draw': 'CUBE',   'size_represents': 'RADIUS',    'description': "Regions which measure the progression in the race." },
	'score_region':             { 'draw': 'CUBE',   'size_represents': 'DIAMETER',  'description': "TODO." },
	'shadow_lower_bottom':      { 'draw': 'POINT',  'size_represents': 'NA',        'description': "TODO. Only the vertical height is used by bombsquad." },
	'shadow_lower_top':         { 'draw': 'POINT',  'size_represents': 'NA',        'description': "TODO. Only the vertical height is used by bombsquad." },
	'shadow_upper_bottom':      { 'draw': 'POINT',  'size_represents': 'NA',        'description': "TODO. Only the vertical height is used by bombsquad." },
	'shadow_upper_top':         { 'draw': 'POINT',  'size_represents': 'NA',        'description': "TODO. Only the vertical height is used by bombsquad." },
	'spawn':                    { 'draw': 'PLANE',  'size_represents': 'RADIUS',    'description': "Spawn regions for the teams. Make sure they are in teh correct otder. Only 2 per map are allowed." },
	'spawn_by_flag':            { 'draw': 'PLANE',  'size_represents': 'RADIUS',    'description': "TODO" },
	'tnt':                      { 'draw': 'POINT',  'size_represents': 'NA',        'description': "The location of TNT." },
	'tnt_loc':                  { 'draw': 'POINT',  'size_represents': 'NA',        'description': "The location of TNT in the runaround game mode." },
}


# These matrices are different from the ones used in bob and cob formats
bs_to_bl_matrix = bpy_extras.io_utils.axis_conversion(from_forward='Z', from_up='-Y').to_3x3()
bl_to_bs_matrix = bpy_extras.io_utils.axis_conversion(to_forward='Z', to_up='-Y').to_3x3()


class IMPORT_SCENE_OT_bombsquad_leveldefs(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
	"""Load Bombsquad Level Defs"""
	bl_idname = "import_scene.bombsquad_leveldefs"
	bl_label = "Import Bombsquad Level Definitions"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}
	
	filename_ext = ".json"
	filter_glob: bpy.props.StringProperty(
		default="*.json",
		options={'HIDDEN'},
	)

	def execute(self, context):
		keywords = self.as_keywords(ignore=('filter_glob',))
		filepath = os.fsencode(keywords["filepath"])
		data = None
		with open(filepath, "r") as file:
			data = json.load(file)

		if data is None or "locations" not in data:
			return {'CANCELLED'}

		collection_name = bpy.path.display_name_from_filepath(filepath)
		scene = bpy.context.scene
		collection = bpy.data.collections.new(collection_name)
		bpy.context.scene.collection.children.link(collection)
		bpy.context.view_layer.update()

		for location_type, locations in data["locations"].items():
			if location_type not in location_metadata:
				self.report({'WARNING'}, f"Unrecognized key `{location_type}` in `{filepath}`. Continuing with the import but the result may not be drawn correctly. If this is supposed to be a valid key, please open an issue.")
			for location in locations:
				if "center" in location and "size" in location:
					center = Vector(location["center"][0:3]) @ bs_to_bl_matrix
					size = Vector(location["size"][0:3]).xzy
					if location_type in location_metadata and location_metadata[location_type]['size_represents'] == 'DIAMETER':
						size = size / 2
					if location_type in location_metadata and location_metadata[location_type]['draw'] == 'PLANE':
						size.z = 0.01
					# blender will autoincrement the counter if the name already exists
					name = location_type + '.000'
					self.add_cube(
						context,
						center=center,
						size=size,
						collection=collection.name,
						name=name
					)
				elif "center" in location:
					center = Vector(location["center"][0:3]) @ bs_to_bl_matrix
					self.add_point(
						context,
						center=center,
						collection=collection.name,
						name=name
					)

		bpy.ops.object.select_all(action='DESELECT')
		bpy.context.view_layer.update()
		return {'FINISHED'}

	def add_point(self, context,
			center, collection, name):
		bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', radius=0.25, location=center, scale=(1, 1, 1))
		empty = context.active_object
		empty.show_name = True
		empty.name = name
		bpy.data.collections[collection].objects.link(empty)
		context.collection.objects.unlink(empty)
		return empty

	def add_cube(self, context,
			center, size, collection, name):
		bpy.ops.object.empty_add(type='CUBE', align='WORLD', radius=1, location=center, scale=(1, 1, 1))
		empty = context.active_object
		empty.scale = size
		empty.show_name = True
		empty.name = name
		bpy.data.collections[collection].objects.link(empty)
		context.collection.objects.unlink(empty)
		return empty


class EXPORT_SCENE_OT_bombsquad_leveldefs(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
	"""Save Bombsquad Level Defs"""
	bl_idname = "export_scene.bombsquad_leveldefs"
	bl_label = "Export Bombsquad Level Definitions"
	bl_options = {'REGISTER', 'PRESET'}

	filename_ext = ".json"
	check_extension = True
	filter_glob: bpy.props.StringProperty(
		default="*.json",
		options={'HIDDEN'},
	)

	@classmethod
	def poll(cls, context):
		return context.collection is not None and len(context.collection.objects) > 0

	def execute(self, context):
		keywords = self.as_keywords(ignore=('filter_glob',))
		filepath = os.fsencode(keywords["filepath"])

		collection = context.collection
		objects = sorted(collection.objects.values(), key=lambda obj: obj.name)

		if len(objects)==0:
			return {'CANCELLED'}

		data_locations = {}
		for obj in objects:
			location_type = obj.name.split('.')[0]
			if location_type not in location_metadata:
				self.report({'WARNING'}, f"Unrecognized location empty `{obj.name}` in collection `{collection.name}`. Continuing with the export but the result may not be drawn correctly. If this is supposed to be a valid location, please open an issue.")
			if obj.type == "EMPTY" and obj.empty_display_type  == "CUBE":
				center = obj.matrix_world.to_translation()
				size = obj.matrix_world.to_scale()
				if location_type in location_metadata and location_metadata[location_type]['size_represents'] == 'DIAMETER':
					size = size * 2
				if location_type in location_metadata and location_metadata[location_type]['draw'] == 'PLANE':
					size.z = 1 # arbitrary value since it is not used by bobmsquad
				if location_type not in data_locations:
					data_locations[location_type] = []
				data_locations[location_type].append({
					"center": [round(n, 2) for n in center @ bl_to_bs_matrix],
					"size": [round(n, 2) for n in size.xzy],
				})
			elif obj.type == "EMPTY" and obj.empty_display_type  == "PLAIN_AXES":
				center = obj.matrix_world.to_translation()
				if location_type not in data_locations:
					data_locations[location_type] = []
				data_locations[location_type].append({
					"center": [round(n, 2) for n in center @ bl_to_bs_matrix],
				})

		if len(data_locations) == 0:
			self.report({'WARNING'}, f"Collection `{collection.name}` has no location data to export. Is the correct collection selected?")
			return {'FINISHED'}

		data = {}
		# TODO: add check_existing flag
		if os.path.exists(filepath):
			with open(filepath, 'r') as file:
				data = json.load(file)

		data["locations"] = data_locations

		with open(filepath, "w") as file:
			json.dump(data, file, indent=2, sort_keys=True)

		return {'FINISHED'}


# Enables importing files by draggin and dropping into the blender UI
# Enables export via collection exporter
class IO_FH_bombsquad_leveldefs(bpy.types.FileHandler):
	bl_idname = "IO_FH_bombsquad_leveldefs"
	bl_label = "BombSquad Level Definitions"
	bl_import_operator = "import_scene.bombsquad_leveldefs"
	bl_export_operator = "export_scene.bombsquad_leveldefs"
	bl_file_extensions = ".json"

	@classmethod
	def poll_drop(cls, context):
		# drop sohuld only be allowed in 3d view and outliner
		return bpy_extras.io_utils.poll_file_object_drop(context)


def menu_func_import_leveldefs(self, context):
	self.layout.operator(IMPORT_SCENE_OT_bombsquad_leveldefs.bl_idname, text="Bombsquad Level Definitions (.json)")


def menu_func_export_leveldefs(self, context):
	self.layout.operator(EXPORT_SCENE_OT_bombsquad_leveldefs.bl_idname, text="Bombsquad Level Definitions (.json)")


classes = (
	IMPORT_SCENE_OT_bombsquad_leveldefs,
	EXPORT_SCENE_OT_bombsquad_leveldefs,
	IO_FH_bombsquad_leveldefs,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import_leveldefs)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export_leveldefs)


def unregister():
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_leveldefs)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_leveldefs)
	_unregister()


if __name__ == "__main__":
	register()
