import struct
import bmesh
import bpy_extras

# import to mesh.py
# export to bob

BOB_FILE_ID = 45623

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
"""


"""

    Blender 3D Coordinates

            +Z
            ^
            | ^ +Y
            |/
            +-----> +X


    BombSquad 3D Coordinates

            +Y
            ^
            |
            |
            +-----> +X
           /
          v +Z



    Blender UV Coordinates

            +Y [0,1]
            ^
            |
            |
            +-----> +X [0,1]


    BombSquad UV Coordinates

            +-----> +X Int[0,65535]
            |
            |
            v
            +Y Int[0,65535]

"""

def to_mesh(mesh, bob_data):
	verts = [vert["pos"] for vert in bob_data["vertices"]]
	faces = [face["indices"] for face in bob_data["faces"]]
	mesh.from_pydata(verts, [], faces)

	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.faces.ensure_lookup_table()
	
	for i, face in enumerate(bm.faces):
		for vi, vert in enumerate(face.verts):
			normal = bob_data["vertices"][faces[i][vi]]["norm"]
			vert.normal = (
				normal[0] / 32767,
				normal[1] / 32767,
				normal[2] / 32767,
			)

	uv_layer = bm.loops.layers.uv.verify()
	for i, face in enumerate(bm.faces):
		for vi, vert in enumerate(face.verts):
			uv = bob_data["vertices"][faces[i][vi]]["uv"]
			uv = (uv[0] / 65535, 1 - uv[1] / 65535)
			face.loops[vi][uv_layer].uv = uv

	matrix = bpy_extras.io_utils.axis_conversion(from_forward='-Z', from_up='Y').to_4x4()
	bm.transform(matrix)

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
	This is also call "Rip Vertex" in blender,
	but here we implement it manually.
	"""

	vertices = []
	faces = []

	bm = bmesh.new()
	bm.from_mesh(mesh)
	bm.faces.ensure_lookup_table()

	matrix = bpy_extras.io_utils.axis_conversion(to_forward='-Z', to_up='Y').to_4x4()
	bm.transform(matrix)

	bmesh.ops.triangulate(bm, faces=bm.faces)

	uv_layer = None
	if len(bm.loops.layers.uv) > 0:
		uv_layer = bm.loops.layers.uv[0]
	for i, face in enumerate(bm.faces):
		faceverts = []
		for vi, vert in enumerate(face.verts):
			uv = face.loops[vi][uv_layer].uv if uv_layer else (0, 0)
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
			"uv": (int(vertex["uv"][0] * 65535), int((1 - vertex["uv"][1]) * 65535)),
			"norm": tuple(map(lambda n: int(n * 32767), vertex["norm"])),
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
