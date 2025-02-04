import os
import struct
import bpy
import bmesh
import bpy_extras

from . import utils


"""
.COB File Structure:

MAGIC 13466 (I)
vertexCount (I)
faceCount   (I)
vertexPos x vertexCount (fff)
index x faceCount*3 (I)
normal x faceCount (fff)
"""


COB_FILE_ID = 13466

bs_to_bl_matrix = bpy_extras.io_utils.axis_conversion(from_forward='-Z', from_up='Y').to_4x4()
bl_to_bs_matrix = bpy_extras.io_utils.axis_conversion(to_forward='-Z', to_up='Y').to_4x4()


def to_mesh(mesh, cob_data):
	verts = [vert["pos"] for vert in cob_data["vertices"]]
	faces = [face["indices"] for face in cob_data["faces"]]
	mesh.from_pydata(verts, [], faces)

	bm = bmesh.new()
	bm.from_mesh(mesh)

	bm.transform(bs_to_bl_matrix)

	bm.to_mesh(mesh)
	bm.free()

	mesh.validate()
	mesh.update()

	return mesh


def from_mesh(mesh):
	vertices = []
	faces = []
	normals = []

	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.faces.ensure_lookup_table()

	bm.transform(bl_to_bs_matrix)

	bmesh.ops.triangulate(bm, faces=bm.faces)

	for i, face in enumerate(bm.faces):
		faceverts = []
		for vi, vert in enumerate(face.verts):
			faceverts.append(vert.index)
		faces.append({
			"indices": faceverts
		})
		normals.append({
			"dir": face.normal
		})

	bm.free()

	return {
		"vertices": vertices,
		"faces": faces,
		"normals": normals,
	}


def serialize(data, file):
	def writestruct(s, *args):
		file.write(struct.pack(s, *args))

	vertexCount = len(data["vertices"])
	faceCount = len(data["faces"])

	writestruct('<I', COB_FILE_ID)
	writestruct('<I', vertexCount)
	writestruct('<I', faceCount)

	for vert in data["vertices"]:
		writestruct('<fff', vert["pos"][0], vert["pos"][1], vert["pos"][2])

	for face in data["faces"]:
		writestruct('<III', face["indices"][0], face["indices"][1], face["indices"][2])

	for normal in data["normals"]:
		writestruct('<fff', normal["dir"][0], normal["dir"][1], normal["dir"][2])

	return


def deserialize(file):
	def readstruct(s):
		tup = struct.unpack(s, file.read(struct.calcsize(s)))
		return tup[0] if len(tup) == 1 else tup

	assert readstruct("<I") == COB_FILE_ID

	vertexCount = readstruct("<I")
	faceCount = readstruct("<I")

	vertices = []
	faces = []
	normals = []

	for i in range(vertexCount):
		pos = readstruct("<fff")
		vertices.append({
			"pos": pos,
		})

	for i in range(faceCount):
		indices = readstruct("<III")
		faces.append({
			"indices": indices
		})

	for i in range(faceCount):
		indices = readstruct("<fff")
		normals.append({
			"dir": indices
		})

	return {
		"vertices": vertices,
		"faces": faces,
		"normals": normals,
	}


