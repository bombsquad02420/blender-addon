"""Attachment templates: ready-made hats, tails, wings and the like.

Each template is an attachment record (target, kind, placement, spring
tuning) with a generated low-poly mesh per segment and its own small
texture and color mask, so it looks right on any character without
touching the body's texture. The meshes and textures are written to
assets/attachments/ by assets/build_template.py and shipped; adding a
template copies them into the character (like New Character's body), so
they can later be swapped for hand-made files.

Pure Python: geometry is built as objfile.ObjMesh in game axes (Y up,
Z forward). Static attachments are modelled in their target part's space
around the anchor; springy segments lie along their own +Z, centred on
the segment (antenna segments are 0.13 long).
"""

import math
import os

from . import attachments, objfile

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'attachments')
TEXTURE_SIZE = 64
SEGMENT = 0.13  # an antenna segment's length


def obj_path(key, segment, count):
	return os.path.join(TEMPLATE_DIR, f'{key}.obj' if count == 1 else f'{key}_{segment}.obj')


def texture_path(key, mask):
	return os.path.join(TEMPLATE_DIR, f'{key}_color_mask.png' if mask else f'{key}_color.png')


# ---- geometry ----

def _sub(a, b):
	return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
	return tuple(x + y for x, y in zip(a, b))


def _scale(v, s):
	return tuple(x * s for x in v)


def _cross(a, b):
	return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
	return sum(x * y for x, y in zip(a, b))


def _unit(v):
	length = math.sqrt(_dot(v, v)) or 1.0
	return _scale(v, 1.0 / length)


class _Builder:
	"""Collects flat-shaded triangles, each facing away from its shape's centre."""

	def __init__(self):
		self.mesh = objfile.ObjMesh()

	def triangle(self, corners, centre):
		"""`corners`: three ((x, y, z), (u, v)); flipped to face away from `centre`."""
		(a, _), (b, _), (c, _) = corners
		normal = _cross(_sub(b, a), _sub(c, a))
		middle = _scale(_add(_add(a, b), c), 1.0 / 3.0)
		if _dot(normal, _sub(middle, centre)) < 0:
			corners = (corners[0], corners[2], corners[1])
			normal = _scale(normal, -1.0)
		mesh = self.mesh
		mesh.normals.append(_unit(normal))
		face = []
		for position, uv in corners:
			mesh.positions.append(tuple(position))
			mesh.uvs.append(tuple(min(max(c, 0.0), 1.0) for c in uv))
			face.append((len(mesh.positions) - 1, len(mesh.uvs) - 1, len(mesh.normals) - 1))
		mesh.faces.append(tuple(face))

	def quad(self, corners, centre):
		self.triangle((corners[0], corners[1], corners[2]), centre)
		self.triangle((corners[0], corners[2], corners[3]), centre)


def _basis(axis):
	"""Two unit vectors perpendicular to `axis` (and to each other)."""
	helper = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
	u = _unit(_cross(axis, helper))
	return u, _cross(axis, u)


def frustum(builder, p0, p1, r0, r1, segments=10):
	"""A capped cone or cylinder from p0 (radius r0) to p1 (radius r1)."""
	axis = _unit(_sub(p1, p0))
	u, v = _basis(axis)
	centre = _scale(_add(p0, p1), 0.5)

	def ring(point, radius, i):
		angle = 2 * math.pi * i / segments
		return _add(point, _add(_scale(u, radius * math.cos(angle)), _scale(v, radius * math.sin(angle))))

	for i in range(segments):
		a0, a1 = ring(p0, r0, i), ring(p0, r0, i + 1)
		b0, b1 = ring(p1, r1, i), ring(p1, r1, i + 1)
		s0, s1 = 0.05 + 0.9 * i / segments, 0.05 + 0.9 * (i + 1) / segments
		if r1 > 1e-9:
			builder.quad(((a0, (s0, 0.1)), (a1, (s1, 0.1)), (b1, (s1, 0.9)), (b0, (s0, 0.9))), centre)
		else:
			builder.triangle(((a0, (s0, 0.1)), (a1, (s1, 0.1)), (p1, ((s0 + s1) / 2, 0.9))), centre)
		if r0 > 1e-9:
			builder.triangle(((p0, (0.5, 0.05)), (a0, (s0, 0.05)), (a1, (s1, 0.05))), centre)
		if r1 > 1e-9:
			builder.triangle(((p1, (0.5, 0.95)), (b0, (s0, 0.95)), (b1, (s1, 0.95))), centre)


