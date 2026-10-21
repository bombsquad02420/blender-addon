"""Body parts: the Parts list and the objects that follow it.

The character's `parts` rows hold which Blender mesh each part uses, in
rig order: one row per part (right side for limbs), then a Left row per
limb. The scene follows the rows:

- A right (or centre) row's mesh is shown by its object; a limb's left
  object shows it too, unless the Left row is on.
- An optional part (pelvis, forearm, hand) whose row is off has no
  objects; its mesh stays in the row, so turning it back on restores it.
- A Left row that's on gives the left limb its own mesh (it starts as a
  copy of the right one).

The .bchar's mesh fields are written from the rows on export; a row
without a mesh keeps the field it was loaded with (a file that wasn't
found stays referenced).
"""

import bpy

from . import attach_scene, pose, rig, scene, template

OPTIONAL_PARTS = tuple(p for p, _, required in rig.PARTS if not required)
FIELDS = {p: f for p, f, _ in rig.PARTS}
# (part, side) in list order.
ROWS = [(p, 'R' if p in rig.PAIRED_PARTS else 'CENTER') for p, _, _ in rig.PARTS] + [(p, 'L') for p in rig.PAIRED_PARTS]

_quiet = False  # True while rows are filled in code: no scene updates.


def is_optional(row):
	return row.side == 'L' or row.part in OPTIONAL_PARTS


def label(row):
	name = row.part.replace('_', ' ').title()
	return f"Left {name}" if row.side == 'L' else name


def field(row):
	"""The .bchar field a row writes."""
	return f'left_{row.part}_mesh' if row.side == 'L' else FIELDS[row.part]


def rows(settings, part):
	"""(right or centre row, left row or None) of a part."""
	right = left = None
	for row in settings.parts:
		if row.part == part:
			if row.side == 'L':
				left = row
			else:
				right = row
	return right, left


def has_rows(settings):
	return [(r.part, r.side) for r in settings.parts] == ROWS


def _objects(collection, part):
	right = [o for o in collection.all_objects if o.ballistica_part.role == part and o.ballistica_part.side != 'L']
	left = [o for o in collection.all_objects if o.ballistica_part.role == part and o.ballistica_part.side == 'L']
	return right, left


def fill_rows(collection):
	"""Make the rows match the character's objects and mesh fields.

	Used after building a character, and by Repair for files from before the
	Parts list.
	"""
	global _quiet
	settings = collection.ballistica_character
	_quiet = True
	try:
		if not has_rows(settings):
			settings.parts.clear()
			for part, side in ROWS:
				row = settings.parts.add()
				row.part, row.side = part, side
		for row in settings.parts:
			right, left = _objects(collection, row.part)
			if row.side == 'L':
				row.enabled = bool(getattr(settings, field(row)))
				own = [o.data for o in left if not right or o.data != right[0].data]
				row.mesh = own[0] if own else None
			else:
				row.enabled = bool(getattr(settings, field(row))) or bool(right)
				row.mesh = right[0].data if right else attach_scene.mesh_for(settings.workspace_root, getattr(settings, field(row)))
	finally:
		_quiet = False


def update_part(collection, part):
	"""Make `part`'s objects match its rows."""
	settings = collection.ballistica_character
	if not has_rows(settings):
		fill_rows(collection)  # a file from before the Parts list
	right_row, left_row = rows(settings, part)
	right, left = _objects(collection, part)
	mesh = right_row.mesh if right_row is not None and right_row.enabled else None
	if mesh is None:
		for obj in right + left:
			bpy.data.objects.remove(obj)
		return
	created = _show(collection, part, 'R' if part in rig.PAIRED_PARTS else 'CENTER', mesh, right)
	if part in rig.PAIRED_PARTS:
		own = left_row.mesh if left_row is not None and left_row.enabled else None
		created += _show(collection, part, 'L', own or mesh, left)
	if created:
		scene.setup_spread_drivers(collection, created)


def _show(collection, part, side, mesh, existing):
	"""Point existing objects at `mesh`, or create the part's object."""
	from .repair import body_material

	material = body_material(collection)
	for obj in existing:
		if obj.data != mesh:
			obj.data = mesh
		if material is not None:
			scene.assign_material(obj, material)
	if existing:
		return []
	arm = next((o for o in collection.all_objects if o.type == 'ARMATURE'), None)
	group = scene.group(collection, scene.PART_GROUPS[part]) or collection
	if arm is None:
		return []
	placements, _ = pose.compute()
	name = f'{part}.{side}' if part in rig.PAIRED_PARTS else part
	obj = bpy.data.objects.new(name, mesh)
	group.objects.link(obj)
	if material is not None:
		scene.assign_material(obj, material)
	obj.ballistica_part.role = part
	obj.ballistica_part.side = side
	world = scene.placement_matrix(placements[part])
	if side == 'L':
		world = scene.MIRROR_X @ world
	scene.parent_to_bone(obj, arm, scene.bone_name(part, 'L' if side == 'L' else 'R'), world)
	return [obj]


