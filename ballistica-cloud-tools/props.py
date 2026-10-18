"""Character settings stored on the character's collection.

Fields mirror the web UI form (same sections and order). Anything the
addon doesn't model is kept in `raw_json` and written back on export.
"""

import os

import bpy

from . import attachments as attach_rules
from . import bchar, rig, workspace

R = rig.BASIC_SPAZ_RANGES
D = rig.DEFAULTS


def _options():
	return set()  # Remove the ANIMATABLE default option.


def _float(name, field, **kwargs):
	lo, hi = R[field]
	return bpy.props.FloatProperty(name=name, default=D[field], min=lo, max=hi, options=_options(), **kwargs)


def _tag_collection(self, context):
	"""Re-evaluate drivers reading this setting (material tints).

	Setting a Python property on a collection doesn't tag the collection
	in the depsgraph by itself, so drivers wouldn't see the change.
	"""
	self.id_data.update_tag()


def _vec(name, field, color=False, default=None, span=None, update=None, description=''):
	lo, hi = span or R[field]
	kwargs = {'update': update} if update else {}
	return bpy.props.FloatVectorProperty(
		name=name, description=description, size=3, default=default or D[field], min=lo, max=hi,
		subtype='COLOR' if color else 'XYZ', options=_options(), **kwargs)


def _asset_search(kind, role=None):
	"""Search callback listing workspace assets, like the web UI dropdowns.

	`role` narrows textures to 'color', 'mask' or 'icon' (by name and
	workspace.json role) unless "Show All Assets" is on.
	"""

	def search(self, context, edit_text):
		# Attachment and segment settings live inside the character's.
		settings = self.id_data.ballistica_character
		root = settings.workspace_root
		if not root or not os.path.isdir(root):
			return []
		items = workspace.list_assets(root, kind)
		if role and not settings.show_all_assets:
			items = [i for i in items if _texture_matches(i, role)]
		return [i for i in items if edit_text.lower() in i.lower()]

	return search


def _texture_matches(logical, role):
	name = logical.rsplit('/', 1)[-1]
	is_icon = 'icon' in name
	is_mask = 'mask' in name
	if role == 'mask':
		return is_mask and not is_icon
	if role == 'icon_mask':
		return is_mask and is_icon
	if role == 'icon':
		return is_icon and not is_mask
	return not is_icon and not is_mask


def _ref(name, kind, role=None, update=None):
	kwargs = {'update': update} if update else {}
	return bpy.props.StringProperty(name=name, search=_asset_search(kind, role), options=_options(), **kwargs)


def _sounds(name):
	return bpy.props.StringProperty(
		name=name, description="Sound paths, separated by commas", options=_options())


def _eye_style(name):
	# Item order matters: the eye stand-ins' visibility drivers read the
	# enum as its index (see scene.build_eyes).
	return bpy.props.EnumProperty(
		name=name, items=[(s, s.capitalize(), '') for s in rig.EYE_STYLES],
		default=D['eye_style_left'], options=_options(), update=_tag_collection)


PART_ITEMS = [(p, p.replace('_', ' ').title(), '') for p, _, _ in rig.PARTS] + [
	('eye', 'Eye', 'Preview-only eye stand-in'),
	('attachment', 'Attachment', 'An attachment segment'),
	('guide', 'Guide', 'Preview-only physics body; never exported'),
]


class OBJECT_PG_ballistica_part(bpy.types.PropertyGroup):
	role: bpy.props.EnumProperty(name="Role", items=[('NONE', 'None', '')] + PART_ITEMS, options=_options())
	side: bpy.props.EnumProperty(
		name="Side", items=[('CENTER', 'Center', ''), ('R', 'Right', ''), ('L', 'Left', '')], options=_options())


# ---- attachments ----

AR = rig.ATTACHMENT_RANGES
_ATTACH_TUNING_NAMES = {
	'stiffness': "Stiffness", 'damping': "Damping", 'drag': "Drag",
	'curl': "Curl", 'length': "Length", 'radius': "Radius",
}


def _id_items(values):
	# Fixed ID numbers: the stored value stays the same option whichever
	# subset a dynamic enum offers.
	return [(v, v.replace('_', ' ').title(), '', i) for i, v in enumerate(values)]


