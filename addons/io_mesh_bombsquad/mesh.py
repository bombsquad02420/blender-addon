# intermediary mesh format
# bob/cob <---mesh.py---> blender mesh

# INTERMEDIATE FORMAT
# vertices: (float, float, float)[] -> position of the vertices
# vertex_normals: (float, float, float)[] -> normal of the vertices
# uvs: (float, float)[] -> uv coordinates of the vertices
# faces: (int, int, int)[] -> indices of the vertices that make up the faces
# face_normals: (float, float, float)[] -> normal of the face
# material: str[] -> material name of the face

class Verts:
    def __init__(self):
        self._verts = []
        self._by_blender_index = defaultdict(list)

    def get(self, coords, normal, blender_index, uv=None):
        instance = Vert(coords=coords, normal=normal, uv=uv)
        for other in self._by_blender_index[blender_index]:
            if instance.similar(other):
                return other
        self._by_blender_index[blender_index].append(instance)
        instance.index = len(self._verts)
        self._verts.append(instance)
        return instance

    def __len__(self):
        return len(self._verts)

    def __iter__(self):
        return iter(self._verts)


def vec_similar(v1, v2):
    return (v1 - v2).length < 0.01


class Vert:
    def __init__(self, coords, normal, uv):
        self.coords = coords
        self.normal = normal
        self.uv = uv

    def similar(self, other):
        is_similar = vec_similar(self.coords, other.coords)
        is_similar = is_similar and vec_similar(self.normal, other.normal)
        if self.uv and other.uv:
            is_similar = is_similar and vec_similar(self.uv, other.uv)
        return is_similar

def mesh_to_bmesh():
	pass

# can we triangulate here? or in mesh_to_bob and mesh_to_cob?
def bmesh_to_mesh():
	pass

