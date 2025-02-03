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


def _get_character_part_name(filename):
	for part in character_part_metadata:
		if filename.endswith(part):
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

		if self.files:
			# Multiple file import
			ret = {'CANCELLED'}
			dirname = os.path.dirname(self.filepath)
			for file in self.files:
				path = os.path.join(dirname, file.name)
				if self.import_bob(context, path, **keywords) == {'FINISHED'}:
					ret = {'FINISHED'}
				else:
					self.report({'WARNING'}, f"The file `{path}` was not imported.")
			return ret
		else:
			# Single file import
			return self.import_bob(context, self.filepath, **keywords)

		self.import_bob(context, **keywords)


	def import_bob(self, context, filepath, **options):
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

	apply_object_transformations: bpy.props.BoolProperty(
		name="Apply Object Transformations",
		description="",
		default=True,
	)

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def execute(self, context):
		keywords = self.as_keywords(ignore=(
			'check_existing',
			'filter_glob',
		))
		return self.export_bob(context, **keywords)

	def export_bob(self, context, filepath,
			apply_object_transformations):
		scene = context.scene
		obj = bpy.context.active_object
		mesh = obj.to_mesh()
		
		if apply_object_transformations:
			mesh.transform(obj.matrix_world)

		filepath = os.fsencode(filepath)

		with open(filepath, 'wb') as file:
			bob_data = from_mesh(mesh)
			serialize(bob_data, file)

		return {'FINISHED'}


# Enables importing files by draggin and dropping into the blender UI
# Enables export via collection exporter
class IO_FH_bombsquad_bob(bpy.types.FileHandler):
	bl_idname = "IO_FH_bombsquad_bob"
	bl_label = "BombSquad Mesh"
	bl_import_operator = "import_mesh.bombsquad_bob"
	bl_file_extensions = ".bob"

	@classmethod
	def poll_drop(cls, context):
		# drop sohuld only be allowed in 3d view and outliner
		return bpy_extras.io_utils.poll_file_object_drop(context)


def menu_func_import_bob(self, context):
	self.layout.operator(IMPORT_MESH_OT_bombsquad_bob.bl_idname, text="Bombsquad Mesh (.bob)")


def menu_func_export_bob(self, context):
	self.layout.operator(EXPORT_MESH_OT_bombsquad_bob.bl_idname, text="Bombsquad Mesh (.bob)")


classes = (
	IMPORT_MESH_OT_bombsquad_bob,
	EXPORT_MESH_OT_bombsquad_bob,
	IO_FH_bombsquad_bob,
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
