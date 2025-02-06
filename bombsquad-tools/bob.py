import os
import struct
import bpy
import bmesh
import bpy_extras

from . import utils


"""
.BOB File Structure:

MAGIC 45623 (I)
meshFormat  (I)
vertexCount (I)
faceCount   (I)
VertexObject x vertexCount (fff HH hhh xx)
index x faceCount*3 (b / H / I)

struct VertexObjectFull {
	float position[3];
	bs_uint16 uv[2]; // normalized to 16 bit unsigned ints 0 - 65535
	bs_sint16  normal[3]; // normalized to 16 bit signed ints -32768 - 32767
	bs_uint8 _padding[2];
};

.
. Blender 3D Coordinates         BombSquad 3D Coordinates
.
.       +Z                               +Y
.       ^                                ^
.       | ^ +Y                           |
.       |/                               |
.       +-----> +X                       +-----> +X
.                                       /
.                                      v +Z
.
.
. Blender UV Coordinates         BombSquad UV Coordinates
.
.       +Y [0,1]                         +-----> +X Int[0,65535]
.       ^                                |
.       |                                |
.       |                                v
.       +-----> +X [0,1]                 +Y Int[0,65535]
.
"""


BOB_FILE_ID = 45623

bs_to_bl_matrix = bpy_extras.io_utils.axis_conversion(from_forward='-Z', from_up='Y').to_4x4()
bl_to_bs_matrix = bpy_extras.io_utils.axis_conversion(to_forward='-Z', to_up='Y').to_4x4()

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


def _get_character_part_name(fullname):
	for part in character_part_metadata:
		if fullname.endswith(part):
			return part
	return None


def to_mesh(mesh, bob_data):
	verts = [vert["pos"] for vert in bob_data["vertices"]]
	faces = [face["indices"] for face in bob_data["faces"]]
	mesh.from_pydata(verts, [], faces)

	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.faces.ensure_lookup_table()
	# bm.verts.ensure_lookup_table()
	
	for i, face in enumerate(bm.faces):
		for vi, vert in enumerate(face.verts):
			normal = bob_data["vertices"][faces[i][vi]]["norm"]
			vert.normal = (
				utils.map_range(normal[0], from_start=-32767, from_end=32767, to_start=-1, to_end=1, clamp=True, precision=6),
				utils.map_range(normal[1], from_start=-32767, from_end=32767, to_start=-1, to_end=1, clamp=True, precision=6),
				utils.map_range(normal[2], from_start=-32767, from_end=32767, to_start=-1, to_end=1, clamp=True, precision=6),
			)
			# bm.verts[vi].normal = vert.normal

	uv_layer = bm.loops.layers.uv.verify()
	for i, face in enumerate(bm.faces):
		for vi, vert in enumerate(face.verts):
			uv = bob_data["vertices"][faces[i][vi]]["uv"]
			uv = (
				utils.map_range(uv[0], from_start=0, from_end=65535, to_start=0, to_end=1, clamp=True, precision=6),
				utils.map_range(uv[1], from_start=0, from_end=65535, to_start=1, to_end=0, clamp=True, precision=6),
			)
			face.loops[vi][uv_layer].uv = uv

	bm.transform(bs_to_bl_matrix)

	bm.to_mesh(mesh)
	bm.free()

	mesh.validate()
	mesh.update()

	return mesh


def _find_index(lst, ref_item, comparator):
	for i, item in enumerate(lst):
		if comparator(ref_item, item):
			return i
	return -1


def _is_same_vertex(vert1, vert2):
	is_same_pos = (vert1["pos"] - vert2["pos"]).length < 0.001
	is_same_norm = (vert1["norm"] - vert2["norm"]).length < 0.001
	is_same_uv = (vert1["uv"] - vert2["uv"]).length < 0.001
	return is_same_pos and is_same_norm and is_same_uv