_ALL_SIDES = _id_items(rig.ATTACH_SIDES)
_ALL_KINDS = _id_items(rig.ATTACH_KINDS)
# Dynamic enum items must stay referenced from Python, so build each subset once.
_SIDE_ITEMS = {t: [i for i in _ALL_SIDES if i[0] in attach_rules.allowed_sides(t)] for t in rig.ATTACH_TARGETS}
_KIND_ITEMS = {t: [i for i in _ALL_KINDS if i[0] in attach_rules.allowed_kinds(t)] for t in rig.ATTACH_TARGETS}


def _side_items(self, context):
	return _SIDE_ITEMS.get(self.target, _ALL_SIDES)


def _kind_items(self, context):
	return _KIND_ITEMS.get(self.target, _ALL_KINDS)


def _attachment_changed(self, context):
	"""Target, side or kind changed: keep the attachment valid, then rebuild it."""
	if self.get('_fixing'):
		return
	self['_fixing'] = True
	try:
		record = attachment_record(self)
		attach_rules.fix(record)
		if self.side != record['side']:
			self.side = record['side']
		if self.kind != record['kind']:
			self.kind = record['kind']
		_set_segments(self, record['segments'])
	finally:
		del self['_fixing']
	_attachment_rebuild(self)


def _segment_changed(self, context):
	"""A segment's mesh or textures changed: rebuild to show it."""
	if not self.get('_loading'):
		_attachment_rebuild(self)


def _placement_changed(self, context):
	"""A placement number changed in the panel: move its handle to match."""
	if self.get('_fixing') or self.get('_loading'):
		return
	hook = ATTACHMENT_REBUILD_HOOKS.get('push')
	if hook is not None:
		hook(self)


def _attachment_rebuild(attachment):
	"""Rebuild the character's attachment objects (set by attach_scene)."""
	hook = ATTACHMENT_REBUILD_HOOKS.get('rebuild')
	if hook is not None:
		hook(attachment)


# The scene module registers its rebuild function here, so props doesn't
# depend on scene (scene imports props).
ATTACHMENT_REBUILD_HOOKS = {}


def _tuning(name, field):
	lo, hi = AR[field]
	return bpy.props.FloatProperty(
		name=name, default=rig.ATTACHMENT_DEFAULTS[field], min=lo, max=hi, options=_options())


class COLLECTION_PG_ballistica_segment(bpy.types.PropertyGroup):
	mesh: _ref("Mesh", 'mesh', update=_segment_changed)
	texture: _ref("Texture", 'texture', 'color', update=_segment_changed)
	mask_texture: _ref("Mask Texture", 'texture', 'mask', update=_segment_changed)
	translate: bpy.props.FloatVectorProperty(
		name="Translate", size=3, subtype='TRANSLATION', options=_options(), update=_placement_changed,
		description="Where the segment's art sits on its body, game axes (Y up, Z forward)")
	rotate: bpy.props.FloatVectorProperty(
		name="Rotate", size=3, description="Heading, pitch, roll in degrees", options=_options(),
		update=_placement_changed)
	scale: bpy.props.FloatVectorProperty(
		name="Scale", size=3, default=(1.0, 1.0, 1.0), options=_options(), update=_placement_changed)


