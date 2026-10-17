"""Character settings stored on the character's collection.

Fields mirror the web UI form (same sections and order). Anything the
addon doesn't model is kept in `raw_json` and written back on export.
"""

import os

import bpy

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


def _vec(name, field, color=False, default=None, span=None, update=None, driven=False):
	lo, hi = span or R[field]
	kwargs = {'update': update} if update else {}
	if driven:
		kwargs['description'] = "Driven by the armature: move the bone in Pose Mode"
	return bpy.props.FloatVectorProperty(
		name=name, size=3, default=default or D[field], min=lo, max=hi,
		subtype='COLOR' if color else 'XYZ',
		options={'ANIMATABLE'} if driven else _options(), **kwargs)


def _asset_search(kind, role=None):
	"""Search callback listing workspace assets, like the web UI dropdowns.

	`role` narrows textures to 'color', 'mask' or 'icon' (by name and
	workspace.json role) unless "Show All Assets" is on.
	"""

	def search(self, context, edit_text):
		root = self.workspace_root
		if not root or not os.path.isdir(root):
			return []
		items = workspace.list_assets(root, kind)
		if role and not self.show_all_assets:
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


def _ref(name, kind, role=None):
	return bpy.props.StringProperty(name=name, search=_asset_search(kind, role), options=_options())


def _sounds(name):
	return bpy.props.StringProperty(
		name=name, description="Sound paths, separated by commas", options=_options())


def _eye_style(name):
	return bpy.props.EnumProperty(
		name=name, items=[(s, s.capitalize(), '') for s in rig.EYE_STYLES],
		default=D['eye_style_left'], options=_options())


PART_ITEMS = [(p, p.replace('_', ' ').title(), '') for p, _, _ in rig.PARTS] + [
	('eye', 'Eye', 'Preview-only eye stand-in'),
	('attachment', 'Attachment', 'An attachment segment'),
	('guide', 'Guide', 'Preview-only physics body; never exported'),
]


class OBJECT_PG_ballistica_part(bpy.types.PropertyGroup):
	role: bpy.props.EnumProperty(name="Role", items=[('NONE', 'None', '')] + PART_ITEMS, options=_options())
	side: bpy.props.EnumProperty(
		name="Side", items=[('CENTER', 'Center', ''), ('R', 'Right', ''), ('L', 'Left', '')], options=_options())


class OBJECT_PG_ballistica_rig(bpy.types.PropertyGroup):
	"""Placement values driven by the character's armature bones.

	Collections can't hold drivers, so these live on the armature object;
	while it exists they override the collection's stored values.
	"""
	shoulder_offset: _vec("Shoulder Offset", 'shoulder_offset', driven=True)
	eye_offset: _vec("Eye Offset", 'eye_offset', driven=True)


RIG_FIELDS = ('shoulder_offset', 'eye_offset')


def armature_of(collection):
	return next((o for o in collection.objects if o.type == 'ARMATURE'), None)


class COLLECTION_PG_ballistica_character(bpy.types.PropertyGroup):
	is_character: bpy.props.BoolProperty(name="Is Character", default=False, options=_options())
	workspace_root: bpy.props.StringProperty(name="Workspace", subtype='DIR_PATH', options=_options())
	character_path: bpy.props.StringProperty(
		name="Character", description="Logical path of the .bchar, e.g. characters/zoe",
		search=_asset_search('character'), options=_options())
	raw_json: bpy.props.StringProperty(
		name="Raw Definition", description="The full .bchar as last loaded; unmodelled fields are kept from here",
		options={'HIDDEN'})
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
	torso_radius: _float("Torso Radius", 'torso_radius')
	shoulder_offset: _vec("Shoulder Offset", 'shoulder_offset')
	thigh_radius: _float("Thigh Radius", 'thigh_radius')
	ankle_radius: _float("Ankle Radius", 'ankle_radius')
	step_separation: _float("Step Separation", 'step_separation')
	idle_arm_stiffness: _float("Idle Arm Stiffness", 'idle_arm_stiffness')
	arm_swing: _float("Arm Swing", 'arm_swing')
	idle_sway: _float("Idle Sway", 'idle_sway')

	# Eyes
	eye_style_left: _eye_style("Eye Style Left")
	eye_style_right: _eye_style("Eye Style Right")
	eye_scale: _float("Eye Scale", 'eye_scale')
	eye_offset: _vec("Eye Offset", 'eye_offset')
	eye_color: _vec("Eye Color", 'eye_color', color=True)
	eyeball_color: _vec("Eyeball Color", 'eyeball_color', color=True)
	eyelid_color: _vec("Eyelid Color", 'eyelid_color', color=True)
	eyelid_angle: _float("Eyelid Angle", 'eyelid_angle')

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
	arm = armature_of(settings.id_data)
	if arm is not None:
		for field in RIG_FIELDS:
			character.set(field, tuple(getattr(arm.ballistica_rig, field)))
	return character


classes = (
	OBJECT_PG_ballistica_part,
	OBJECT_PG_ballistica_rig,
	COLLECTION_PG_ballistica_character,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.Collection.ballistica_character = bpy.props.PointerProperty(type=COLLECTION_PG_ballistica_character)
	bpy.types.Object.ballistica_part = bpy.props.PointerProperty(type=OBJECT_PG_ballistica_part)
	bpy.types.Object.ballistica_rig = bpy.props.PointerProperty(type=OBJECT_PG_ballistica_rig)


def unregister():
	del bpy.types.Object.ballistica_rig
	del bpy.types.Object.ballistica_part
	del bpy.types.Collection.ballistica_character
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
