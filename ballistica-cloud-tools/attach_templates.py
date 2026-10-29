"""Attachment templates: ready-made hats, tails, swords and the like.

Each template is an attachment record (target, kind, placement, spring
tuning) plus a hand-made mesh per segment, shipped in assets/attachments/
(edited in assets/source/attachment_templates.blend; see
assets/attachment_blend.py). All templates share one texture atlas and
its color mask (ATLAS), so a character gets one attachment texture
however many templates it adds. Adding a template copies these files
into the character, so they can be edited like any other.

Static attachments are modelled in their target part's space around the
anchor; springy segments lie along their own +Z, centred on the segment.
"""

import os

from . import attachments

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'attachments')
# The shared texture atlas and its color mask.
ATLAS = 'attachments_color'
ATLAS_MASK = 'attachments_color_mask'


def obj_path(key, segment, count):
	return os.path.join(TEMPLATE_DIR, f'{key}.obj' if count == 1 else f'{key}_{segment}.obj')


def texture_path(mask):
	return os.path.join(TEMPLATE_DIR, f'{ATLAS_MASK if mask else ATLAS}.png')


class Template:
	def __init__(self, key, label, icon, description, target, kind, translate, rotate,
			side='both', tuning=None, segment_transforms=None):
		self.key = key
		self.label = label
		self.icon = icon
		self.description = description
		self.target = target
		self.kind = kind
		self.side = side
		self.translate = translate
		self.rotate = rotate
		self.segment_count = attachments.segment_count(kind)
		self.segment_transforms = segment_transforms or [None] * self.segment_count
		self.tuning = tuning or {}

	def obj_paths(self):
		return [obj_path(self.key, index, self.segment_count) for index in range(self.segment_count)]

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


TEMPLATES = [
	Template(
		'hat', "Hat", 'MESH_CYLINDER', "A top hat on the head",
		'head', 'static', (0.0, 0.19, 0.0), (0.0, 0.0, 0.0)),
	Template(
		'crown', "Crown", 'SOLO_ON', "A crown on the head",
		'head', 'static', (0.0, 0.16, 0.0), (0.0, 0.0, 0.0)),
	Template(
		'horn', "Horn", 'MOD_SIMPLEDEFORM', "A horn on the head (add another for a pair)",
		'head', 'static', (0.0, 0.13, 0.0), (0.0, 0.0, 0.0)),
	Template(
		'antenna', "Bobble Antenna", 'LIGHT_POINT', "A wobbly antenna with a ball on top",
		'head', 'antenna_2', (0.0, 0.2, 0.0), (0.0, 90.0, 0.0),
		tuning={'stiffness': 0.3, 'damping': 0.3}),
	Template(
		'ponytail', "Ponytail", 'FORCE_CURVE', "A swinging ponytail at the back of the head",
		'head', 'antenna_3', (0.0, 0.08, -0.21), (180.0, -40.0, 0.0),
		tuning={'stiffness': 0.4, 'damping': 0.6}),
	Template(
		'backpack', "Backpack", 'PACKAGE', "A backpack",
		'torso', 'static', (0.0, 0.02, -0.14), (0.0, 0.0, 0.0)),
	Template(
		'cape', "Cape", 'MOD_CLOTH', "A cape that flaps behind",
		'torso', 'antenna_2', (0.0, 0.12, -0.15), (180.0, -70.0, 0.0),
		tuning={'stiffness': 0.2, 'damping': 0.7, 'drag': 0.6}),
	Template(
		'tail', "Tail", 'FORCE_HARMONIC', "A swishing tail",
		'pelvis', 'antenna_3', (0.0, 0.0, -0.1), (180.0, 15.0, 0.0),
		tuning={'stiffness': 0.3, 'damping': 0.5}),
	Template(
		'wings', "Wings", 'MOD_SMOOTH', "A pair of wings on the back",
		'wing', 'static', (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
	# Hands: modelled on the right hand (the left mirrors it). The fist runs
	# along +Z from the wrist; the knuckles face +Y, the outside is -X.
	Template(
		'sword', "Sword", 'MOD_LINEART', "A sword held in the right hand",
		'hand', 'static', (0.0, 0.0, 0.04), (0.0, 0.0, 0.0), side='right'),
	Template(
		'shield', "Shield", 'FAKE_USER_ON', "A round shield on the left arm",
		'hand', 'static', (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), side='left'),
	Template(
		'claws', "Claws", 'MOD_DECIM', "Three claws out of each fist",
		'hand', 'static', (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
]
BY_KEY = {t.key: t for t in TEMPLATES}
