"""The eye handle: move and size the eyes in the viewport.

The engine draws each eye at `head + eye_scale * eye_offset`, sized by
`eye_scale` (spaz_node.cc DrawEyeBalls: scale, then translate), so in the
.bchar a bigger eye also sits further out. People think of an eye's
position and size separately, so the handle and the panel use those:

	position = eye_scale * eye_offset   (from the head centre, game axes)
	size     = eye_scale

The handle is a sphere empty on the head bone, around the +X eye (the one
eye_style_right styles); the other eye mirrors it. Its location is the
position and its (uniform) scale the size; its rotation is padlocked.
Handle and panel numbers stay in sync both ways, like attachment handles.
"""

import bpy
from mathutils import Matrix

from . import pose, rig, scene, transforms

HANDLE_KEY = 'bct_eye_handle'
# The eyeball's radius at size 1 (the game's eye mesh scale).
RADIUS = rig.EYE_MESH_SCALE


def position_from(offset, scale):
	return tuple(c * scale for c in offset)


def offset_from(position, scale):
	"""The .bchar eye_offset for a position and size (clamped to its range)."""
	lo, hi = rig.BASIC_SPAZ_RANGES['eye_offset']
	return tuple(min(max(c / scale, lo), hi) for c in position)


def handle(collection):
	return next((o for o in collection.all_objects if o.get(HANDLE_KEY)), None)


def build(collection, arm, group):
	"""The eye handle, placed from the character's settings."""
	placements, _ = pose.compute()
	obj = bpy.data.objects.new('eye_handle', None)
	group.objects.link(obj)
	obj.empty_display_type = 'SPHERE'
	obj.empty_display_size = RADIUS
	obj.hide_render = True
	obj.show_in_front = True
	obj.rotation_mode = transforms.EULER_ORDER
	obj.lock_rotation = (True, True, True)
	obj.ballistica_part.role = 'NONE'
	obj[HANDLE_KEY] = True
	scene.parent_to_bone(obj, arm, 'head', Matrix.Translation(scene.game_point(placements['head'].location)))
	push(collection)
	return obj


def push(collection):
	"""Settings -> handle."""
	obj = handle(collection)
	if obj is None or _syncing:
		return
	settings = collection.ballistica_character
	position = position_from(settings.eye_offset, settings.eye_scale)
	location = scene.game_point(position)
	if (obj.location - location).length > 1e-6:
		obj.location = location
	if any(abs(s - settings.eye_scale) > 1e-6 for s in obj.scale):
		obj.scale = (settings.eye_scale,) * 3


def pull(collection):
	"""Handle -> settings (an uneven scale counts as its average)."""
	obj = handle(collection)
	if obj is None:
		return
	settings = collection.ballistica_character
	lo, hi = rig.BASIC_SPAZ_RANGES['eye_scale']
	size = min(max(sum(obj.scale) / 3.0, lo), hi)
	position = tuple(transforms.vec_to_game(tuple(obj.location)))
	offset = offset_from(position, size)
	if abs(settings.eye_scale - size) > 1e-6:
		settings.eye_scale = size
	if any(abs(a - b) > 1e-6 for a, b in zip(settings.eye_offset, offset)):
		settings.eye_offset = offset


_syncing = False


@bpy.app.handlers.persistent
def on_depsgraph_update(scene_, depsgraph):
	"""The handle moved or was scaled in the viewport: update the settings."""
	global _syncing
	if _syncing:
		return
	moved = [
		u.id.original for u in depsgraph.updates
		if u.is_updated_transform and isinstance(u.id, bpy.types.Object) and u.id.original.get(HANDLE_KEY)
	]
	if not moved:
		return
	from .attach_scene import character_of

	_syncing = True
	try:
		for obj in moved:
			collection = character_of(obj)
			if collection is not None:
				pull(collection)
	finally:
		_syncing = False


def on_settings_changed(settings):
	"""props hook: eye_offset or eye_scale changed in the panel."""
	collection = settings.id_data
	if isinstance(collection, bpy.types.Collection) and settings.is_character:
		push(collection)


from . import props as _props  # noqa: E402

_props.ATTACHMENT_REBUILD_HOOKS['eye'] = on_settings_changed


def register():
	if on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
		bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)


def unregister():
	if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
		bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)