def sphere(builder, centre, radius, squash=(1.0, 1.0, 1.0), segments=10, rings=6):
	"""A UV sphere, scaled per axis by `squash`."""

	def point(ring, i):
		lat = math.pi * ring / rings - math.pi / 2
		lon = 2 * math.pi * i / segments
		local = (math.cos(lat) * math.cos(lon), math.sin(lat), math.cos(lat) * math.sin(lon))
		return _add(centre, tuple(c * radius * s for c, s in zip(local, squash))), (i / segments, ring / rings)

	for ring in range(rings):
		for i in range(segments):
			a, b, c, d = point(ring, i), point(ring, i + 1), point(ring + 1, i + 1), point(ring + 1, i)
			if ring == 0:
				builder.triangle((a, c, d), centre)
			elif ring == rings - 1:
				builder.triangle((a, b, c), centre)
			else:
				builder.quad((a, b, c, d), centre)


def box(builder, lo, hi):
	"""An axis-aligned box from `lo` to `hi`."""
	centre = _scale(_add(lo, hi), 0.5)
	for axis in range(3):
		for side in (lo, hi):
			u_axis, v_axis = [a for a in range(3) if a != axis]
			corners = []
			for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
				p = [0.0, 0.0, 0.0]
				p[axis] = side[axis]
				p[u_axis] = hi[u_axis] if du else lo[u_axis]
				p[v_axis] = hi[v_axis] if dv else lo[v_axis]
				corners.append((tuple(p), (0.1 + 0.8 * du, 0.1 + 0.8 * dv)))
			builder.quad(corners, centre)


def plate(builder, outline, x0, x1):
	"""A convex outline in the (y, z) plane, given thickness from x0 to x1."""
	ys, zs = [p[0] for p in outline], [p[1] for p in outline]

	def uv(y, z):
		return (0.05 + 0.9 * (z - min(zs)) / ((max(zs) - min(zs)) or 1), 0.05 + 0.9 * (y - min(ys)) / ((max(ys) - min(ys)) or 1))

	mid = (sum(ys) / len(ys), sum(zs) / len(zs))
	centre = ((x0 + x1) / 2, mid[0], mid[1])
	count = len(outline)
	for x in (x0, x1):
		for i in range(1, count - 1):
			builder.triangle(tuple(((x, *outline[k]), uv(*outline[k])) for k in (0, i, i + 1)), centre)
	for i in range(count):
		(ya, za), (yb, zb) = outline[i], outline[(i + 1) % count]
		builder.quad((((x0, ya, za), uv(ya, za)), ((x0, yb, zb), uv(yb, zb)),
			((x1, yb, zb), uv(yb, zb)), ((x1, ya, za), uv(ya, za))), centre)


def _mesh(*parts):
	builder = _Builder()
	for make in parts:
		make(builder)
	return builder.mesh


def _segment_stalk(r0, r1, length=SEGMENT * 1.15):
	"""A tapered piece along a springy segment's +Z (a little long, to overlap)."""
	half = length / 2
	return lambda b: frustum(b, (0.0, 0.0, -half), (0.0, 0.0, half), r0, r1)


# ---- the templates ----

class Template:
	def __init__(self, key, label, icon, description, target, kind, translate, rotate, segments,
			color, tint=None, side='both', tuning=None, segment_transforms=None):
		self.key = key
		self.label = label
		self.icon = icon
		self.description = description
		self.target = target
		self.kind = kind
		self.side = side
		self.translate = translate
		self.rotate = rotate
		self.segments = segments  # one function per segment: () -> ObjMesh
		self.segment_transforms = segment_transforms or [None] * len(segments)
		self.color = color  # the texture's color
		self.tint = tint  # None, or the mask channel: 'color', 'highlight', 'highlight2'
		self.tuning = tuning or {}

	def record(self, meshes, texture='', mask=''):
		"""An attachments-module record using the given mesh paths."""
		record = attachments.new_attachment(self.target, self.kind)
		record.update(side=self.side, translate=self.translate, rotate=self.rotate)
		record.update(self.tuning)
		for segment, mesh, transform in zip(record['segments'], meshes, self.segment_transforms):
			segment.update(mesh=mesh, texture=texture, mask_texture=mask)
			if transform:
				segment.update(transform)
		return record

	def textures(self, size=TEXTURE_SIZE):
		"""(color, mask) as flat RGBA float lists: one flat color, tinted or not."""
		tint = {'color': (1.0, 0.0, 0.0), 'highlight': (0.0, 1.0, 0.0), 'highlight2': (0.0, 0.0, 1.0), None: (0.0, 0.0, 0.0)}
		color = list(self.color) + [1.0]
		mask = list(tint[self.tint]) + [1.0]
		return color * (size * size), mask * (size * size)


