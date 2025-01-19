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
index x faceCount*3 (b / H)

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

def bob_to_mesh():

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

	pass

def mesh_to_bob():
	pass