def from_mesh(mesh):
	"""
	.bob only supports faces with exactly 3 vertices,
	so we need to triangulate our mesh first.
	"""

	"""
	.bob has uv coordinates associated with each vertex,
	but blender has uv coordinates associated with each face.
	since the same vertex can have different uv coordinates in different faces.
	To work around this limitation,
	we create a new vertex whenever we encounter a vertex with different uv coordinates.
	This is also call "Rip Vertex" or "Split Edge" in blender,
	but here we implement it manually.
	"""

	vertices = []
	faces = []

	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.faces.ensure_lookup_table()
	# bm.verts.ensure_lookup_table()

	bm.transform(bl_to_bs_matrix)

	bmesh.ops.triangulate(bm, faces=bm.faces)

	uv_layer = None
	if len(bm.loops.layers.uv) > 0:
		uv_layer = bm.loops.layers.uv[0]
	for i, face in enumerate(bm.faces):
		faceverts = []
		for vi, vert in enumerate(face.verts):
			uv = face.loops[vi][uv_layer].uv if uv_layer else (0, 0)
			# orig_vert = bm.verts[vi]
			current_vertex = {
				"pos": vert.co,
				"uv":  uv,
				"norm": vert.normal,
			}
			index = _find_index(vertices, current_vertex, _is_same_vertex)
			if index == -1:
				vertices.append(current_vertex)
				faceverts.append(len(vertices) - 1)
			else:
				faceverts.append(index)
		faces.append({
			"indices": faceverts
		})

	bm.free()

	return {
		"vertices": [{
			"pos": vertex["pos"],
			"uv": (
				utils.map_range(vertex["uv"][0], from_start=0, from_end=1, to_start=0, to_end=65535, clamp=True, precision=0),
				utils.map_range(vertex["uv"][1], from_start=1, from_end=0, to_start=0, to_end=65535, clamp=True, precision=0),
			),
			"norm": (
				utils.map_range(vertex["norm"][0], from_start=-1, from_end=1, to_start=-32767, to_end=32767, clamp=True, precision=0),
				utils.map_range(vertex["norm"][1], from_start=-1, from_end=1, to_start=-32767, to_end=32767, clamp=True, precision=0),
				utils.map_range(vertex["norm"][2], from_start=-1, from_end=1, to_start=-32767, to_end=32767, clamp=True, precision=0),
			),
		} for vertex in vertices],
		"faces": faces,
	}


def serialize(data, file):
	def writestruct(s, *args):
		file.write(struct.pack(s, *args))

	vertexCount = len(data["vertices"])
	faceCount = len(data["faces"])
	meshFormat = 1 if vertexCount < 65536 else 2

	writestruct('<I', BOB_FILE_ID)
	writestruct('<I', meshFormat)
	writestruct('<I', vertexCount)
	writestruct('<I', faceCount)

	for vert in data["vertices"]:
		writestruct('<fff', vert["pos"][0], vert["pos"][1], vert["pos"][2])
		writestruct('<HH', vert["uv"][0], vert["uv"][1])
		writestruct('<hhh', vert["norm"][0], vert["norm"][1], vert["norm"][2])
		writestruct('xx')

	for face in data["faces"]:
		writestruct('<HHH' if meshFormat == 1 else '<III', face["indices"][0], face["indices"][1], face["indices"][2])

	return


def deserialize(file):
	def readstruct(s):
		tup = struct.unpack(s, file.read(struct.calcsize(s)))
		return tup[0] if len(tup) == 1 else tup

	assert readstruct("<I") == BOB_FILE_ID
	meshFormat = readstruct("<I")
	assert meshFormat in [0, 1, 2]

	vertexCount = readstruct("<I")
	faceCount = readstruct("<I")

	vertices = []
	faces = []

	for i in range(vertexCount):
		pos = readstruct("<fff")
		uv = readstruct("<HH")
		norm = readstruct("<hhh")
		readstruct("xx")
		vertices.append({
			"pos": pos,
			"uv": uv,
			"norm": norm,
		})

	for i in range(faceCount):
		if meshFormat == 0:
			# MESH_FORMAT_UV16_N8_INDEX8
			indices = readstruct("<bbb")
			faces.append({
				"indices": indices
			})
		elif meshFormat == 1:
			# MESH_FORMAT_UV16_N8_INDEX16
			indices = readstruct("<HHH")
			faces.append({
				"indices": indices
			})
		elif meshFormat == 2:
			# MESH_FORMAT_UV16_N8_INDEX32
			indices = readstruct("<III")
			faces.append({
				"indices": indices
			})

	return {
		"vertices": vertices,
		"faces": faces,
	}


