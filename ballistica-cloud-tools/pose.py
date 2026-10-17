"""The rest pose, from the rig numbers. Game space throughout.

An estimate of the web UI's pose (standing, arms out and a little down,
legs straight down), close enough to model against. Bodies start at the
rig's stand heights; the whole pose is then shifted so the feet (the toes
balls) rest on the ground at y=0. (In the game the roller ball does the
walking and the legs dangle a little above its bottom.)
Each limb segment is placed so its joint anchors meet, using the rig's
anchor points on each body. Only the right side is computed; the left is
the mirror in x.
"""

import math

from . import rig

ARM_DROP_DEGREES = 20.0


class Placement:
	"""A body's rest placement: location and rotation (3x3, columns = axes)."""

	def __init__(self, location, rotation):
		self.location = tuple(location)
		self.rotation = rotation

	def point(self, local):
		"""A point given in this body's space, in game space."""
		return _add(self.location, _apply(self.rotation, local))


IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def compute(shoulder_offset=(0.0, 0.0, 0.0), arm_drop=ARM_DROP_DEGREES):
	"""Placements for every right-side body part, plus joint positions.

	Returns (placements, joints): placements maps part name to Placement;
	joints maps joint name to a game-space point.
	"""
	placements = {}
	joints = {}

	torso = Placement((0.0, rig.STAND_TORSO_HEIGHT, 0.0), IDENTITY)
	head = Placement((0.0, rig.STAND_HEAD_HEIGHT, 0.0), IDENTITY)
	pelvis = Placement((0.0, rig.STAND_PELVIS_HEIGHT, 0.0), IDENTITY)
	placements.update(torso=torso, head=head, pelvis=pelvis)
	joints['head'] = head.location
	joints['neck'] = torso.point((0.0, rig.SHOULDER_ON_TORSO[1], 0.0))
	joints['spine'] = torso.point((0.0, -rig.PELVIS_JOINT_DROP, rig.PELVIS_JOINT_FORWARD))
	joints['pelvis'] = pelvis.location

	# Arm: out to the character's right (-X), dropped a little.
	drop = math.radians(arm_drop)
	arm = _aim((-math.cos(drop), -math.sin(drop), 0.0), up=(0.0, 1.0, 0.0))
	shoulder = torso.point(_add(rig.SHOULDER_ON_TORSO, shoulder_offset))
	upper_arm = _attach(shoulder, arm, rig.SHOULDER_ON_UPPER_ARM)
	elbow = upper_arm.point(rig.ELBOW_ON_UPPER_ARM)
	forearm = _attach(elbow, arm, rig.ELBOW_ON_LOWER_ARM)
	wrist = forearm.point((0.0, 0.0, rig.LOWER_ARM_LENGTH / 2 + rig.LOWER_ARM_RADIUS))
	turn = _rot_y(math.radians(rig.HAND_TURN))
	hand = Placement(forearm.point((0.0, 0.0, rig.HAND_OFFSET)), _mul(arm, turn))
	placements.update(upper_arm=upper_arm, forearm=forearm, hand=hand)
	joints.update(shoulder=shoulder, elbow=elbow, wrist=wrist)

	# Leg: straight down, knee forward axis = +Z.
	leg = _aim((0.0, -1.0, 0.0), up=(0.0, 0.0, 1.0))
	hip = pelvis.point(rig.HIP_ON_PELVIS)
	upper_leg = _attach(hip, leg, rig.HIP_ON_UPPER_LEG)
	knee = upper_leg.point(rig.KNEE_ON_UPPER_LEG)
	lower_leg = _attach(knee, leg, rig.KNEE_ON_LOWER_LEG)
	ankle = lower_leg.point(rig.ANKLE_ON_LOWER_LEG)
	# The foot shares the leg's frame (z down, y forward), as the engine
	# draws it; the toes mesh is long along its own y.
	toes = _attach(ankle, leg, rig.ANKLE_ON_TOES)
	placements.update(upper_leg=upper_leg, lower_leg=lower_leg, toes=toes)
	joints.update(hip=hip, knee=knee, ankle=ankle, toe_tip=toes.point((0.0, rig.TOES_RADIUS, 0.0)))

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
