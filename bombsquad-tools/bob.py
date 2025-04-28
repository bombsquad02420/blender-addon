import os
import struct
import bpy
import bmesh
import bpy_extras
# FIXME: IDK why bpy_extras.image_utils does not work
from bpy_extras import image_utils

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
	bs_sint16 normal[3]; // normalized to 16 bit signed ints -32768 - 32767
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


def bob_to_mesh(bob_data, bob_name):
	verts = [vert["pos"] for vert in bob_data["vertices"]]
	faces = [face["indices"] for face in bob_data["faces"]]

	mesh = bpy.data.meshes.new(name=bob_name)
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


def mesh_to_bob(mesh):
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

	import_matching_textures: bpy.props.BoolProperty(
		name="Import Matching Textures",
		description="",
		default=False,
	)

	setup_materials: bpy.props.BoolProperty(
		name="Setup Materials",
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

		dirname = os.path.dirname(self.filepath)
		selected_files = [os.path.join(dirname, file.name) for file in self.files]
		ba_data_dir = utils.get_ba_data_path_from_filepath(self.filepath)

		print(f"{self.__class__.__name__}: [INFO] Files selected for import: {selected_files}")
		
		is_character = False
 
		collection = None
		if self.group_into_collection:
			display_name = bpy.path.display_name_from_filepath(selected_files[0])
			character_part = utils.get_character_part_name(display_name)

			if character_part is not None:
				is_character = True
				collection_name = display_name.rstrip(character_part)
				collection = bpy.data.collections.new(collection_name)
				print(f"{self.__class__.__name__}: [INFO] Created collection `{collection_name}` because you are importing a character.")
			
			else:
				collection = bpy.data.collections.new(display_name)
				print(f"{self.__class__.__name__}: [INFO] Created collection `{collection.name}`.")

			context.scene.collection.children.link(collection)
			context.view_layer.update()

		execution_context = {
			'dirname': dirname,
			'ba_data_dir': ba_data_dir,
		}

		ret = {'CANCELLED'}
		for file_path in selected_files:
			if self.import_bob(context, file_path, collection=collection, execution_context=execution_context, **keywords) == {'FINISHED'}:
				ret = {'FINISHED'}
			else:
				self.report({'WARNING'}, f"The file `{file_path}` was not imported.")
	
		if ret != {'FINISHED'}:
			return {'CANCELLED'}

		if self.group_into_collection and self.setup_collection_exporter:
			utils.set_active_collection(collection)
			if is_character:
				bpy.ops.collection.bombsquad_create_character_exporter()
			else:
				bpy.ops.collection.bombsquad_create_bob_exporter()

		return {'FINISHED'}

	def import_bob(self, context, filepath, collection=None, execution_context=None, **options):
		print(f"{self.__class__.__name__}: [INFO] Importing `{filepath}` with options {options} and execution context {execution_context}")
		filepath = os.fsencode(filepath)
		
		bob_data = None
		with open(filepath, 'rb') as file:
			bob_data = deserialize(file)

		bob_name = bpy.path.display_name_from_filepath(filepath)
		mesh = bob_to_mesh(bob_data=bob_data, bob_name=bob_name)

		if not mesh:
			return {'CANCELLED'}

		obj = bpy.data.objects.new(bob_name, mesh)
		if collection:
			collection.objects.link(obj)
		else:
			context.scene.collection.objects.link(obj)

		bpy.ops.object.select_all(action='DESELECT')
		obj.select_set(True)
		context.view_layer.objects.active = obj
		context.view_layer.update()

		character_name = utils.get_character_name(bob_name)

		if options['arrange_character_meshes']:
			bpy.ops.scene.bombsquad_arrange_character()

		imported_texture_image = None
		imported_mask_image = None
		if options['import_matching_textures']:
			assert execution_context is not None
			assert 'dirname' in execution_context
			assert 'ba_data_dir' in execution_context

			dirname = execution_context['dirname']
			ba_data_dir = execution_context['ba_data_dir']

			texture_dir = dirname
			if ba_data_dir is not None:
				texture_dir = os.path.join(ba_data_dir, 'textures')

			if character_name is not None:
				texture_name = character_name + 'Color.dds'
				mask_name = character_name + 'ColorMask.dds'
				texture_path = os.path.join(texture_dir, texture_name)
				mask_path = os.path.join(texture_dir, mask_name)

				if texture_name in bpy.data.images:
					print(f"{self.__class__.__name__}: [INFO] Reusing previously imported image `{texture_name}`")
					imported_texture_image = bpy.data.images[texture_name]
				else:
					print(f"{self.__class__.__name__}: [INFO] Importing image `{texture_path}`")
					imported_texture_image = image_utils.load_image(texture_path)
					if imported_texture_image is None:
						self.report({'WARNING'}, f"The image `{texture_path}` could not be imported.")
						print(f"{self.__class__.__name__}: [WARN] The image `{texture_path}` could not be imported.")

				if mask_name in bpy.data.images:
					print(f"{self.__class__.__name__}: [INFO] Reusing previously imported image `{mask_name}`")
					imported_mask_image = bpy.data.images[mask_name]
				else:
					print(f"{self.__class__.__name__}: [INFO] Importing image `{mask_path}`")
					imported_mask_image = image_utils.load_image(mask_path)
					if imported_mask_image is None:
						self.report({'WARNING'}, f"The image `{mask_path}` could not be imported.")
						print(f"{self.__class__.__name__}: [WARN] The image `{mask_path}` could not be imported.")

			else:
				possible_texture_names = utils.get_possible_texture_file_names(bob_name)

				valid_texture_name = None
				valid_texture_path = None
				for texture_name in possible_texture_names:
					texture_path = os.path.join(texture_dir, texture_name)
					if os.path.isfile(texture_path):
						valid_texture_path = texture_path
						valid_texture_name = texture_name
						print(f"{self.__class__.__name__}: [INFO] Found texture `{texture_path}` for `{bob_name}`")
						break

				if valid_texture_name is None:
					print(f"{self.__class__.__name__}: [INFO] No texture found for `{bob_name}`")
				elif valid_texture_name in bpy.data.images:
					print(f"{self.__class__.__name__}: [INFO] Reusing previously imported image `{valid_texture_name}`")
					imported_texture_image = bpy.data.images[valid_texture_name]
				else:
					print(f"{self.__class__.__name__}: [INFO] Importing image `{valid_texture_path}`")
					imported_texture_image = image_utils.load_image(valid_texture_path)

		if options['setup_materials']:
			if character_name is not None:
				material_name = character_name + ' Material'
				if material_name in bpy.data.materials:
					obj.data.materials.append(bpy.data.materials[material_name])
				else:
					bpy.ops.material.add_bombsquad_colorize_shader(
						material_name=material_name,
						image=imported_texture_image.name if imported_texture_image is not None else "",
						color_mask=imported_mask_image.name if imported_mask_image is not None else "",
					)
			else:
				if imported_texture_image is not None:
					bpy.ops.material.add_bombsquad_shader(
						material_name=bpy.path.display_name(imported_texture_image.name) + ' Material',
						image=imported_texture_image.name,
					)
				else:
					bpy.ops.material.add_bombsquad_shader(
						material_name=bob_name + ' Material',
					)

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
		description="Export mesh geometry with modifiers applied, as visible in viewport",
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
			# we are manually exporting a single object from the menu
			obj = context.active_object
			selected_objects = context.selected_objects
			
			if len(selected_objects) > 1:
				print(f"{self.__class__.__name__}: [WARN] Multiple objects selected. Only the active object will be exported.")
				self.report({'WARNING'}, f"Multiple objects selected. Only the active object will be exported.")

			print(f"{self.__class__.__name__}: [INFO] Exporting active object `{obj.name}`.")

			return self.export_bob(context, obj, self.filepath, **keywords)

	def export_bob(self, context, obj, filepath, **options):
		print(f"{self.__class__.__name__}: [INFO] Exporting object `{obj.name}` to `{filepath}`")

		mesh = utils.obj_to_mesh(
			obj,
			context,
			apply_modifiers=options['apply_modifiers'],
			apply_object_transformations=options['apply_object_transformations'],
		)
		bob_data = mesh_to_bob(mesh)

		filepath = os.fsencode(filepath)
		with open(filepath, 'wb') as file:
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


class MESH_OT_CONVERT_TO_BOB(bpy.types.Operator):
	"""Prepare a mesh for .bob export, but import it back instead of writing to a file"""
	bl_idname = "mesh.bombsquad_convert_to_bob"
	bl_label = "Convert to Bombsquad Mesh"
	bl_options = {'REGISTER', 'PRESET', 'UNDO'}

	apply_object_transformations: bpy.props.BoolProperty(
		name="Apply Object Transformations",
		description="Export mesh geometry with translation, rotation and scaling applied",
		default=True,
	)

	apply_modifiers: bpy.props.BoolProperty(
		name="Apply Modifiers",
		description="Export mesh geometry with modifiers applied, as visible in viewport",
		default=True,
	)

	@classmethod
	def poll(cls, context):
			return context.active_object is not None

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		keywords = self.as_keywords(ignore=())

		original_obj = context.active_object
		export_mesh = utils.obj_to_mesh(
			original_obj,
			context,
			apply_modifiers=keywords['apply_modifiers'],
			apply_object_transformations=keywords['apply_object_transformations'],
		)
		bob_data = mesh_to_bob(export_mesh)
		import_mesh = bob_to_mesh(bob_data=bob_data, bob_name=original_obj.name)

		if not import_mesh:
			return {'CANCELLED'}

		new_obj = bpy.data.objects.new(original_obj.name, import_mesh)
		context.scene.collection.objects.link(new_obj)

		bpy.ops.object.select_all(action='DESELECT')
		new_obj.select_set(True)
		context.view_layer.objects.active = new_obj
		context.view_layer.update()

		print(f"{self.__class__.__name__}: [INFO] Done!")

		return {'FINISHED'}


classes = (
	IMPORT_MESH_OT_bombsquad_bob,
	EXPORT_MESH_OT_bombsquad_bob,
	IO_FH_bombsquad_bob,
	MESH_OT_CONVERT_TO_BOB,
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
