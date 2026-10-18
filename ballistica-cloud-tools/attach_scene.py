"""Attachments in the scene: placement handles and their meshes.

For each attachment (and each side it's drawn on):

	anchor empty      bone-parented to the target part; rest place on the
	                  bone in its parent inverse; its own location and
	                  rotation (mode YXZ) ARE the .bchar transform.
	  segment handle  child of the anchor; the kind's joint chain in its
	                  parent inverse; its own location/rotation/scale are
	                  the segment's transform.
	    mesh          child of the handle with an identity transform: move
	                  it freely to work on it; export and placement ignore
	                  it, and Reset to T-Pose puts it back.

Handles are the saved placement: they live in the Rig collection, and
`sync_from_handles` reads them back into the attachment settings. Left
copies of `side: both` limb attachments follow the right side's handles
by drivers, so only right-side (or centre) handles are edited.
"""

import bpy
from mathutils import Matrix

from . import attachments as rules
from . import pose, rig, scene, transforms, workspace

ANCHOR = 'anchor'
HANDLE = 'handle'
MESH = 'attachment'
ROLE_KEY = 'bct_attach_role'
INDEX_KEY = 'bct_attachment'
SEGMENT_KEY = 'bct_segment'
SIDE_KEY = 'bct_side'
LOGICAL_KEY = 'bct_logical'
ROOT_KEY = 'bct_root'


def _sides(record):
	if record['target'] not in rules.LIMB_TARGETS:
		return ['C']
	return [s for s, _ in scene.SIDES if record['side'] == 'both' or (record['side'], s) in (('right', 'R'), ('left', 'L'))]


def _group(collection, name):
	return bpy.data.collections.get(f'{collection.name} {name}') or collection


def _armature(collection):
	return next((o for o in collection.all_objects if o.type == 'ARMATURE'), None)


def tagged(collection, role=None, index=None):
	"""Attachment objects of this character, optionally by role and index."""
	return [
		o for o in collection.all_objects
		if o.get(ROLE_KEY) and (role is None or o[ROLE_KEY] == role) and (index is None or o.get(INDEX_KEY) == index)
	]


def anchor(collection, index):
	"""The editable (right or centre) anchor of attachment `index`."""
	return next((o for o in tagged(collection, ANCHOR, index) if o.get(SIDE_KEY) != 'L'), None)


def handle(collection, index, segment):
	return next(
		(o for o in tagged(collection, HANDLE, index) if o.get(SEGMENT_KEY) == segment and o.get(SIDE_KEY) != 'L'),
		None)


# ---- meshes and materials ----

def mesh_for(root, logical):
	"""The Blender mesh for an attachment mesh path.

	A mesh already loaded (or made) for this path is reused, so rebuilding
	an attachment keeps edits made to its mesh in Blender. Otherwise it's
	read from the workspace; None if it isn't there either.
	"""
	if not logical:
		return None
	for mesh in bpy.data.meshes:
		if mesh.get(LOGICAL_KEY) == logical and mesh.get(ROOT_KEY) == root:
			return mesh
	path = workspace.file_path(root, logical, 'mesh')
	if path is None:
		return None
	mesh = scene.mesh_from_obj(path, logical)
	tag_mesh(mesh, root, logical)
	return mesh


def tag_mesh(mesh, root, logical):
	mesh[LOGICAL_KEY] = logical
	mesh[ROOT_KEY] = root


def _material(collection, settings, segment):
	texture = segment.texture or settings.color_texture
	mask = segment.mask_texture or settings.color_mask_texture
	if (texture, mask) == (settings.color_texture, settings.color_mask_texture):
		name = collection.name
	else:
		name = f'{collection.name}_{texture.rsplit("/", 1)[-1]}'
	material = bpy.data.materials.get(name)
	if material is None:
		material = scene.build_material(name, settings.workspace_root, texture, mask, collection)
	return material


# ---- build / clear ----

def build(collection, placements=None, spread=True):
	"""Create handles and meshes for every attachment in the settings.

	`spread=False` when the caller sets up spread drivers for the whole
	character afterwards (import), so anchors don't get them twice.
	"""
	settings = collection.ballistica_character
	arm = _armature(collection)
	if arm is None:
		return []
	if placements is None:
		placements, _ = pose.compute()
	created = []
	for index, attachment in enumerate(settings.attachments):
		created += _build_one(collection, settings, arm, placements, index, attachment)
	_mirror_drivers(collection)
	if spread:
		scene.setup_spread_drivers(collection, [o for o in created if o.get(ROLE_KEY) == ANCHOR])
	return created


