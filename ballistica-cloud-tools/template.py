"""A from-scratch character: one cuboid per body part, Minecraft style.

Boxes sit where the game draws each part. Each limb box runs along its
body's +z (the bone) as far as the default Spaz's mesh for that limb does
(the `neo_spaz_*` meshes in ClassicCharacterAssets), so limbs have the
game's lengths and overlap at the joints the way the real meshes do; its
thickness is about the game's collision capsule, not Spaz's armour. The
torso and pelvis follow the rig's torso radius and pelvis box; the head is
a cube just inside the head ball with its front face where the eyes sit.
Sizes are in each part's own space (game axes); arm and leg parts are
right-side.

The cuboids share one texture atlas: each part gets a cell, and each face
of its box a patch inside that cell, so faces can be painted separately.
The color mask tints the body with the player color (red) and the lower
limbs with the highlight (green); head, hands and feet stay untinted.
Pure Python, testable without Blender.
"""

from . import objfile, rig

# Half-size of the head cube: inside the head ball (radius 0.23), with the
# front face at the eyes' depth (eye_offset z = 0.205).
HEAD = 0.21



def _limb(z_extent, half_width, forward=0.0):
	"""A box along the bone (+z) over `z_extent`, `half_width` thick.

	`forward` shifts it along +y (a shin's front, toward the ankle).
	"""
	return ((-half_width, forward - half_width, z_extent[0]), (half_width, forward + half_width, z_extent[1]))


# Part -> how much its far end (+z, away from the parent joint) narrows,
# so limbs taper like muscle instead of reading as planks. The box's x/y
# extents are its widest (near) end.
TAPER = {
	'upper_arm': 0.72, 'forearm': 0.75,
	'upper_leg': 0.7, 'lower_leg': 0.72,
	'pelvis': 0.85,
}


_TORSO_R = rig.DEFAULTS['torso_radius']
_PELVIS_W, _PELVIS_H, _PELVIS_D = rig.PELVIS_SIZE

# Part -> (min corner, max corner), game axes, in the part's own space.
CUBOIDS = {
	'head': ((-HEAD, -HEAD, -HEAD), (HEAD, HEAD, HEAD)),
	# Shoulders on top (shoulder joints sit 0.14 up), the spine joint below.
	'torso': ((-_TORSO_R * 1.05, -0.12, -0.12), (_TORSO_R * 1.05, rig.SHOULDER_ON_TORSO[1] + 0.06, 0.13)),
	'pelvis': ((-_PELVIS_W * 0.46, -_PELVIS_H * 0.5, -0.09), (_PELVIS_W * 0.46, _PELVIS_H * 0.6, 0.09)),
	# Lengths along the bone from the neo_spaz meshes; widths a bit over
	# the capsule radii at the near end, tapering (TAPER) toward the far one.
	'upper_arm': _limb((-0.2, 0.075), 0.072),  # capsule radius 0.06
	'forearm': _limb((-0.13, 0.07), 0.055),  # capsule radius 0.06
	# A fist, from the wrist forward along the hand.
	'hand': ((-0.055, -0.05, -0.02), (0.055, 0.06, 0.1)),
	'upper_leg': _limb((-0.12, 0.1), 0.075),  # thigh radius 0.04
	'lower_leg': _limb((-0.12, 0.1), 0.06, forward=0.01),  # ankle radius 0.07
	# A shoe, long along the foot's forward (+y), sole at the bottom.
	'toes': ((-0.055, -0.04, -0.02), (0.055, 0.12, 0.065)),
}

# Atlas cell (column, row) per part on a 3x3 grid; row 0 is the bottom.
CELLS = {
	'head': (0, 2), 'torso': (1, 2), 'pelvis': (2, 2),
	'upper_arm': (0, 1), 'forearm': (1, 1), 'hand': (2, 1),
	'upper_leg': (0, 0), 'lower_leg': (1, 0), 'toes': (2, 0),
}
GRID = 3

# Mask channel per part: which tint it takes in the game.
TINT = {
	'torso': 'color', 'pelvis': 'color', 'upper_arm': 'color', 'upper_leg': 'color',
	'forearm': 'highlight', 'lower_leg': 'highlight',
}
MASK_RGB = {'color': (1.0, 0.0, 0.0), 'highlight': (0.0, 1.0, 0.0), None: (0.0, 0.0, 0.0)}

SKIN = (1.0, 1.0, 1.0)
TINTED = (0.85, 0.85, 0.85)  # light, so the tint shows
SHOE = (0.18, 0.16, 0.15)
BASE_COLORS = {'head': SKIN, 'hand': SKIN, 'toes': SHOE}

