import os
import json
import bpy
import bpy_extras
from mathutils import Vector

from . import utils

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

	setup_collection_exporter: bpy.props.BoolProperty(
		name="Setup Collection Exporter",
		description="Automatically configure a collection exporter for the imported leveldefs",
		default=False,
	)

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")
		
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

		# IMPORTANT: we set the newly created collection as active,
		# so we can freely call operators that work on active collection,
		# example: add primitives, collection exporters, etc.
		utils.set_active_collection(collection)

		print(f"{self.__class__.__name__}: [INFO] Created collection {collection_name} to import to.")

		for location_type, locations in data["locations"].items():
			if location_type not in location_metadata:
				self.report({'WARNING'}, f"Unrecognized key `{location_type}` in `{filepath}`. Continuing with the import but the result may not be drawn correctly. If this is supposed to be a valid key, please open an issue.")
				print(f"{self.__class__.__name__}: [WARNING] Unrecognized location {location_type}")
			
			# blender will autoincrement the counter if the name already exists
			name = location_type + '.000'
			
			for location in locations:
				if "center" in location and "size" in location:
					center = Vector(location["center"][0:3]) @ bs_to_bl_matrix
					size = Vector(location["size"][0:3]).xzy
					
					if location_type in location_metadata and location_metadata[location_type]['size_represents'] == 'DIAMETER':
						size = size / 2
					
					if location_type in location_metadata and location_metadata[location_type]['draw'] == 'PLANE':
						print(f"{self.__class__.__name__}: [INFO] Adding location {location_type} at center {center} and size {size} as PLANE.")
						self.add_plane(
							context,
							name=name,
							center=center,
							size=size,
						)
					else:
						print(f"{self.__class__.__name__}: [INFO] Adding location {location_type} at center {center} and size {size} as CUBE.")
						self.add_cube(
							context,
							name=name,
							center=center,
							size=size,
						)
				
				elif "center" in location:
					center = Vector(location["center"][0:3]) @ bs_to_bl_matrix
					
					print(f"{self.__class__.__name__}: [INFO] Adding location {location_type} at center {center} as POINT.")
					self.add_point(
						context,
						name=name,
						center=center,
					)

		bpy.ops.object.select_all(action='DESELECT')
		bpy.context.view_layer.update()

		if self.setup_collection_exporter:
			bpy.ops.collection.exporter_add(name='IO_FH_bombsquad_leveldefs')
			exporter = collection.exporters[-1]
			exporter.export_properties.filepath = self.filepath
			print(f"{self.__class__.__name__}: [INFO] Created collection exporter for collection `{collection.name}`.")

		print(f"{self.__class__.__name__}: [INFO] Finished importing {filepath}")
		return {'FINISHED'}

	@classmethod
	def add_point(cls, context,
			name, center):
		empty = bpy.data.objects.new(name, None)
		empty.empty_display_type = 'PLAIN_AXES'
		empty.empty_display_size = 0.25
		empty.location = center
		empty.lock_rotation[0] = True
		empty.lock_rotation[1] = True
		empty.lock_rotation[2] = True
		context.collection.objects.link(empty)
		empty.show_name = True
		return empty

	@classmethod
	def add_cube(cls, context,
			name, center, size):
		empty = bpy.data.objects.new(name, None)
		empty.empty_display_type = 'CUBE'
		empty.empty_display_size = 1
		empty.location = center
		empty.scale = size
		empty.lock_rotation[0] = True
		empty.lock_rotation[1] = True
		empty.lock_rotation[2] = True
		context.collection.objects.link(empty)
		empty.show_name = True
		return empty

	@classmethod
	def add_plane(cls, context,
			name, center, size):
		empty = bpy.data.objects.new(name, None)
		empty.empty_display_type = 'CUBE'
		empty.empty_display_size = 1
		empty.location = center
		empty.scale = size
		empty.scale[2] = 0.01
		empty.lock_scale[2] = True
		empty.lock_rotation[0] = True
		empty.lock_rotation[1] = True
		empty.lock_rotation[2] = True
		context.collection.objects.link(empty)
		empty.show_name = True
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

	# this is set by the collection exporter feature.
	collection: bpy.props.StringProperty(
		name="Source Collection",
		description="Export only objects from this collection (and its children)",
		default="",
	)

	@classmethod
	def poll(cls, context):
		return context.collection is not None and len(context.collection.objects) > 0

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")
		
		keywords = self.as_keywords(ignore=('filter_glob',))
		filepath = os.fsencode(keywords["filepath"])

		collection = None

		if self.collection:
			print(f"{self.__class__.__name__}: [INFO] Using collection `{self.collection}` for export because you are using collection exporter.")
			collection = bpy.data.collections[self.collection]
		else:
			print(f"{self.__class__.__name__}: [INFO] Using selected collection `{collection}` for export.")
			collection = context.collection

		# sort objects by name, because order of locations is important to bombsquad to determine correct team / flag.
		objects = sorted(collection.objects.values(), key=lambda obj: obj.name)

		if len(objects)==0:
			print(f"{self.__class__.__name__}: [INFO] No objects in collection `{collection.name}`. Nothing to do.")
			return {'CANCELLED'}

		print(f"{self.__class__.__name__}: [INFO] Exporting collection `{collection.name}` with {len(objects)} objects")

		data_locations = {}
		for obj in objects:
			location_type = obj.name.split('.')[0]
			
			if location_type not in location_metadata:
				self.report({'WARNING'}, f"Unrecognized location empty `{obj.name}` in collection `{collection.name}`. Continuing with the export but the result may not be drawn correctly. If this is supposed to be a valid location, please open an issue.")
				print(f"{self.__class__.__name__}: [WARNING] Unrecognized location {location_type}")
			
			if obj.type == "EMPTY" and obj.empty_display_type == "CUBE":
				center = obj.matrix_world.to_translation()
				size = obj.matrix_world.to_scale()
				
				print(f"{self.__class__.__name__}: [INFO] Adding object {obj.name} to locations {location_type} as CUBE.")
				
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

				print(f"{self.__class__.__name__}: [INFO] Adding object {obj.name} to locations {location_type} as POINT.")
				
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
				print(f"{self.__class__.__name__}: [INFO] File {filepath} already exists. Exported data will be merged into this file.")
				data = json.load(file)

		data["locations"] = data_locations

		with open(filepath, "w") as file:
			json.dump(data, file, indent=2, sort_keys=True)

		print(f"{self.__class__.__name__}: [INFO] Finished exporting {filepath}")
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