class IMPORT_MESH_OT_bombsquad_bob(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
	"""Load a Bombsquad Mesh file"""
	bl_idname = "import_mesh.bombsquad_bob"
	bl_label = "Import Bombsquad Mesh"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	filename_ext = ".bob"
	filter_glob: bpy.props.StringProperty(
		default="*.bob",
		options={'HIDDEN'},
	)

	files: bpy.props.CollectionProperty(
		name="File Path",
		type=bpy.types.OperatorFileListElement,
	)

	group_into_collection: bpy.props.BoolProperty(
		name="Group into collection",
		description="If you are importing multiple files, create a new collection and add the imported meshes to it",
		default=False,
	)

	setup_collection_exporter: bpy.props.BoolProperty(
		name="Setup Collection Exporter",
		description="Automatically configure a collection exporter for the imported meshes if group_into_collection is checked",
		default=False,
	)

	arrange_character_meshes: bpy.props.BoolProperty(
		name="Arrange Character Meshes",
		description="",
		default=False,
	)

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		keywords = self.as_keywords(ignore=(
			'filter_glob',
			'files',
			'filepath',
		))
		
		should_create_collection = self.files and self.group_into_collection
		is_character = False
 
		collection = None
		if should_create_collection:
			display_name = bpy.path.display_name_from_filepath(self.files[0].name)
			character_part = _get_character_part_name(display_name)

			if character_part is not None:
				is_character = True
				collection_name = display_name.rstrip(character_part)
				collection = bpy.data.collections.new(collection_name)
				print(f"{self.__class__.__name__}: [INFO] Created collection `{collection_name}` because you are importing a character.")
			
			else:
				collection = bpy.data.collections.new(display_name)
				print(f"{self.__class__.__name__}: [INFO] Created collection `{collection.name}`.")

			scene = bpy.context.scene
			bpy.context.scene.collection.children.link(collection)
			bpy.context.view_layer.update()

		ret = None
		if self.files:
			# Multiple file import
			ret = {'CANCELLED'}
			dirname = os.path.dirname(self.filepath)
			for file in self.files:
				path = os.path.join(dirname, file.name)
				if self.import_bob(context, path, collection=collection, **keywords) == {'FINISHED'}:
					ret = {'FINISHED'}
				else:
					self.report({'WARNING'}, f"The file `{path}` was not imported.")
		else:
			# Single file import
			ret = self.import_bob(context, self.filepath, collection=collection, **keywords)
	
		if ret != {'FINISHED'}:
			return {'CANCELLED'}

		if should_create_collection and collection is not None and self.setup_collection_exporter:
			utils.set_active_collection(collection)
			bpy.ops.collection.exporter_add(name='IO_FH_bombsquad_bob')
			exporter = collection.exporters[-1]
			exporter.export_properties.filepath = self.filepath
			if is_character:
				exporter.export_properties.apply_object_transformations = False
				exporter.export_properties.apply_modifiers = True
			print(f"{self.__class__.__name__}: [INFO] Created collection exporter for collection `{collection.name}`.")

		return {'FINISHED'}

	def import_bob(self, context, filepath, collection=None, **options):
		print(f"{self.__class__.__name__}: [INFO] Importing `{filepath}` with options {options}")
		filepath = os.fsencode(filepath)
		
		bob_data = None
		with open(filepath, 'rb') as file:
			bob_data = deserialize(file)

		bob_name = bpy.path.display_name_from_filepath(filepath)
		mesh = bpy.data.meshes.new(name=bob_name)
		mesh = to_mesh(mesh=mesh, bob_data=bob_data)

		if not mesh:
			return {'CANCELLED'}

		obj = bpy.data.objects.new(bob_name, mesh)
		if collection:
			collection.objects.link(obj)
		else:
			context.scene.collection.objects.link(obj)

		character_part_name = _get_character_part_name(bob_name)
		if character_part_name is not None and options['arrange_character_meshes']:
			print(f"{self.__class__.__name__}: [INFO] Detected {filepath} is a `{character_part_name}` and will be arranged.")
			part_metadata = character_part_metadata[character_part_name]
			obj.location = part_metadata['location']
			obj.rotation_euler = part_metadata['rotation']

		bpy.ops.object.select_all(action='DESELECT')
		obj.select_set(True)
		
		context.view_layer.objects.active = obj
		context.view_layer.update()
		
		return {'FINISHED'}


class EXPORT_MESH_OT_bombsquad_bob(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
	"""Save a Bombsquad Mesh file"""
	bl_idname = "export_mesh.bombsquad_bob"
	bl_label = "Export Bombsquad Mesh"
	bl_options = {'REGISTER', 'PRESET'}

	filter_glob: bpy.props.StringProperty(
		default="*.bob",
		options={'HIDDEN'},
	)
	check_extension = True
	filename_ext = ".bob"

	# this is set by the collection exporter feature.
	collection: bpy.props.StringProperty(
		name="Source Collection",
		description="Export only objects from this collection",
		default="",
	)

	apply_object_transformations: bpy.props.BoolProperty(
		name="Apply Object Transformations",
		description="Export mesh geometry with translation, rotation and scaling applied",
		default=True,
	)

	apply_modifiers: bpy.props.BoolProperty(
		name="Apply Modifiers",
		description="Exoprt mesh geometry with modifiers applied (as visible in render)",
		default=True,
	)

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		keywords = self.as_keywords(ignore=(
			'check_existing',
			'filter_glob',
			'filepath',
			'directory',
			'collection',
		))

		if self.collection:
			collection = bpy.data.collections[self.collection]
			objects = collection.objects

			if len(objects)==0:
				print(f"{self.__class__.__name__}: [INFO] No objects in collection `{collection.name}`. Nothing to do.")
				return {'CANCELLED'}
			else:
				print(f"{self.__class__.__name__}: [INFO] Exporting collection `{collection.name}` with {len(objects)} objects")

			ret = {'CANCELLED'}
			for obj in objects:
				if not obj.data:
					# skip empty
					continue
				dirname = os.path.dirname(self.filepath)
				filename = bpy.path.display_name_to_filepath(obj.name) + '.bob'
				filepath = os.path.join(dirname, filename)
				if self.export_bob(context, obj, filepath, **keywords) == {'FINISHED'}:
					ret = {'FINISHED'}
				else:
					self.report({'WARNING'}, f"The file `{path}` was not exported.")
			return ret
		
		else:
			# we are manually exporting a single object fro the menu
			obj = context.active_object
			selected_objects = context.selected_objects
			
			if len(selected_objects) > 1:
				print(f"{self.__class__.__name__}: [WARN] Multiple objects selected. Only the active object will be exported.")
				self.report({'WARNING'}, f"Multiple objects selected. Only the active object will be exported.")

			print(f"{self.__class__.__name__}: [INFO] Exporting active object `{obj.name}`.")

			return self.export_bob(context, obj, self.filepath, **keywords)

	def export_bob(self, context, obj, filepath, **options):
		print(f"{self.__class__.__name__}: [INFO] Exporting object `{obj.name}` to `{filepath}`")

		mesh = None
		if options['apply_modifiers']:
			depsgraph = context.evaluated_depsgraph_get()
			modified_obj = obj.evaluated_get(depsgraph)
			mesh = bpy.data.meshes.new_from_object(modified_obj, preserve_all_data_layers=True, depsgraph=depsgraph)
		else:
			mesh = obj.to_mesh(preserve_all_data_layers=True)

		if options['apply_object_transformations']:
			mesh.transform(obj.matrix_world)

		filepath = os.fsencode(filepath)
		with open(filepath, 'wb') as file:
			bob_data = from_mesh(mesh)
			serialize(bob_data, file)

		print(f"{self.__class__.__name__}: [INFO] Exported object `{obj.name}` to `{filepath}`")

		return {'FINISHED'}

	def draw(self, context):
		is_file_browser = context.space_data.type == 'FILE_BROWSER'
		is_collection_exporter = context.space_data.type == 'PROPERTIES'

		layout = self.layout

		if is_file_browser:
			col = layout.column(align=True)
			self.draw_file_browser_props(col)

		if is_collection_exporter:
			col = layout.column(align=True)
			self.draw_collection_exporter_props(col)

		col = layout.column(align=True)
		self.draw_props(layout)

	def draw_file_browser_props(self, layout):
		pass

	def draw_collection_exporter_props(self, layout):
		layout.label(text="The name of the object will be used as the final file name for export.", icon="INFO")

	def draw_props(self, layout):
		layout.prop(self, 'apply_object_transformations')
		layout.prop(self, 'apply_modifiers')


# Enables importing files by draggin and dropping into the blender UI
# Enables export via collection exporter
class IO_FH_bombsquad_bob(bpy.types.FileHandler):
	bl_idname = "IO_FH_bombsquad_bob"
	bl_label = "BombSquad Mesh"
	bl_import_operator = "import_mesh.bombsquad_bob"
	bl_export_operator = "export_mesh.bombsquad_bob"
	bl_file_extensions = ".bob"

	@classmethod
	def poll_drop(cls, context):
		# drop sohuld only be allowed in 3d view and outliner
		return bpy_extras.io_utils.poll_file_object_drop(context)


def menu_func_import_bob(self, context):
	self.layout.operator(IMPORT_MESH_OT_bombsquad_bob.bl_idname, text="Bombsquad Mesh (.bob)")


def menu_func_export_bob(self, context):
	self.layout.operator(EXPORT_MESH_OT_bombsquad_bob.bl_idname, text="Bombsquad Mesh (.bob)")


class SCENE_OT_bombsquad_arrange_character(bpy.types.Operator):
	"""Arrange selected character parts"""
	bl_idname = "scene.bombsquad_arrange_character"
	bl_label = "Arrange Bombsquad Character"
	bl_options = {'REGISTER', 'UNDO'}

	style: bpy.props.EnumProperty(
		items=(
			('NONE', 'None', "Clear all transformations."),
			('DEFAULT', 'Default', "Arrange the character parts to resemble `neoSpaz` style"),
		),
		default='DEFAULT',
		name="Style",
	)

	@classmethod
	def poll(cls, context):
		return len(context.selected_objects) > 0

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		selected_objects = context.selected_objects

		for obj in selected_objects:
			character_part = _get_character_part_name(obj.name.split('.')[0])
			if character_part is None:
				continue
			part_metadata = character_part_metadata[character_part]
			if self.style == 'NONE':
				obj.location = (0, 0, 0)
				obj.rotation_euler = (0, 0, 0)
			elif self.style == 'DEFAULT':
				obj.location = part_metadata['location']
				obj.rotation_euler = part_metadata['rotation']

		return {'FINISHED'}


class COLLECTION_OT_bombsquad_create_character_exporter(bpy.types.Operator):
	"""Create a collection exporter for the active collection"""
	bl_idname = "collection.bombsquad_create_character_exporter"
	bl_label = "Create Character Exporter"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	@classmethod
	def poll(cls, context):
		return context.view_layer.active_layer_collection.collection != context.scene.collection

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		collection = context.view_layer.active_layer_collection.collection
		
		bpy.ops.collection.exporter_add(name='IO_FH_bombsquad_bob')
		exporter = collection.exporters[-1]

		exporter.export_properties.apply_object_transformations = False
		exporter.export_properties.apply_modifiers = True

		print(f"{self.__class__.__name__}: [INFO] Created collection exporter for collection `{collection.name}`.")

		return {'FINISHED'}


class VIEW3D_PT_bombsquad_character(bpy.types.Panel):
	bl_idname = "VIEW3D_PT_bombsquad_character"
	bl_label = "BombSquad Character"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "BombSquad"
	bl_context = "objectmode"

	def draw(self, context):
		layout = self.layout
		scene = context.scene
		
		col = layout.column(align=True)
		col.label(text="Arrange selected character parts")
		col.operator_enum('SCENE_OT_bombsquad_arrange_character', "style")

		col = layout.column(align=True)
		col.label(text="Create character exporter")
		col.operator('COLLECTION_OT_bombsquad_create_character_exporter')


classes = (
	IMPORT_MESH_OT_bombsquad_bob,
	EXPORT_MESH_OT_bombsquad_bob,
	IO_FH_bombsquad_bob,
	SCENE_OT_bombsquad_arrange_character,
	COLLECTION_OT_bombsquad_create_character_exporter,
	VIEW3D_PT_bombsquad_character,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import_bob)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export_bob)


def unregister():
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_bob)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_bob)
	_unregister()


if __name__ == "__main__":
	register()