def new_mesh(collection, part):
	"""A starter mesh for a part: the template's cuboid, no export path yet."""
	mesh = scene.mesh_from_obj(template.obj_path(part), f'{collection.name}_{part}')
	return mesh


def use_object_mesh(row, obj):
	"""Give a row `obj`'s mesh (shared, not copied). Returns a note, or None.

	Only the mesh comes across: the object's own transform and modifiers
	don't, so the note says so when it has any.
	"""
	from .repair import _is_identity, _own_matrix

	row.mesh = obj.data
	left_behind = []
	if not _is_identity(_own_matrix(obj)):
		left_behind.append("location, rotation or scale")
	if any(m.show_viewport for m in obj.modifiers):
		left_behind.append("modifiers")
	if left_behind and obj.ballistica_part.role == 'NONE':
		return (f"Took {obj.name}'s mesh, but not its {' and '.join(left_behind)}. "
			f"If it looks wrong, apply them on {obj.name} first (Ctrl+A)")
	return None


def copy_mesh(mesh, name):
	"""A copy of a mesh with its own (empty) export path."""
	from .props import ASSET_PATH_KEY

	copy = mesh.copy()
	copy.name = name
	for key in (ASSET_PATH_KEY, attach_scene.ROOT_KEY, scene.SIGNATURE_KEY):
		if key in copy:
			del copy[key]
	return copy


def on_row_changed(row, turned_on=False):
	"""props hook: a row's checkbox or mesh changed.

	Turning a row on that has no mesh yet gives it one: a copy of the right
	side for a Left row, a box for an optional part.
	"""
	global _quiet
	if _quiet:
		return
	collection = row.id_data
	if not isinstance(collection, bpy.types.Collection) or not collection.ballistica_character.is_character:
		return
	settings = collection.ballistica_character
	if turned_on and row.mesh is None:
		_quiet = True
		try:
			if row.side == 'L':
				right, _ = rows(settings, row.part)
				if right is not None and right.mesh is not None:
					row.mesh = copy_mesh(right.mesh, f'{collection.name}_left_{row.part}')
			elif row.part in template.CUBOIDS:
				row.mesh = new_mesh(collection, row.part)
		finally:
			_quiet = False
	update_part(collection, row.part)


# ---- export paths and fields ----

def default_path(collection, row):
	name = collection.name.split('.')[0]
	return f'meshes/{name}_left_{row.part}' if row.side == 'L' else f'meshes/{name}_{row.part}'


def fields(collection):
	"""{.bchar mesh field: logical path} as export will write them.

	Meshes without an export path get the one export would give them.
	A row without a mesh keeps the field as loaded.
	"""
	settings = collection.ballistica_character
	out = {}
	if not has_rows(settings):
		return out
	for row in settings.parts:
		if not row.enabled:
			out[field(row)] = ''
		elif row.mesh is not None:
			out[field(row)] = row.mesh.ballistica_asset.path or _free_path(collection, row)
	return out


def _free_path(collection, row):
	"""The default path for a row's mesh, made unique among loaded meshes."""
	base = default_path(collection, row)
	taken = {m.ballistica_asset.path for m in bpy.data.meshes if m != row.mesh}
	path, n = base, 2
	while path in taken:
		path, n = f'{base}_{n}', n + 1
	return path


def assign_paths(collection):
	"""Give meshes without an export path theirs, and write the mesh fields."""
	settings = collection.ballistica_character
	for row in settings.parts:
		if row.enabled and row.mesh is not None and not row.mesh.ballistica_asset.path:
			row.mesh.ballistica_asset.path = _free_path(collection, row)
	for name, value in fields(collection).items():
		setattr(settings, name, value)


# ---- selection follows the list, and the list follows selection ----

_following = False


def objects_of(collection, row):
	right, left = _objects(collection, row.part)
	return left if row.side == 'L' else right


def select_row(collection, index):
	"""props hook: a Parts row was clicked; select its object."""
	global _following
	context = bpy.context
	settings = collection.ballistica_character
	if _following or _quiet or context.mode != 'OBJECT' or context.view_layer is None:
		return
	if not 0 <= index < len(settings.parts):
		return
	view_layer = context.view_layer
	objects = [o for o in objects_of(collection, settings.parts[index]) if o.name in view_layer.objects and o.visible_get()]
	if not objects:
		return
	_following = True
	try:
		for obj in view_layer.objects.selected:
			obj.select_set(False)
		for obj in objects:
			obj.select_set(True)
		view_layer.objects.active = objects[0]
	finally:
		_following = False


def follow(collection, obj):
	"""An object became active: pick its row in the Parts list."""
	global _following
	if _following:
		return
	settings = collection.ballistica_character
	role, side = obj.ballistica_part.role, obj.ballistica_part.side
	for index, row in enumerate(settings.parts):
		if row.part == role and (row.side == 'L') == (side == 'L'):
			if settings.active_part_index != index:
				_following = True
				try:
					settings.active_part_index = index
				finally:
					_following = False
			return


from . import props as _props  # noqa: E402

_props.ATTACHMENT_REBUILD_HOOKS['part'] = on_row_changed
_props.ATTACHMENT_REBUILD_HOOKS['select_part'] = select_row