class IMPORT_MESH_OT_bombsquad_cob(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
	"""Load a Bombsquad Collision Mesh"""
	bl_idname = "import_mesh.bombsquad_cob"
	bl_label = "Import Bombsquad Collision Mesh"
	bl_options = {'REGISTER', 'UNDO', 'PRESET'}

	filename_ext = ".cob"
	filter_glob: bpy.props.StringProperty(
		default="*.cob",
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

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		keywords = self.as_keywords(ignore=(
			'filter_glob',
			'files',
			'filepath',
		))

		should_create_collection = self.files and self.group_into_collection

		collection = None
		if should_create_collection:
			filename = bpy.path.display_name_from_filepath(self.files[0].name)
			collection = bpy.data.collections.new(filename)
			
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
				if self.import_cob(context, path, collection=collection, **keywords) == {'FINISHED'}:
					ret = {'FINISHED'}
				else:
					self.report({'WARNING'}, f"The file `{path}` was not imported.")
		else:
			# Single file import
			ret = self.import_cob(context, self.filepath, collection=collection, **keywords)

		if ret != {'FINISHED'}:
			return {'CANCELLED'}

		if should_create_collection and collection is not None and self.setup_collection_exporter:
			utils.set_active_collection(collection)
			bpy.ops.collection.exporter_add(name='IO_FH_bombsquad_cob')
			exporter = collection.exporters[-1]
			exporter.export_properties.filepath = self.filepath
			print(f"{self.__class__.__name__}: [INFO] Created collection exporter for collection `{collection.name}`.")

		return {'FINISHED'}

	def import_cob(self, context, filepath, collection=None):
		print(f"{self.__class__.__name__}: [INFO] Importing `{filepath}`")
		filepath = os.fsencode(filepath)

		cob_data = None
		with open(filepath, 'rb') as file:
			cob_data = deserialize(file)

		cob_name = bpy.path.display_name_from_filepath(filepath)
		mesh = bpy.data.meshes.new(name=cob_name)
		mesh = to_mesh(mesh=mesh, cob_data=cob_data)

		if not mesh:
			return {'CANCELLED'}

		obj = bpy.data.objects.new(mesh.name, mesh)
		if collection:
			collection.objects.link(obj)
		else:
			context.scene.collection.objects.link(obj)
		
		bpy.ops.object.select_all(action='DESELECT')
		obj.select_set(True)
		
		context.view_layer.objects.active = obj
		context.view_layer.update()
		
		return {'FINISHED'}


class EXPORT_MESH_OT_bombsquad_cob(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
	"""Save a Bombsquad Collision Mesh file"""
	bl_idname = "export_mesh.bombsquad_cob"
	bl_label = "Export Bombsquad Collision Mesh"
	bl_options = {'REGISTER', 'PRESET'}

	filter_glob: bpy.props.StringProperty(
		default="*.cob",
		options={'HIDDEN'},
	)
	check_extension = True
	filename_ext = ".cob"

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
				dirname = os.path.dirname(self.filepath)
				filename = bpy.path.display_name_to_filepath(obj.name) + '.bob'
				filepath = os.path.join(dirname, filename)
				if self.export_cob(context, obj, filepath, **keywords) == {'FINISHED'}:
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

			return self.export_cob(context, obj, self.filepath, **keywords)

	def export_cob(self, context, obj, filepath, **options):
		print(f"{self.__class__.__name__}: [INFO] Exporting object `{obj.name}` to `{filepath}`")

		mesh = None
		if options['apply_modifiers']:
			depsgraph = context.evaluated_depsgraph_get()
			modified_obj = obj.evaluated_get(depsgraph)
			mesh = bpy.data.meshes.new_from_object(modified_obj, preserve_all_data_layers=True, depsgraph=depsgraph)
		else:
			mesh = obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

		if options['apply_object_transformations']:
			mesh.transform(obj.matrix_world)

		filepath = os.fsencode(filepath)
		with open(filepath, 'wb') as file:
			cob_data = from_mesh(mesh)
			serialize(cob_data, file)

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
class IO_FH_bombsquad_cob(bpy.types.FileHandler):
	bl_idname = "IO_FH_bombsquad_cob"
	bl_label = "BombSquad Collision Mesh"
	bl_import_operator = "import_mesh.bombsquad_cob"
	bl_export_operator = "export_mesh.bombsquad_cob"
	bl_file_extensions = ".cob"

	@classmethod
	def poll_drop(cls, context):
		# drop sohuld only be allowed in 3d view and outliner
		return bpy_extras.io_utils.poll_file_object_drop(context)


def menu_func_import_cob(self, context):
	self.layout.operator(IMPORT_MESH_OT_bombsquad_cob.bl_idname, text="Bombsquad Collision Mesh (.cob)")


def menu_func_export_cob(self, context):
	self.layout.operator(EXPORT_MESH_OT_bombsquad_cob.bl_idname, text="Bombsquad Collision Mesh (.cob)")


classes = (
	IMPORT_MESH_OT_bombsquad_cob,
	EXPORT_MESH_OT_bombsquad_cob,
	IO_FH_bombsquad_cob,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import_cob)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export_cob)


def unregister():
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_cob)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_cob)
	_unregister()


if __name__ == "__main__":
	register()
