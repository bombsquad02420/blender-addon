"""Painting the body textures, and brushes for the color mask.

The color mask is three separate channels: red tints with the player's
color, green with the highlight, blue with the second highlight. So the
mask brushes add (or remove) one channel at a time, instead of painting a
color: going over a red area with Highlight makes it red + green, tinted
by both, as the game does.

The brushes ship in the addon's asset file (assets/build_assets.py), in
the "Ballistica Cloud Tools" library's Mask Brushes catalog, so they're
always in the brush shelf; activating one appends it to the file.
"""

import os

import bpy

PREFIX = "Ballistica "
# Mask channel per tint: key -> (name, color).
TINTS = {
	'COLOR': ("Player Color", (1.0, 0.0, 0.0)),
	'HIGHLIGHT': ("Highlight", (0.0, 1.0, 0.0)),
	'HIGHLIGHT2': ("Highlight 2", (0.0, 0.0, 1.0)),
}
# What a brush does to its channel: key -> (word, blend mode, hard edge, description).
ACTIONS = {
	'ADD': ("Add", 'ADD', False, "Tint with {tint}, keeping other tints (adds {channel} to the mask)"),
	'ERASE': ("Erase", 'SUB', False, "Erase {tint}, keeping other tints (removes {channel} from the mask)"),
	'ONLY': ("Only", 'MIX', True, "Tint with {tint} and nothing else, with a hard edge (paints pure {channel})"),
}
CHANNELS = {'COLOR': "red", 'HIGHLIGHT': "green", 'HIGHLIGHT2': "blue"}


def _brushes():
	"""Key -> (name, blend mode, color, hard edge, description)."""
	brushes = {}
	for tint, (tint_name, color) in TINTS.items():
		for action, (word, blend, hard, description) in ACTIONS.items():
			brushes[f'{action}_{tint}'] = (
				f"{word} {tint_name}", blend, color, hard,
				description.format(tint=f"the {tint_name.lower()}", channel=CHANNELS[tint]))
	brushes['ERASE_ALL'] = ("Erase All Tints", 'SUB', (1.0, 1.0, 1.0), False,
		"Erase every tint: back to the color texture's own colors")
	return brushes


BRUSHES = _brushes()


def part_object(collection):
	"""The body part to paint on: the selected Parts row's, else the torso."""
	settings = collection.ballistica_character
	parts = [o for o in collection.all_objects if o.type == 'MESH' and o.ballistica_part.role in [r.part for r in settings.parts]]
	if 0 <= settings.active_part_index < len(settings.parts):
		row = settings.parts[settings.active_part_index]
		for obj in parts:
			if obj.ballistica_part.role == row.part and (obj.ballistica_part.side == 'L') == (row.side == 'L'):
				return obj
	return next((o for o in parts if o.ballistica_part.role == 'torso'), parts[0] if parts else None)


def start(context, collection, image):
	"""Texture Paint on a body part, painting `image` (whatever the material shows)."""
	view_layer = context.view_layer
	obj = context.active_object
	if obj is None or obj.mode != 'TEXTURE_PAINT' or obj.ballistica_part.role == 'NONE':
		obj = part_object(collection)
		if obj is None:
			return False
		if context.mode != 'OBJECT':
			bpy.ops.object.mode_set(mode='OBJECT')
		for other in view_layer.objects.selected:
			other.select_set(False)
		obj.hide_set(False)
		obj.select_set(True)
		view_layer.objects.active = obj
		bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
	settings = context.scene.tool_settings.image_paint
	settings.mode = 'IMAGE'  # paint this image, whatever the material
	settings.canvas = image
	return True


def use_brush(context, key):
	"""Make the addon's brush for `key` the active texture paint brush."""
	from . import nodegroup

	name = PREFIX + BRUSHES[key][0]
	bpy.ops.brush.asset_activate(
		asset_library_type='CUSTOM', asset_library_identifier=nodegroup.LIBRARY_NAME,
		relative_asset_identifier=f'{os.path.basename(nodegroup.ASSETS_BLEND)}/Brush/{name}')
	match_shared_color(context)
	return context.scene.tool_settings.image_paint.brush


def match_shared_color(context=None):
	"""If one of the addon's brushes is active, give the shared color its tint.

	Blender's brush color is shared between brushes by default (the
	"unified" toggle beside the color). The panel's brush buttons set it;
	a brush picked from the shelf doesn't, so the paint box offers to turn
	the shared color off, and warns while it's on.
	"""
	context = context or bpy.context
	scene = getattr(context, 'scene', None)
	if scene is None:
		return
	settings = scene.tool_settings.image_paint
	brush = settings.brush
	if brush is None or not brush.name.startswith(PREFIX):
		return
	unified = settings.unified_paint_settings
	if unified.use_unified_color and tuple(unified.color) != tuple(brush.color):
		unified.color = brush.color
