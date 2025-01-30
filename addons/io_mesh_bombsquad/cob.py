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

	def execute(self, context):
		keywords = self.as_keywords(ignore=('filter_glob',))
		mesh = self.import_cob(context, **keywords)
		if not mesh:
			return {'CANCELLED'}

		scene = bpy.context.scene
		obj = bpy.data.objects.new(mesh.name, mesh)
		scene.collection.objects.link(obj)
		bpy.ops.object.select_all(action='DESELECT')
		obj.select_set(True)
		bpy.context.view_layer.objects.active = obj
		bpy.context.view_layer.update()
		return {'FINISHED'}

	def import_cob(self, context, filepath):
		filepath = os.fsencode(filepath)
		with open(filepath, 'rb') as file:
			cob_data = deserialize(file)
			print(cob_data)
			cob_name = bpy.path.display_name_from_filepath(filepath)
			mesh = bpy.data.meshes.new(name=cob_name)
			return to_mesh(mesh=mesh, cob_data=cob_data)


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

	apply_object_transformations: bpy.props.BoolProperty(
		name="Apply Object Transformations",
		description="",
		default=False,
	)

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def execute(self, context):
		keywords = self.as_keywords(ignore=(
			'check_existing',
			'filter_glob',
		))
		return self.export_cob(context, **keywords)

	def export_cob(self, context, filepath,
			apply_object_transformations):
		scene = context.scene
		obj = bpy.context.active_object
		mesh = obj.to_mesh()

		if apply_object_transformations:
			mesh.transform(obj.matrix_world)

		filepath = os.fsencode(filepath)

		with open(filepath, 'wb') as file:
			cob_data = from_mesh(mesh)
			serialize(cob_data, file)

		return {'FINISHED'}


# Enables importing files by draggin and dropping into the blender UI
# Enables export via collection exporter
class IO_FH_bombsquad_cob(bpy.types.FileHandler):
	bl_idname = "IO_FH_bombsquad_cob"
	bl_label = "BombSquad Collision Mesh"
	bl_import_operator = "import_mesh.bombsquad_cob"
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
