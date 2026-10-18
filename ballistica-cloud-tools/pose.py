"""The rest pose: the web UI's character preview pose. Game space.

Matches the web UI's preview data exactly (tests/fixtures/lucky_preview.json):
arms out and 20 degrees down with palms facing down, elbows bent 20 degrees
forward, thighs swung 20 degrees forward and shins 20 degrees back, feet
flat. Each body is placed so the rig's joint anchors meet; parts sit on
their bodies with no extra offset. The whole pose is then shifted so the
feet rest on the ground at y=0. Only the right side is computed; the left
is the mirror in x.
"""

import math

from . import rig

ARM_DROP_DEGREES = 20.0  # arms below horizontal
ELBOW_BEND_DEGREES = 20.0  # forearm bent forward from the upper arm
THIGH_SWING_DEGREES = 20.0  # thigh swung forward from straight down
SHIN_SWING_DEGREES = 20.0  # shin swung back from straight down

# Bone display ends the rig doesn't define, from the web UI's pivots.
NECK_HEIGHT = 0.2  # above the torso centre
HAND_TIP = 0.07  # along the hand
TOE_TIP = 0.0425  # forward of the toes centre

# The web UI's exploded-view ("spread") offset per part, game space, at
# full spread. Eyes and head attachments follow the head; the roller
# follows the pelvis.
SPREAD = {
	'head': (0.0, 0.4, 0.0),
	'torso': (0.0, 0.0, 0.0),
	'pelvis': (0.0, -0.24, 0.0),
	'upper_arm': (-0.22553, -0.08208, 0.0),
	'forearm': (-0.45105, -0.16417, 0.0),
	'hand': (-0.67658, -0.24625, 0.0),
	'upper_leg': (-0.084, -0.48, 0.0),
	'lower_leg': (-0.168, -0.72, 0.0),
	'toes': (-0.252, -0.96, 0.0),
	'wing': (0.0, 0.0, 0.0),
}


class Placement:
	"""A body's rest placement: location and rotation (3x3, columns = axes)."""

	def __init__(self, location, rotation):
		self.location = tuple(location)
		self.rotation = rotation

	def point(self, local):
		"""A point given in this body's space, in game space."""
		return _add(self.location, _apply(self.rotation, local))


IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def compute(shoulder_offset=(0.0, 0.0, 0.0)):
	"""Placements for every right-side body part, plus joint positions.

	Returns (placements, joints): placements maps part name to Placement;
	joints maps joint name to a game-space point.
	"""
	placements = {}
	joints = {}

	torso = Placement((0.0, rig.STAND_TORSO_HEIGHT, 0.0), IDENTITY)
	head = Placement((0.0, rig.STAND_HEAD_HEIGHT, 0.0), IDENTITY)
	# The pelvis hangs from the torso's spine joint, which sits forward.
	pelvis = Placement((0.0, rig.STAND_PELVIS_HEIGHT, rig.PELVIS_JOINT_FORWARD), IDENTITY)
	placements.update(torso=torso, head=head, pelvis=pelvis)
	joints['head'] = head.location
	joints['neck'] = torso.point((0.0, NECK_HEIGHT, 0.0))
	joints['spine'] = torso.point((0.0, -rig.PELVIS_JOINT_DROP, rig.PELVIS_JOINT_FORWARD))
	joints['pelvis'] = pelvis.location

	# Arm: out to the character's right (-X) and down, +Y forward so the
	# palms face down; the elbow bends the forearm forward.
	drop = math.radians(ARM_DROP_DEGREES)
	arm = _aim((-math.cos(drop), -math.sin(drop), 0.0), up=(0.0, 0.0, 1.0))
	shoulder = torso.point(_add(rig.SHOULDER_ON_TORSO, shoulder_offset))
	upper_arm = _attach(shoulder, arm, rig.SHOULDER_ON_UPPER_ARM)
	elbow = upper_arm.point(rig.ELBOW_ON_UPPER_ARM)
	forearm_rot = _mul(arm, _rot_x(-math.radians(ELBOW_BEND_DEGREES)))
	forearm = _attach(elbow, forearm_rot, rig.ELBOW_ON_LOWER_ARM)
	turn = _rot_y(math.radians(rig.HAND_TURN))
	hand = Placement(forearm.point((0.0, 0.0, rig.HAND_OFFSET)), _mul(forearm_rot, turn))
	placements.update(upper_arm=upper_arm, forearm=forearm, hand=hand)
	joints.update(shoulder=shoulder, elbow=elbow, wrist=hand.location, hand_tip=hand.point((0.0, 0.0, HAND_TIP)))

	# Leg: from straight down (z down, y forward), the thigh swings forward
	# and the shin back, bending the knee; the foot stays flat.
	leg = _aim((0.0, -1.0, 0.0), up=(0.0, 0.0, 1.0))
	hip = pelvis.point(rig.HIP_ON_PELVIS)
	upper_leg = _attach(hip, _mul(leg, _rot_x(-math.radians(THIGH_SWING_DEGREES))), rig.HIP_ON_UPPER_LEG)
	knee = upper_leg.point(rig.KNEE_ON_UPPER_LEG)
	lower_leg = _attach(knee, _mul(leg, _rot_x(math.radians(SHIN_SWING_DEGREES))), rig.KNEE_ON_LOWER_LEG)
	ankle = lower_leg.point(rig.ANKLE_ON_LOWER_LEG)
	# The foot shares the straight leg's frame; its mesh is long along y.
	toes = _attach(ankle, leg, rig.ANKLE_ON_TOES)
	placements.update(upper_leg=upper_leg, lower_leg=lower_leg, toes=toes)
	joints.update(hip=hip, knee=knee, ankle=ankle, toe_tip=toes.point((0.0, TOE_TIP, 0.0)))

	# Wing: frame at the torso centre, +Z out toward the wing's rest point
	# (behind and to the side), +Y up (ApplyWingTransform_).
	wing = Placement(torso.location, _aim(rig.WING_ATTACH, up=(0.0, 1.0, 0.0)))
	placements['wing'] = wing
	joints['wing_tip'] = wing.point((0.0, 0.0, 0.3))
	joints['roller'] = (0.0, rig.STAND_ROLLER_HEIGHT, 0.0)
	joints['torso'] = torso.location

	# Stand the feet on the ground.
	drop = (0.0, toes.location[1] - rig.TOES_RADIUS, 0.0)
	placements = {k: Placement(_sub(v.location, drop), v.rotation) for k, v in placements.items()}
	joints = {k: _sub(v, drop) for k, v in joints.items()}
	return placements, joints


def mirror(point):
	"""The left-side counterpart of a right-side point."""
	return (-point[0], point[1], point[2])


def _attach(joint, rotation, anchor_on_body):
	"""Place a body so `anchor_on_body` (its own space) lands on `joint`."""
	return Placement(_sub(joint, _apply(rotation, anchor_on_body)), rotation)


def _aim(forward, up):
	"""Rotation whose +Z is `forward` and whose +Y is as close to `up` as possible."""
	z = _norm(forward)
	y = _norm(_sub(up, _scale(z, _dot(up, z))))
	x = _cross(y, z)
	return tuple(zip(x, y, z))  # rows of a matrix whose columns are x, y, z


def _rot_x(t):
	c, s = math.cos(t), math.sin(t)
	return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def _rot_y(t):
	c, s = math.cos(t), math.sin(t)
	return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def _apply(m, v):
	return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def _mul(a, b):
	return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _add(a, b):
	return tuple(x + y for x, y in zip(a, b))


def _sub(a, b):
	return tuple(x - y for x, y in zip(a, b))


def _scale(a, s):
	return tuple(x * s for x in a)


def _dot(a, b):
	return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
	return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
	length = math.sqrt(_dot(a, a))
	return tuple(x / length for x in a)