def _horn(sign):
	return lambda b: frustum(b, (sign * 0.12, 0.0, 0.02), (sign * 0.27, 0.22, 0.07), 0.065, 0.0)


def _crown(b):
	frustum(b, (0.0, 0.0, 0.0), (0.0, 0.06, 0.0), 0.15, 0.15, segments=12)
	for i in range(6):
		angle = 2 * math.pi * i / 6
		base = (0.13 * math.cos(angle), 0.05, 0.13 * math.sin(angle))
		frustum(b, base, (base[0], 0.15, base[2]), 0.035, 0.0, segments=6)


TEMPLATES = [
	Template(
		'hat', "Hat", 'MESH_CYLINDER', "A top hat on the head, tinted with the highlight",
		'head', 'static', (0.0, 0.19, 0.0), (0.0, 0.0, 0.0),
		[lambda: _mesh(
			lambda b: frustum(b, (0.0, 0.0, 0.0), (0.0, 0.025, 0.0), 0.27, 0.27, segments=14),
			lambda b: frustum(b, (0.0, 0.02, 0.0), (0.0, 0.22, 0.0), 0.17, 0.16, segments=14))],
		color=(1.0, 1.0, 1.0), tint='highlight'),
	Template(
		'crown', "Crown", 'SOLO_ON', "A gold crown on the head",
		'head', 'static', (0.0, 0.16, 0.0), (0.0, 0.0, 0.0),
		[lambda: _mesh(_crown)], color=(1.0, 0.78, 0.2)),
	Template(
		'horns', "Horns", 'MOD_SIMPLEDEFORM', "Two horns on the head",
		'head', 'static', (0.0, 0.13, 0.0), (0.0, 0.0, 0.0),
		[lambda: _mesh(_horn(1), _horn(-1))], color=(0.95, 0.9, 0.78)),
	Template(
		'antenna', "Bobble Antenna", 'LIGHT_POINT', "A wobbly antenna with a ball on top, tinted with the player color",
		'head', 'antenna_2', (0.0, 0.2, 0.0), (0.0, 90.0, 0.0),
		[lambda: _mesh(_segment_stalk(0.015, 0.013)),
			lambda: _mesh(_segment_stalk(0.013, 0.011), lambda b: sphere(b, (0.0, 0.0, 0.08), 0.05))],
		color=(1.0, 1.0, 1.0), tint='color', tuning={'stiffness': 0.3, 'damping': 0.3}),
	Template(
		'ponytail', "Ponytail", 'FORCE_CURVE', "A swinging ponytail at the back of the head",
		'head', 'antenna_3', (0.0, 0.08, -0.21), (180.0, -40.0, 0.0),
		[lambda: _mesh(_segment_stalk(0.06, 0.05)), lambda: _mesh(_segment_stalk(0.05, 0.04)),
			lambda: _mesh(_segment_stalk(0.04, 0.02))],
		color=(0.42, 0.25, 0.12), tuning={'stiffness': 0.4, 'damping': 0.6}),
	Template(
		'backpack', "Backpack", 'PACKAGE', "A backpack, tinted with the player color",
		'torso', 'static', (0.0, 0.02, -0.14), (0.0, 0.0, 0.0),
		[lambda: _mesh(lambda b: box(b, (-0.12, -0.14, -0.12), (0.12, 0.14, 0.0)),
			lambda b: box(b, (-0.08, -0.12, -0.15), (0.08, -0.02, -0.11)))],
		color=(1.0, 1.0, 1.0), tint='color'),
	Template(
		'cape', "Cape", 'MOD_CLOTH', "A cape that flaps behind, tinted with the player color",
		'torso', 'antenna_2', (0.0, 0.12, -0.15), (180.0, -70.0, 0.0),
		[lambda: _mesh(lambda b: box(b, (-0.15, -0.012, -0.08), (0.15, 0.012, 0.08))),
			lambda: _mesh(lambda b: box(b, (-0.17, -0.012, -0.08), (0.17, 0.012, 0.08)))],
		color=(1.0, 1.0, 1.0), tint='color', tuning={'stiffness': 0.2, 'damping': 0.7, 'drag': 0.6}),
	Template(
		'tail', "Tail", 'FORCE_HARMONIC', "A swishing tail, tinted with the highlight",
		'pelvis', 'antenna_3', (0.0, 0.0, -0.1), (180.0, 15.0, 0.0),
		[lambda: _mesh(_segment_stalk(0.055, 0.045)), lambda: _mesh(_segment_stalk(0.045, 0.034)),
			lambda: _mesh(_segment_stalk(0.034, 0.0))],
		color=(1.0, 1.0, 1.0), tint='highlight', tuning={'stiffness': 0.3, 'damping': 0.5}),
	Template(
		'wings', "Wings", 'MOD_SMOOTH', "A pair of wings on the back",
		'wing', 'static', (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
		[lambda: _mesh(lambda b: plate(b, [(0.0, 0.06), (0.38, 0.18), (0.32, 0.5), (0.06, 0.42)], -0.01, 0.01))],
		color=(0.88, 0.95, 1.0)),
	Template(
		'shoulder_pads', "Shoulder Pads", 'MESH_UVSPHERE', "Armour on both shoulders, tinted with the highlight",
		'upper_arm', 'static', (0.0, 0.03, -0.08), (0.0, 0.0, 0.0),
		[lambda: _mesh(lambda b: sphere(b, (0.0, 0.0, 0.0), 0.105, squash=(1.15, 0.8, 1.1)))],
		color=(1.0, 1.0, 1.0), tint='highlight'),
	# Hands: modelled on the right hand (the left mirrors it). The fist runs
	# along +Z from the wrist; the knuckles face +Y, the outside is -X.
	Template(
		'sword', "Sword", 'MOD_LINEART', "A sword held in the right hand",
		'hand', 'static', (0.0, 0.0, 0.04), (0.0, 0.0, 0.0),
		[lambda: _mesh(
			lambda b: box(b, (-0.01, 0.08, -0.035), (0.01, 0.48, 0.035)),
			lambda b: frustum(b, (0.0, 0.48, 0.0), (0.0, 0.55, 0.0), 0.035, 0.0, segments=4),
			lambda b: box(b, (-0.02, 0.06, -0.09), (0.02, 0.085, 0.09)),
			lambda b: frustum(b, (0.0, -0.1, 0.0), (0.0, 0.07, 0.0), 0.018, 0.018, segments=8),
			lambda b: sphere(b, (0.0, -0.11, 0.0), 0.03))],
		color=(0.8, 0.82, 0.86), side='right'),
	Template(
		'shield', "Shield", 'FAKE_USER_ON', "A round shield on the left arm, tinted with the player color",
		'hand', 'static', (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
		[lambda: _mesh(
			lambda b: frustum(b, (-0.06, 0.0, 0.0), (-0.09, 0.0, 0.0), 0.2, 0.19, segments=16),
			lambda b: sphere(b, (-0.09, 0.0, 0.0), 0.05, squash=(0.6, 1.0, 1.0)))],
		color=(1.0, 1.0, 1.0), tint='color', side='left'),
	Template(
		'claws', "Claws", 'MOD_DECIM', "Three claws out of each fist",
		'hand', 'static', (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
		[lambda: _mesh(*[
			(lambda x: lambda b: frustum(b, (x, 0.03, 0.06), (x, 0.06, 0.28), 0.014, 0.0, segments=6))(x)
			for x in (-0.035, 0.0, 0.035)])],
		color=(0.85, 0.85, 0.9)),
]
BY_KEY = {t.key: t for t in TEMPLATES}
