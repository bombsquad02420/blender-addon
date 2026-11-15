"""The shoulder handle: move the shoulders in the viewport.

`shoulder_offset` moves where the arms join the torso (the right arm's, in
game axes; the left mirrors it). The handle is a small sphere empty at the
right shoulder: its location IS the offset. It hangs from a hidden spread
parent on the torso bone (scene.spread_parent), and a Limit Location
constraint keeps it in the game's range (-0.05 to 0.03 per axis) while
it's dragged. Handle and panel numbers stay in sync both ways, like the
eye handle. The shoulder_offset bones still follow the setting by driver
(scene.setup_offset_drivers).
"""

import bpy
from mathutils import Matrix

from . import pose, rig, scene, transforms

HANDLE_KEY = 'bct_shoulder_handle'
RADIUS = 0.04


def handle(collection):
	return next((o for o in collection.all_objects if o.get(HANDLE_KEY)), None)


def rest_matrix(placements):
	"""Where the handle rests: the right shoulder joint, game axes."""
	return Matrix.Translation(scene.game_point(placements['torso'].point(rig.SHOULDER_ON_TORSO)))


def build(collection, arm, group):
	placements, _ = pose.compute()
	obj = bpy.data.objects.new('shoulder_handle', None)
	group.objects.link(obj)
	obj.empty_display_type = 'SPHERE'
	obj.empty_display_size = RADIUS
	obj.hide_render = True
	obj.show_in_front = True
	obj.rotation_mode = transforms.EULER_ORDER
	obj.lock_rotation = (True, True, True)  # only where it is matters
	obj.lock_scale = (True, True, True)
	obj.ballistica_part.role = 'NONE'
	obj[HANDLE_KEY] = True
	layer = scene.spread_parent('shoulder_handle spread', group, arm, 'torso', rest_matrix(placements))
	scene.hang(obj, layer)
	scene.limit_location(obj, *_game_range())
	push(collection)
	return obj


def _game_range():
	"""The offset's range per game axis, as (low corner, high corner)."""
	lo, hi = rig.BASIC_SPAZ_RANGES['shoulder_offset']
	return (lo, lo, lo), (hi, hi, hi)


def remove(collection):
	"""Delete the handle and its spread parent (Repair builds them again)."""
	obj = handle(collection)
	if obj is None:
		return
	layer = obj.parent if obj.parent is not None and obj.parent.get(scene.SPREAD_KEY) else None
	bpy.data.objects.remove(obj)
	if layer is not None:
		bpy.data.objects.remove(layer)


_syncing = False


def push(collection):
	"""Settings -> handle."""
	obj = handle(collection)
	if obj is None or _syncing:
		return
	location = scene.game_point(collection.ballistica_character.shoulder_offset)
	if (obj.location - location).length > 1e-6:
		obj.location = location


def pull(collection):
	"""Handle -> settings (clamped to the game's range)."""
	obj = handle(collection)
	if obj is None:
		return
	lo, hi = rig.BASIC_SPAZ_RANGES['shoulder_offset']
	offset = tuple(min(max(c, lo), hi) for c in transforms.vec_to_game(tuple(obj.location)))
	settings = collection.ballistica_character
	if any(abs(a - b) > 1e-6 for a, b in zip(settings.shoulder_offset, offset)):
		settings.shoulder_offset = offset


@bpy.app.handlers.persistent
def on_depsgraph_update(scene_, depsgraph):
	"""The handle moved in the viewport: update the setting."""
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
	"""props hook: shoulder_offset changed in the panel."""
	collection = settings.id_data
	if isinstance(collection, bpy.types.Collection) and settings.is_character:
		push(collection)


from . import props as _props  # noqa: E402

_props.ATTACHMENT_REBUILD_HOOKS['shoulder'] = on_settings_changed


def register():
	if on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
		bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)


def unregister():
	if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
		bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)
