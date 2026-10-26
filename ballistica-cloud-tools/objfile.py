"""Minimal Wavefront OBJ for workspace meshes.

Workspace meshes are one object each: positions, UVs and normals, with
triangles that index all three (`f v/vt/vn`). No objects, groups or
materials. Coordinates are game space (Y up, Z forward).
"""


class ObjMesh:
	def __init__(self, positions=None, uvs=None, normals=None, faces=None):
		self.positions = positions or []  # [(x, y, z)]
		self.uvs = uvs or []  # [(u, v)]
		self.normals = normals or []  # [(x, y, z)]
		# Each face: ((v, vt, vn), ...) zero-based; vt/vn may be None.
		self.faces = faces or []


def read(path):
	mesh = ObjMesh()
	with open(path, encoding='utf-8') as infile:
		for line in infile:
			parts = line.split()
			if not parts or parts[0].startswith('#'):
				continue
			tag = parts[0]
			if tag == 'v':
				mesh.positions.append(tuple(float(x) for x in parts[1:4]))
			elif tag == 'vt':
				mesh.uvs.append(tuple(float(x) for x in parts[1:3]))
			elif tag == 'vn':
				mesh.normals.append(tuple(float(x) for x in parts[1:4]))
			elif tag == 'f':
				corners = [_corner(p, mesh) for p in parts[1:]]
				# Fan-triangulate anything bigger than a triangle.
				for i in range(1, len(corners) - 1):
					mesh.faces.append((corners[0], corners[i], corners[i + 1]))
	return mesh


def _corner(token, mesh):
	fields = token.split('/')
	sizes = (len(mesh.positions), len(mesh.uvs), len(mesh.normals))
	out = []
	for i in range(3):
		if i < len(fields) and fields[i]:
			index = int(fields[i])
			out.append(index - 1 if index > 0 else sizes[i] + index)
		else:
			out.append(None)
	return tuple(out)


def write(path, mesh):
	"""Write triangles with positions, UVs and normals, deduplicated."""
	positions, uvs, normals = {}, {}, {}
	lines_v, lines_vt, lines_vn, lines_f = [], [], [], []

	def index(table, lines, prefix, value):
		key = tuple(round(c, 6) for c in value)
		if key not in table:
			table[key] = len(table) + 1
			lines.append(prefix + ' ' + ' '.join(_num(c) for c in key))
		return table[key]

	for face in mesh.faces:
		tokens = []
		for vi, ti, ni in face:
			v = index(positions, lines_v, 'v', mesh.positions[vi])
			t = index(uvs, lines_vt, 'vt', mesh.uvs[ti]) if ti is not None else ''
			n = index(normals, lines_vn, 'vn', mesh.normals[ni]) if ni is not None else ''
			tokens.append(f'{v}/{t}/{n}')
		lines_f.append('f ' + ' '.join(tokens))
	with open(path, 'w', encoding='utf-8', newline='\n') as outfile:
		outfile.write('# Exported by Ballistica Cloud Tools for Blender\n')
		for block in (lines_v, lines_vt, lines_vn, lines_f):
			if block:
				outfile.write('\n'.join(block) + '\n')


def _num(value):
	text = f'{value:.6f}'
	return '0.000000' if text == '-0.000000' else text


# The mesh compiler (ballistica tools/bacommontools/meshcompile.py) stores
# UVs as u16 over [0, 1]: anything further outside than this is an error
# (no tiling or wrapping UVs); within it, it's clamped as authoring noise.
UV_TOLERANCE = 0.05


def uv_range_problem(uvs):
	"""(lowest, highest) UV component if any falls outside what the cloud
	build accepts, else None. `uvs` is a flat sequence u0, v0, u1, v1, ..."""
	if not uvs:
		return None
	lo, hi = min(uvs), max(uvs)
	if lo < -UV_TOLERANCE or hi > 1.0 + UV_TOLERANCE:
		return lo, hi
	return None