class COLLECTION_PG_ballistica_attachment(bpy.types.PropertyGroup):
	target: bpy.props.EnumProperty(
		name="Target", items=[(t, t.replace('_', ' ').title(), '') for t in rig.ATTACH_TARGETS],
		options=_options(), update=_attachment_changed)
	side: bpy.props.EnumProperty(name="Side", items=_side_items, options=_options(), update=_attachment_changed)
	kind: bpy.props.EnumProperty(name="Kind", items=_kind_items, options=_options(), update=_attachment_changed)
	translate: bpy.props.FloatVectorProperty(
		name="Translate", size=3, subtype='TRANSLATION', min=AR['position'][0], max=AR['position'][1],
		description="Where it sits on the target part, in the part's space, game axes (Y up, Z forward)",
		options=_options(), update=_placement_changed)
	rotate: bpy.props.FloatVectorProperty(
		name="Rotate", size=3, description="Heading, pitch, roll in degrees", options=_options(),
		update=_placement_changed)
	stiffness: _tuning("Stiffness", 'stiffness')
	damping: _tuning("Damping", 'damping')
	drag: _tuning("Drag", 'drag')
	curl: _tuning("Curl", 'curl')
	length: _tuning("Length", 'length')
	radius: _tuning("Radius", 'radius')
	curl_change: _tuning("Curl Change", 'curl_change')
	length_change: _tuning("Length Change", 'length_change')
	radius_change: _tuning("Radius Change", 'radius_change')
	stiffness_change: _tuning("Stiffness Change", 'stiffness_change')
	damping_change: _tuning("Damping Change", 'damping_change')
	segments: bpy.props.CollectionProperty(type=COLLECTION_PG_ballistica_segment)
	active_segment_index: bpy.props.IntProperty(name="Active Segment", options=_options())
	raw_json: bpy.props.StringProperty(
		name="Raw Attachment", description="This attachment's JSON as loaded; unmodelled keys are kept from here",
		options={'HIDDEN'})


ATTACHMENT_VALUES = ('translate', 'rotate', *attach_rules.TUNING, *attach_rules.TUNING_CHANGES)
SEGMENT_VALUES = ('translate', 'rotate', 'scale')


def attachment_record(attachment):
	"""An attachments-module record from an attachment's settings."""
	record = {'target': attachment.target, 'side': attachment.side or 'both', 'kind': attachment.kind or 'static'}
	for key in ATTACHMENT_VALUES:
		value = getattr(attachment, key)
		record[key] = tuple(value) if key in ('translate', 'rotate') else value
	record['segments'] = [
		{**{k: getattr(s, k) for k in attach_rules.SEGMENT_REFS}, **{k: tuple(getattr(s, k)) for k in SEGMENT_VALUES}}
		for s in attachment.segments
	]
	return record


def set_attachment(attachment, record, raw=None):
	"""Fill an attachment's settings from a record (and its original JSON)."""
	import json

	attachment['_fixing'] = True  # Don't fix or rebuild while loading.
	try:
		attachment.target = record['target']
		attachment.side = record['side']
		attachment.kind = record['kind']
		for key in ATTACHMENT_VALUES:
			setattr(attachment, key, record[key])
		_set_segments(attachment, record['segments'])
		if raw is not None:
			attachment.raw_json = json.dumps(raw)
	finally:
		del attachment['_fixing']


def _set_segments(attachment, segments):
	while len(attachment.segments) > len(segments):
		attachment.segments.remove(len(attachment.segments) - 1)
	while len(attachment.segments) < len(segments):
		attachment.segments.add()
	for item, segment in zip(attachment.segments, segments):
		item['_loading'] = True  # No rebuild or handle push per field; the caller handles it.
		try:
			for key in attach_rules.SEGMENT_REFS:
				if getattr(item, key) != segment[key]:
					setattr(item, key, segment[key])
			for key in SEGMENT_VALUES:
				setattr(item, key, segment[key])
		finally:
			del item['_loading']
	attachment.active_segment_index = min(attachment.active_segment_index, max(len(segments) - 1, 0))