def _build_one(collection, settings, arm, placements, index, attachment):
	from . import props

	record = props.attachment_record(attachment)
	rig_group = _group(collection, 'Rig')
	mesh_group = _group(collection, 'Attachments')
	anchors = rig.ATTACHMENT_ANCHORS.get(record['kind'], ())
	created = []
	for side in _sides(record):
		suffix = '' if side == 'C' else f'.{side}'
		body = scene.placement_matrix(placements[record['target']])
		if side == 'L':
			body = scene.MIRROR_X @ body
		bone = scene.bone_name(record['target'], 'R' if side == 'C' else side)
		spot = _empty(f'attach{index}{suffix}', rig_group, 'ARROWS', 0.08)
		scene.parent_to_bone(spot, arm, bone, body)
		_set_transform(spot, record['translate'], record['rotate'])
		_tag(spot, ANCHOR, index, side)
		created.append(spot)
		chain = Matrix.Identity(4)
		for j, segment in enumerate(record['segments']):
			if record['kind'] != 'static' and j < len(anchors):
				parent_anchor, child_anchor = anchors[j]
				if j > 0:
					chain = chain @ Matrix.Translation(scene.game_point(parent_anchor))
				chain = chain @ Matrix.Translation(-scene.game_point(child_anchor))
			grip = _empty(f'attach{index}.{j}{suffix}', rig_group, 'PLAIN_AXES', 0.05)
			grip.parent = spot
			grip.matrix_parent_inverse = chain.copy()
			_set_transform(grip, segment['translate'], segment['rotate'], segment['scale'])
			_tag(grip, HANDLE, index, side, j)
			created.append(grip)
			mesh = mesh_for(settings.workspace_root, segment['mesh'])
			if mesh is None:
				continue
			obj = bpy.data.objects.new(f'attachment{index}.{j}{suffix}', mesh)
			mesh_group.objects.link(obj)
			obj.parent = grip
			obj.ballistica_part.role = 'attachment'
			obj.ballistica_part.side = {'C': 'CENTER'}.get(side, side)
			if not mesh.materials:
				mesh.materials.append(_material(collection, settings, attachment.segments[j]))
			_tag(obj, MESH, index, side, j)
			created.append(obj)
	return created


def _empty(name, group, display, size):
	obj = bpy.data.objects.new(name, None)
	group.objects.link(obj)
	obj.empty_display_type = display
	obj.empty_display_size = size
	obj.hide_render = True
	obj.rotation_mode = transforms.EULER_ORDER
	obj.ballistica_part.role = 'NONE'
	return obj


def _tag(obj, role, index, side, segment=None):
	obj[ROLE_KEY] = role
	obj[INDEX_KEY] = index
	obj[SIDE_KEY] = side
	if segment is not None:
		obj[SEGMENT_KEY] = segment


def _set_transform(obj, translate, rotate, scale=(1.0, 1.0, 1.0)):
	obj.location = scene.game_point(translate)
	obj.rotation_euler = transforms.rotate_to_blender_euler(rotate)
	sx, sy, sz = scale
	obj.scale = (sx, sz, sy)  # game (x, y, z) -> Blender (x, z, y)


def _mirror_drivers(collection):
	"""Left copies follow the right side's handles."""
	for obj in tagged(collection):
		if obj.get(SIDE_KEY) != 'L' or obj[ROLE_KEY] == MESH:
			continue
		source = next(
			(o for o in tagged(collection, obj[ROLE_KEY], obj[INDEX_KEY])
				if o.get(SIDE_KEY) == 'R' and o.get(SEGMENT_KEY) == obj.get(SEGMENT_KEY)),
			None)
		if source is None:
			continue
		for path in ('location', 'rotation_euler', 'scale'):
			for i in range(3):
				driver = obj.driver_add(path, i).driver
				driver.type = 'AVERAGE'
				var = driver.variables.new()
				var.type = 'SINGLE_PROP'
				var.targets[0].id_type = 'OBJECT'
				var.targets[0].id = source
				var.targets[0].data_path = f'{path}[{i}]'


def clear(collection):
	"""Remove every attachment handle and mesh object (mesh data is kept)."""
	for obj in tagged(collection):
		bpy.data.objects.remove(obj)


def sync_from_handles(collection):
	"""Write the handles' placement into the attachment settings."""
	from . import props

	settings = collection.ballistica_character
	for index, attachment in enumerate(settings.attachments):
		spot = anchor(collection, index)
		if spot is None:
			continue
		record = props.attachment_record(attachment)
		record['translate'], record['rotate'], _ = _read_transform(spot)
		for j, segment in enumerate(record['segments']):
			grip = handle(collection, index, j)
			if grip is not None:
				segment['translate'], segment['rotate'], segment['scale'] = _read_transform(grip)
		props.set_attachment(attachment, record)


def _read_transform(obj):
	translate = tuple(transforms.vec_to_game(tuple(obj.location)))
	if obj.rotation_mode != transforms.EULER_ORDER:
		euler = obj.matrix_basis.to_euler(transforms.EULER_ORDER)
	else:
		euler = obj.rotation_euler
	rotate = tuple(transforms.blender_euler_to_rotate(tuple(euler)))
	sx, sz, sy = obj.scale
	return translate, rotate, (sx, sy, sz)


def rebuild(collection):
	"""Keep handle edits, then recreate every attachment's objects."""
	sync_from_handles(collection)
	clear(collection)
	return build(collection)


def rebuild_for(item):
	"""props hook: rebuild the character an attachment or segment belongs to."""
	collection = item.id_data
	if isinstance(collection, bpy.types.Collection) and collection.ballistica_character.is_character:
		rebuild(collection)


from . import props as _props  # noqa: E402  (props must not import scene modules)

_props.ATTACHMENT_REBUILD_HOOKS['rebuild'] = rebuild_for
