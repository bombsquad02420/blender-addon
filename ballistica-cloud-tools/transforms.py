"""Game space <-> Blender space.

Game: Y up, Z forward (a part's "nose"), the character's right is -X.
Blender: Z up, -Y forward. So game (x, y, z) is Blender (x, -z, y), the
same conversion as the old addon's axis_conversion(from_forward='-Z',
from_up='Y').

`.bchar` rotations are heading, pitch, roll in degrees, applied in that
order as turns of the thing's own axes (characterbuilder.BuilderTransform):
heading about up (positive turns the nose to the character's right),
pitch about +X (positive raises the nose), roll about the nose (positive
is clockwise seen from behind). In game axes that is
R = Ry(-h) . Rx(-p) . Rz(r), which in Blender axes is an Euler in 'YXZ'
mode with (x, y, z) = (-p, -r, -h) in radians.

Derived from the docstring; the server's own conversion isn't available.
Pure Python so it can be tested without Blender.
"""

import math

EULER_ORDER = 'YXZ'


def vec_to_blender(v):
	x, y, z = v
	return (x, -z, y)


def vec_to_game(v):
	x, y, z = v
	return (x, z, -y)


def rotate_to_blender_euler(rotate):
	"""`.bchar` [heading, pitch, roll] degrees -> Blender YXZ Euler radians."""
	h, p, r = (math.radians(a) for a in rotate)
	return (-p, -r, -h)


def blender_euler_to_rotate(euler):
	"""Blender YXZ Euler radians -> `.bchar` [heading, pitch, roll] degrees."""
	ex, ey, ez = euler
	return [_clean(math.degrees(-ez)), _clean(math.degrees(-ex)), _clean(math.degrees(-ey))]


def euler_to_matrix(euler):
	"""YXZ Euler (x, y, z) -> 3x3 rotation matrix rows, R = Rz . Rx . Ry."""
	x, y, z = euler
	return _mul(_mul(_rz(z), _rx(x)), _ry(y))


def _clean(deg):
	value = round(deg, 4)
	return 0.0 if value == 0 else value


def _rx(t):
	c, s = math.cos(t), math.sin(t)
	return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(t):
	c, s = math.cos(t), math.sin(t)
	return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _rz(t):
	c, s = math.cos(t), math.sin(t)
	return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _mul(a, b):
	return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