# Box faces: (outward normal axis, sign) and the two axes spanning it,
# laid out in the cell as a 3x2 grid of patches.
FACES = (
	((2, 1), (0, 1)),   # +Z front
	((2, -1), (0, 1)),  # -Z back
	((0, 1), (2, 1)),   # +X
	((0, -1), (2, 1)),  # -X
	((1, 1), (0, 2)),   # +Y top
	((1, -1), (0, 2)),  # -Y bottom
)
PATCH_MARGIN = 0.06  # of a patch, so bleeding at patch edges stays inside


def cuboid(part):
	"""The part's box as an ObjMesh (game axes): 12 triangles, UVs, flat normals."""
	lo, hi = CUBOIDS[part]
	return box(lo, hi, part, TAPER.get(part, 1.0))


def box(lo, hi, cell='head', taper=1.0):
	"""A box from `lo` to `hi` (game axes), UV'd into an atlas cell.

	`taper` scales the +z end's x/y about the box's centre line.
	"""
	part = cell
	mesh = objfile.ObjMesh()
	for index, ((axis, sign), (u_axis, v_axis)) in enumerate(FACES):
		normal = [0.0, 0.0, 0.0]
		normal[axis] = float(sign)
		mesh.normals.append(tuple(normal))
		ni = len(mesh.normals) - 1
		corners = []
		for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
			point = [0.0, 0.0, 0.0]
			point[axis] = hi[axis] if sign > 0 else lo[axis]
			point[u_axis] = hi[u_axis] if du else lo[u_axis]
			point[v_axis] = hi[v_axis] if dv else lo[v_axis]
			if taper != 1.0 and point[2] == hi[2]:
				for a in (0, 1):
					mid = (lo[a] + hi[a]) / 2
					point[a] = mid + (point[a] - mid) * taper
			mesh.positions.append(tuple(point))
			mesh.uvs.append(_uv(part, index, du, dv))
			corners.append((len(mesh.positions) - 1, len(mesh.uvs) - 1, ni))
		# Keep the winding counter-clockwise seen from outside.
		if _flips(axis, sign, u_axis, v_axis):
			corners.reverse()
		if taper != 1.0:  # tapered sides lean: use the face's real normal
			a, b, c = (mesh.positions[corner[0]] for corner in corners[:3])
			mesh.normals[ni] = _normalized(_cross(_sub(b, a), _sub(c, a)))
		mesh.faces.append((corners[0], corners[1], corners[2]))
		mesh.faces.append((corners[0], corners[2], corners[3]))
	return mesh


def _sub(a, b):
	return tuple(x - y for x, y in zip(a, b))


def _cross(a, b):
	return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _normalized(v):
	length = sum(x * x for x in v) ** 0.5
	return tuple(x / length for x in v)


def _flips(axis, sign, u_axis, v_axis):
	"""Whether u x v points against the face's outward normal."""
	a, b = [0, 0, 0], [0, 0, 0]
	a[u_axis], b[v_axis] = 1, 1
	cross = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
	return cross[axis] * sign < 0


def _uv(part, face, du, dv):
	col, row = CELLS[part]
	pcol, prow = face % 3, face // 3
	inset = PATCH_MARGIN
	u = (col + (pcol + inset + du * (1 - 2 * inset)) / 3) / GRID
	v = (row + (prow + inset + dv * (1 - 2 * inset)) / 2) / GRID
	return (u, v)


def part_at(u, v):
	"""Which part's atlas cell holds UV (u, v), or None."""
	col, row = min(int(u * GRID), GRID - 1), min(int(v * GRID), GRID - 1)
	return next((p for p, cell in CELLS.items() if cell == (col, row)), None)


def textures(size=256):
	"""(color, mask) atlases as flat RGBA float lists, bottom row first.

	The layout Blender's Image.pixels expects.
	"""
	color, mask = [], []
	for y in range(size):
		for x in range(size):
			part = part_at((x + 0.5) / size, (y + 0.5) / size)
			tint = TINT.get(part)
			color.extend((*BASE_COLORS.get(part, TINTED), 1.0))
			mask.extend((*MASK_RGB[tint], 1.0))
	return color, mask


def icon(size=64):
	"""(icon, icon mask): a plain body-colored tile with a skin-colored face."""
	pixels, mask = [], []
	for y in range(size):
		for x in range(size):
			face = (x - size / 2) ** 2 + (y - size * 0.62) ** 2 < (size * 0.28) ** 2
			body = not face and y < size * 0.4 and abs(x - size / 2) < size * 0.3
			pixels.extend((*(SKIN if face else TINTED if body else (0.1, 0.1, 0.12)), 1.0))
			mask.extend((*MASK_RGB['color' if body else None], 1.0))
	return pixels, mask