class COLLECTION_PG_ballistica_character(bpy.types.PropertyGroup):
	is_character: bpy.props.BoolProperty(name="Is Character", default=False, options=_options())
	workspace_root: bpy.props.StringProperty(name="Workspace", subtype='DIR_PATH', options=_options())
	character_path: bpy.props.StringProperty(
		name="Character", description="Logical path of the .bchar, e.g. characters/zoe",
		search=_asset_search('character'), options=_options())
	raw_json: bpy.props.StringProperty(
		name="Raw Definition", description="The full .bchar as last loaded; unmodelled fields are kept from here",
		options={'HIDDEN'})
	spread: bpy.props.FloatProperty(
		name="Spread", description="Pull the parts apart (exploded view), as the web UI's Spread slider",
		default=0.0, min=0.0, max=1.0, subtype='FACTOR', options=_options(), update=_tag_collection)
	show_all_assets: bpy.props.BoolProperty(
		name="Show All Assets", description="List every asset in pickers, not just likely matches",
		default=False, options=_options())

	# Identity
	name: bpy.props.StringProperty(
		name="Name", description="Translation key of the display name, e.g. strings/characters/zoe",
		options=_options())
	icon_texture: _ref("Icon Texture", 'texture', 'icon')
	icon_mask_texture: _ref("Icon Mask Texture", 'texture', 'icon_mask')
	color: _vec("Color", 'color', color=True, default=(0.5, 0.5, 0.5), update=_tag_collection)
	highlight: _vec("Highlight", 'highlight', color=True, default=(0.5, 0.5, 0.5), update=_tag_collection)
	highlight_name: bpy.props.StringProperty(name="Highlight Name", description="Translation key", options=_options())
	highlight_editing: bpy.props.BoolProperty(name="Highlight Editing", default=D['highlight_editing'], options=_options())
	highlight2: _vec("Highlight 2", 'highlight2', color=True, span=(0.0, 1.0), update=_tag_collection)
	highlight2_name: bpy.props.StringProperty(name="Highlight 2 Name", description="Translation key", options=_options())
	highlight2_editing: bpy.props.BoolProperty(name="Highlight 2 Editing", default=D['highlight2_editing'], options=_options())

	# Textures
	color_texture: _ref("Color Texture", 'texture', 'color')
	color_mask_texture: _ref("Color Mask Texture", 'texture', 'mask')

	# Meshes
	head_mesh: _ref("Head Mesh", 'mesh')
	torso_mesh: _ref("Torso Mesh", 'mesh')
	pelvis_mesh: _ref("Pelvis Mesh", 'mesh')
	upper_arm_mesh: _ref("Upper Arm Mesh", 'mesh')
	forearm_mesh: _ref("Forearm Mesh", 'mesh')
	hand_mesh: _ref("Hand Mesh", 'mesh')
	upper_leg_mesh: _ref("Upper Leg Mesh", 'mesh')
	lower_leg_mesh: _ref("Lower Leg Mesh", 'mesh')
	toes_mesh: _ref("Toes Mesh", 'mesh')

	# Sounds
	jump_sounds: _sounds("Jump Sounds")
	attack_sounds: _sounds("Attack Sounds")
	impact_sounds: _sounds("Impact Sounds")
	death_sounds: _sounds("Death Sounds")
	pickup_sounds: _sounds("Pickup Sounds")
	fall_sounds: _sounds("Fall Sounds")

	# Physique
	torso_radius: _float("Torso Radius", 'torso_radius', update=_tag_collection)
	shoulder_offset: _vec(
		"Shoulder Offset", 'shoulder_offset', update=_tag_collection,
		description="Drives the shoulder_offset bones (right side; mirrored for the left)")
	thigh_radius: _float("Thigh Radius", 'thigh_radius', update=_tag_collection)
	ankle_radius: _float("Ankle Radius", 'ankle_radius', update=_tag_collection)
	step_separation: _float("Step Separation", 'step_separation')
	idle_arm_stiffness: _float("Idle Arm Stiffness", 'idle_arm_stiffness')
	arm_swing: _float("Arm Swing", 'arm_swing')
	idle_sway: _float("Idle Sway", 'idle_sway')

	# Eyes
	eye_style_left: _eye_style("Eye Style Left")
	eye_style_right: _eye_style("Eye Style Right")
	eye_scale: _float("Eye Scale", 'eye_scale', update=_tag_collection)
	eye_offset: _vec(
		"Eye Offset", 'eye_offset', update=_tag_collection,
		description="Drives the eye_offset bones: the +X eye (Eye Style Right) from the head centre, mirrored for the other; scaled by Eye Scale")
	eye_color: _vec("Eye Color", 'eye_color', color=True, update=_tag_collection)
	eyeball_color: _vec("Eyeball Color", 'eyeball_color', color=True, update=_tag_collection)
	eyelid_color: _vec("Eyelid Color", 'eyelid_color', color=True, update=_tag_collection)
	eyelid_angle: _float("Eyelid Angle", 'eyelid_angle', update=_tag_collection)

	# Surface
	reflection_scale: _float("Reflection Scale", 'reflection_scale')

	# Advanced (not in the web UI form)
	flippers: bpy.props.BoolProperty(
		name="Flippers", description="One long upper-arm mesh is the whole arm", default=False, options=_options())
	left_upper_arm_mesh: _ref("Left Upper Arm Mesh", 'mesh')
	left_forearm_mesh: _ref("Left Forearm Mesh", 'mesh')
	left_hand_mesh: _ref("Left Hand Mesh", 'mesh')
	left_upper_leg_mesh: _ref("Left Upper Leg Mesh", 'mesh')
	left_lower_leg_mesh: _ref("Left Lower Leg Mesh", 'mesh')
	left_toes_mesh: _ref("Left Toes Mesh", 'mesh')

	# Attachments (not in the web UI form)
	attachments: bpy.props.CollectionProperty(type=COLLECTION_PG_ballistica_attachment)
	active_attachment_index: bpy.props.IntProperty(name="Active Attachment", options=_options())


