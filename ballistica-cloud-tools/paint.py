"""Painting the body textures, and brushes for the colour mask.

The colour mask is three separate channels: red tints with the player's
colour, green with the highlight, blue with the second highlight. So the
mask brushes add (or remove) one channel at a time, instead of painting a
colour: going over a red area with Highlight makes it red + green, tinted
by both, as the game does.

Brushes are local assets in the file (Blender 4.3+ activates brushes as
assets), made the first time they're used.
"""

import bpy

PREFIX = "Ballistica "
# Key -> (name, blend mode, colour, description).
BRUSHES = {
	'COLOR': ("Player Colour", 'ADD', (1.0, 0.0, 0.0), "Tint with the player's colour (adds red to the mask)"),
	'HIGHLIGHT': ("Highlight", 'ADD', (0.0, 1.0, 0.0), "Tint with the highlight colour (adds green to the mask)"),
	'HIGHLIGHT2': ("Highlight 2", 'ADD', (0.0, 0.0, 1.0), "Tint with the second highlight colour (adds blue to the mask)"),
	'REMOVE': ("Remove Tint", 'SUB', (1.0, 1.0, 1.0), "Take every tint away: back to the colour texture's own colours"),
}


def brush(key):
	"""The addon's brush for `key`, made (and marked as an asset) if missing."""
	label, blend, color, _ = BRUSHES[key]
	name = PREFIX + label
	found = bpy.data.brushes.get(name)
	if found is None:
		found = bpy.data.brushes.new(name, mode='TEXTURE_PAINT')
		found.asset_mark()
	found.blend = blend
	found.color = color
	return found


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
	found = brush(key)
	bpy.ops.brush.asset_activate(asset_library_type='LOCAL', relative_asset_identifier=f'Brush/{found.name}')
	# Brush colour is shared between brushes by default: set that too.
	unified = context.scene.tool_settings.image_paint.unified_paint_settings
	if unified.use_unified_color:
		unified.color = found.color
	return found
