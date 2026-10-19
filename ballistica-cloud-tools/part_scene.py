"""Body part objects following the Meshes fields.

Changing a part's mesh field swaps the mesh its objects show (both sides
of a paired part, unless a left_* override gives the left its own);
clearing an optional part removes its objects, and setting an empty one
creates them on their bones. Meshes are shared by path: two parts using
the same file use the same Blender mesh, as they'd use the same file.
"""

import bpy

from . import attach_scene, pose, rig, scene


def _objects(collection, part):
	right = [o for o in collection.all_objects if o.ballistica_part.role == part and o.ballistica_part.side != 'L']
	left = [o for o in collection.all_objects if o.ballistica_part.role == part and o.ballistica_part.side == 'L']
	return right, left


def _body_material(collection):
	return bpy.data.materials.get(collection.name)


def update_part(collection, part):
	"""Make `part`'s objects match its mesh fields."""
	settings = collection.ballistica_character
	field = dict((p, f) for p, f, _ in rig.PARTS)[part]
	logical = getattr(settings, field)
	right, left = _objects(collection, part)
	if not logical:
		for obj in right + left:
			bpy.data.objects.remove(obj)
		return
	root = settings.workspace_root
	mesh = attach_scene.mesh_for(root, logical)
	if mesh is None:
		print(f"Ballistica: {logical} not found in the workspace; {part} keeps its mesh.")
		return
	_give_material(collection, mesh)
	placements, _ = pose.compute()
	created = []
	side = 'R' if part in rig.PAIRED_PARTS else 'CENTER'
	created += _show(collection, part, side, mesh, right, placements)
	if part in rig.PAIRED_PARTS:
		left_logical = getattr(settings, f'left_{part}_mesh')
		left_mesh = attach_scene.mesh_for(root, left_logical) if left_logical else None
		if left_mesh is not None:
			_give_material(collection, left_mesh)
		created += _show(collection, part, 'L', left_mesh or mesh, left, placements)
	if created:
		scene.setup_spread_drivers(collection, created)


def _give_material(collection, mesh):
	material = _body_material(collection)
	if material is not None and not mesh.materials:
		mesh.materials.append(material)


def _show(collection, part, side, mesh, existing, placements):
	"""Point existing objects at `mesh`, or create the part's object."""
	for obj in existing:
		obj.data = mesh
	if existing:
		return []
	arm = next((o for o in collection.all_objects if o.type == 'ARMATURE'), None)
	group = bpy.data.collections.get(f'{collection.name} {scene.PART_GROUPS[part]}') or collection
	if arm is None:
		return []
	name = f'{part}.{side}' if part in rig.PAIRED_PARTS else part
	obj = bpy.data.objects.new(name, mesh)
	group.objects.link(obj)
	obj.ballistica_part.role = part
	obj.ballistica_part.side = side
	world = scene.placement_matrix(placements[part])
	if side == 'L':
		world = scene.MIRROR_X @ world
	scene.parent_to_bone(obj, arm, scene.bone_name(part, 'L' if side == 'L' else 'R'), world)
	return [obj]


def on_field_changed(settings, field):
	"""props hook: a Meshes (or left_*) field changed."""
	collection = settings.id_data
	if not isinstance(collection, bpy.types.Collection) or not settings.is_character:
		return
	part = field[5:-5] if field.startswith('left_') else field[:-5]
	update_part(collection, part)


from . import props as _props  # noqa: E402

_props.ATTACHMENT_REBUILD_HOOKS['part'] = on_field_changed