REF_FIELDS = (
	'icon_texture', 'icon_mask_texture', 'color_texture', 'color_mask_texture',
	*(field for _, field, _ in rig.PARTS),
	*(f'left_{p}_mesh' for p in rig.PAIRED_PARTS),
)
STRING_FIELDS = ('name', 'highlight_name', 'highlight2_name', *REF_FIELDS)
VALUE_FIELDS = (
	'color', 'highlight', 'highlight_editing', 'highlight2', 'highlight2_editing',
	'torso_radius', 'shoulder_offset', 'thigh_radius', 'ankle_radius', 'step_separation',
	'idle_arm_stiffness', 'arm_swing', 'idle_sway',
	'eye_style_left', 'eye_style_right', 'eye_scale', 'eye_offset', 'eye_color',
	'eyeball_color', 'eyelid_color', 'eyelid_angle', 'reflection_scale', 'flippers',
)


def load_into(settings, character):
	"""Fill collection settings from a bchar.Character."""
	import json

	settings.raw_json = json.dumps(character.raw)
	for field in STRING_FIELDS:
		setattr(settings, field, character.get(field) or '')
	for field in VALUE_FIELDS:
		value = character.get(field)
		if value is not None:
			if field in R and isinstance(value, (int, float)):
				value = rig.clamp(value, R[field])
			setattr(settings, field, value)
	for field in rig.SOUND_FIELDS:
		setattr(settings, field, ', '.join(character.get(field, [])))
	settings.attachments.clear()
	for raw in character.attachments:
		set_attachment(settings.attachments.add(), attach_rules.from_json(raw), raw)
	settings.active_attachment_index = 0


def to_character(settings):
	"""A bchar.Character built from the stored raw definition plus settings."""
	import json

	character = bchar.Character(json.loads(settings.raw_json) if settings.raw_json else None)
	for field in STRING_FIELDS:
		character.set(field, getattr(settings, field).strip())
	for field in VALUE_FIELDS:
		value = getattr(settings, field)
		character.set(field, tuple(value) if hasattr(value, '__len__') and not isinstance(value, str) else value)
	for field in rig.SOUND_FIELDS:
		sounds = [s.strip() for s in getattr(settings, field).split(',') if s.strip()]
		character.set(field, sounds)
	written = [
		attach_rules.to_json(attachment_record(a), json.loads(a.raw_json) if a.raw_json else None)
		for a in settings.attachments
	]
	if written:
		character.data['attachments'] = written
	else:
		character.data.pop('attachments', None)
	return character


classes = (
	OBJECT_PG_ballistica_part,
	COLLECTION_PG_ballistica_segment,
	COLLECTION_PG_ballistica_attachment,
	COLLECTION_PG_ballistica_character,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.Collection.ballistica_character = bpy.props.PointerProperty(type=COLLECTION_PG_ballistica_character)
	bpy.types.Object.ballistica_part = bpy.props.PointerProperty(type=OBJECT_PG_ballistica_part)


def unregister():
	del bpy.types.Object.ballistica_part
	del bpy.types.Collection.ballistica_character
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
