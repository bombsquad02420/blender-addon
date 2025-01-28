import struct
import bmesh
import bpy_extras

from . import utils


COB_FILE_ID = 13466

"""
.COB File Structure:

MAGIC 13466 (I)
vertexCount (I)
faceCount   (I)
vertexPos x vertexCount (fff)
index x faceCount*3 (I)
normal x faceCount (fff)
"""


def to_mesh(mesh, cob_data):
	verts = [vert["pos"] for vert in cob_data["vertices"]]
	faces = [face["indices"] for face in cob_data["faces"]]
	mesh.from_pydata(verts, [], faces)

	bm = bmesh.new()
	bm.from_mesh(mesh)

	matrix = bpy_extras.io_utils.axis_conversion(from_forward='-Z', from_up='Y').to_4x4()
	bm.transform(matrix)

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

	matrix = bpy_extras.io_utils.axis_conversion(to_forward='-Z', to_up='Y').to_4x4()
	bm.transform(matrix)

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
