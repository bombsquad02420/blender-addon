"""Finding and fixing what drifted in a character's scene.

Nothing in the scene is locked hard: moving a part aside to model, paint or
unwrap it is useful. But export only reads meshes and settings, so some
changes silently don't reach the game (a part moved in Object Mode), and
some break the scene (a deleted rig). `issues()` lists them in plain words,
and `fix()` repairs one; `repair()` fixes everything it can. Repair never
touches the pose (that's Reset to T-Pose), mesh shapes or paint, except
**Keep**, which applies an Object Mode move to the mesh so it's exported.
"""

import bpy
from mathutils import Matrix

from . import attach_scene, pose, rig, scene

PART_ROLES = tuple(p for p, _, _ in rig.PARTS)

# Issue kinds. Object-level ones name an object; the rest are the character's.
MOVED = 'moved'  # own transform isn't identity (export ignores it)
DETACHED = 'detached'  # not on its bone (or handle) any more
HIDDEN = 'hidden'  # hidden with H
MATERIAL = 'material'  # not the character's material: preview won't match
ANCHOR_SCALED = 'anchor_scaled'  # .bchar can't store an anchor's scale
NO_RIG = 'no_rig'
RIG_MOVED = 'rig_moved'  # bones moved (or deleted) in Edit Mode
NO_ROOT = 'no_root'
NO_GROUP = 'no_group'  # a child collection was deleted
NO_EYES = 'no_eyes'
NO_GUIDES = 'no_guides'
NO_ATTACHMENTS = 'no_attachments'  # an attachment's handles or meshes are gone
NO_PART = 'no_part'  # a part with a mesh has no object

# Kind -> (short label, fix button, longer explanation for the tooltip).
TEXT = {
	MOVED: ("{name} moved", "Put Back",
		"{name} was moved, turned or scaled in Object Mode. The game only uses its spot on the rig, "
		"so this isn't exported. Put Back returns it; Keep applies the change to its mesh so it is"),
	DETACHED: ("{name} came off the rig", "Reattach", "{name} isn't attached to its bone any more"),
	HIDDEN: ("{name} is hidden", "Show", "{name} was hidden (H). It's still exported; Show brings it back"),
	MATERIAL: ("{name} has another material", "Fix",
		"{name} doesn't use the character's material, so the preview won't match the game "
		"(export only uses the character's textures)"),
	ANCHOR_SCALED: ("{name} is scaled", "Fix",
		"The anchor {name} is scaled, but attachments can't be scaled in the game. "
		"Scale a segment's Art Offset handle instead"),
	NO_RIG: ("Rig missing", "Rebuild", "The character's rig was deleted. Rebuild puts a new one at the game's joints"),
	RIG_MOVED: ("Rig bones moved", "Put Back",
		"Bones were moved or deleted in Edit Mode, but the game's skeleton can't change. Put Back restores them"),
	NO_ROOT: ("Root missing", "Rebuild", "The circle that moves the whole character was deleted"),
	NO_GROUP: ("{name} collection missing", "Rebuild", "A collection the character's objects are sorted into was deleted"),
	NO_EYES: ("Eyes missing", "Rebuild", "The eye preview objects were deleted"),
	NO_GUIDES: ("Guides missing", "Rebuild", "The physics guides were deleted"),
	NO_ATTACHMENTS: ("Attachment {name} incomplete", "Rebuild", "Attachment {name}'s handles or meshes were deleted"),
	NO_PART: ("{name} missing", "Rebuild", "The {name} object was deleted, but the character still uses its mesh"),
}
# Kinds whose fix can instead keep the change (apply it to the mesh).
KEEPABLE = (MOVED,)


class Issue:
	def __init__(self, kind, name='', obj=None):
		self.kind = kind
		self.name = name or (obj.name if obj is not None else '')
		self.obj = obj

	@property
	def label(self):
		return TEXT[self.kind][0].format(name=self.name)

	@property
	def button(self):
		return TEXT[self.kind][1]

	@property
	def explanation(self):
		return TEXT[self.kind][2].format(name=self.name) + '.'

	@property
	def keepable(self):
		return self.kind in KEEPABLE and self.obj is not None and self.obj.type == 'MESH' and self.obj.ballistica_part.role != 'eye'

	def __repr__(self):
		return f'Issue({self.kind}, {self.name})'


_REST = {}


def _rest():
	"""(placements, joints) of the rest pose (fixed; computed once)."""
	if not _REST:
		_REST['placements'], _REST['joints'] = pose.compute()
	return _REST['placements'], _REST['joints']


def armature(collection):
	return next((o for o in collection.all_objects if o.type == 'ARMATURE'), None)


def root_object(collection):
	return collection.objects.get(collection.name + scene.ROOT_SUFFIX) or next(
		(o for o in collection.objects if o.type == 'CURVE' and o.name.startswith(collection.name + scene.ROOT_SUFFIX)), None)


def body_material(collection):
	"""The character's body material: textures through the Colorize group."""
	settings = collection.ballistica_character
	if settings.body_material is not None:
		return settings.body_material
	return bpy.data.materials.get(collection.name)


# ---- what an object should be ----

def _expected_parent(collection, obj, arm):
	"""(parent object, bone name or '', parent inverse) for a placed object, or None."""
	placements, joints = _rest()
	role = obj.ballistica_part.role
	side = obj.ballistica_part.side
	if role in PART_ROLES:
		world = scene.placement_matrix(placements[role])
		if side == 'L':
			world = scene.MIRROR_X @ world
		bone = scene.bone_name(role, 'L' if side == 'L' else 'R')
		return arm, bone, world
	if role == 'eye' and obj.name.startswith('eye.'):
		world = Matrix.Translation(scene.game_point(placements['head'].location)) @ scene.EYEBALL_PITCH
		return arm, f'eye_offset.{side}', world
	return None


def _own_matrix(obj):
	"""The object's own location/rotation/scale, without delta transforms."""
	if obj.rotation_mode == 'QUATERNION':
		rotation = obj.rotation_quaternion
	elif obj.rotation_mode == 'AXIS_ANGLE':
		angle, *axis = obj.rotation_axis_angle
		rotation = Matrix.Rotation(angle, 4, axis).to_quaternion()
	else:
		rotation = obj.rotation_euler.to_quaternion()
	return Matrix.LocRotScale(obj.location, rotation, obj.scale)


def _is_identity(matrix, tolerance=1e-5):
	identity = Matrix.Identity(4)
	return all(abs(matrix[i][j] - identity[i][j]) <= tolerance for i in range(4) for j in range(4))


def _close(a, b, tolerance=1e-4):
	return all(abs(a[i][j] - b[i][j]) <= tolerance for i in range(4) for j in range(4))


def _moved(obj):
	if obj.ballistica_part.role == 'eye':
		# Eyes are sized by drivers; only a move counts.
		return obj.location.length > 1e-5
	return not _is_identity(_own_matrix(obj))


def _object_issues(collection, obj, arm, material):
	"""Issues of one body part, eye or attachment object."""
	issues = []
	role = obj.ballistica_part.role
	tag = obj.get(attach_scene.ROLE_KEY)
	if tag == attach_scene.ANCHOR:
		if obj.get(attach_scene.SIDE_KEY) != 'L' and any(abs(s - 1.0) > 1e-5 for s in obj.scale):
			issues.append(Issue(ANCHOR_SCALED, obj=obj))
		return issues
	if tag == attach_scene.HANDLE:
		return issues
	if role not in PART_ROLES and role not in ('eye', 'attachment'):
		return issues
	expected = _expected_parent(collection, obj, arm) if arm is not None else None
	if expected is not None:
		parent, bone, rest = expected
		if (obj.parent != parent or obj.parent_type != 'BONE' or obj.parent_bone != bone
				or bone not in parent.data.bones
				or not _close(obj.matrix_parent_inverse, scene.bone_rest_parent_inverse(parent, bone, rest))):
			issues.append(Issue(DETACHED, obj=obj))
	elif role == 'attachment' and obj.parent is None:
		issues.append(Issue(DETACHED, obj=obj))
	if _moved(obj):
		issues.append(Issue(MOVED, obj=obj))
	if role != 'eye' and (obj.hide_get() or obj.hide_viewport):
		issues.append(Issue(HIDDEN, obj=obj))
	if role in PART_ROLES and material is not None:
		slot = obj.material_slots[0] if obj.material_slots else None
		if slot is None or slot.link != 'OBJECT' or slot.material != material:
			issues.append(Issue(MATERIAL, obj=obj))
	return issues


# ---- the character as a whole ----

def _guides(collection):
	return scene.group(collection, scene.GUIDES_SUFFIX.strip())


def _character_issues(collection, arm):
	issues = []
	for group in scene.GROUPS:
		if scene.group(collection, group) is None:
			issues.append(Issue(NO_GROUP, group))
	if arm is None:
		issues.append(Issue(NO_RIG))
	elif scene.rest_bone_problem(arm, _rest()[1]):
		issues.append(Issue(RIG_MOVED))
	if root_object(collection) is None:
		issues.append(Issue(NO_ROOT))
	objects = list(collection.all_objects)
	if not any(o.ballistica_part.role == 'eye' for o in objects):
		issues.append(Issue(NO_EYES))
	guides = _guides(collection)
	if guides is None or not guides.objects:
		issues.append(Issue(NO_GUIDES))
	settings = collection.ballistica_character
	for index, attachment in enumerate(settings.attachments):
		have = attach_scene.tagged(collection, None, index)
		anchors = [o for o in have if o[attach_scene.ROLE_KEY] == attach_scene.ANCHOR]
		handles = [o for o in have if o[attach_scene.ROLE_KEY] == attach_scene.HANDLE]
		meshes = [o for o in have if o[attach_scene.ROLE_KEY] == attach_scene.MESH]
		with_mesh = sum(1 for s in attachment.segments if s.mesh)
		if not anchors or len(handles) < len(anchors) * len(attachment.segments) or (with_mesh and not meshes):
			issues.append(Issue(NO_ATTACHMENTS, str(index + 1)))
	for part, field, _ in rig.PARTS:
		if not getattr(settings, field):
			continue
		have = {o.ballistica_part.side for o in objects if o.ballistica_part.role == part}
		need = {'R', 'L'} if part in rig.PAIRED_PARTS else {'CENTER'}
		for side in sorted(need - have):
			issues.append(Issue(NO_PART, scene.bone_name(part, side) if side != 'CENTER' else part))
	return issues


def issues(collection, objects=None):
	"""Everything that drifted in the character (or just in `objects`)."""
	arm = armature(collection)
	material = body_material(collection)
	found = [] if objects is not None else _character_issues(collection, arm)
	for obj in collection.all_objects if objects is None else objects:
		found += _object_issues(collection, obj, arm, material)
	return found


# ---- fixing ----

def fix(collection, issue, keep=False):
	"""Fix one issue. `keep` applies a move to the mesh instead of undoing it."""
	kind, obj = issue.kind, issue.obj
	if kind == MOVED:
		if keep:
			_apply_to_mesh(obj)
		_clear_own_transform(obj)
	elif kind == DETACHED:
		_reattach(collection, obj)
	elif kind == HIDDEN:
		obj.hide_viewport = False
		obj.hide_set(False)
	elif kind == MATERIAL:
		material = body_material(collection)
		if material is not None:
			scene.assign_material(obj, material)
	elif kind == ANCHOR_SCALED:
		obj.scale = (1.0, 1.0, 1.0)
	elif kind == NO_GROUP:
		_ensure_groups(collection)
	elif kind == NO_ROOT:
		_ensure_root(collection)
	elif kind in (NO_RIG, RIG_MOVED):
		_fix_rig(collection)
	elif kind == NO_EYES:
		_rebuild_eyes(collection)
	elif kind == NO_GUIDES:
		_rebuild_guides(collection)
	elif kind == NO_ATTACHMENTS:
		attach_scene.rebuild(collection)
	elif kind == NO_PART:
		from . import part_scene

		part_scene.update_part(collection, issue.name.partition('.')[0])
	collection.update_tag()


# Character-level fixes run first: they recreate what object fixes need.
ORDER = (NO_GROUP, NO_RIG, RIG_MOVED, NO_ROOT, NO_GUIDES, NO_EYES, NO_ATTACHMENTS, NO_PART)


def repair(collection, objects=None):
	"""Fix every issue (undoing moves rather than keeping them).

	Returns how many were fixed. Character-level fixes go first, then the
	objects are checked again, since rebuilding can fix or change them.
	"""
	fixed = 0
	if objects is None:
		for kind in ORDER:
			pending = [i for i in issues(collection) if i.kind == kind]
			for issue in pending[:1] if kind not in (NO_PART,) else pending:
				fix(collection, issue)
			fixed += len(pending)
	for issue in issues(collection, objects if objects is not None else list(collection.all_objects)):
		try:
			issue.obj.name
		except ReferenceError:
			continue  # removed by an earlier fix (an attachment rebuild)
		fix(collection, issue)
		fixed += 1
	return fixed


TRANSFORM_CHANNELS = ('location', 'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle', 'scale')


def _clear_own_transform(obj):
	obj.location = (0.0, 0.0, 0.0)
	obj.rotation_euler = (0.0, 0.0, 0.0)
	obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
	obj.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
	obj.scale = (1.0, 1.0, 1.0)


def _apply_to_mesh(obj):
	"""Bake the object's own transform into its mesh (shared ones included)."""
	if obj.type != 'MESH':
		return
	matrix = _own_matrix(obj)
	obj.data.transform(matrix)
	if matrix.is_negative:
		obj.data.flip_normals()
	obj.data.update()


def _reattach(collection, obj):
	arm = armature(collection)
	if obj.ballistica_part.role == 'attachment' or arm is None:
		attach_scene.rebuild(collection)
		return
	expected = _expected_parent(collection, obj, arm)
	if expected is not None:
		parent, bone, rest = expected
		# Keep a move (that's its own issue). Saved channel by channel: a
		# driven mirror scale (the left eye) doesn't survive a matrix.
		channels = {k: tuple(getattr(obj, k)) for k in TRANSFORM_CHANNELS}
		scene.parent_to_bone(obj, parent, bone, rest)
		for key, value in channels.items():
			setattr(obj, key, value)


def _ensure_groups(collection):
	"""Recreate missing child collections and sort loose objects back in."""
	groups = {}
	for group in scene.GROUPS:
		child = scene.group(collection, group)
		if child is None:
			child = bpy.data.collections.new(f'{collection.name} {group}')
			collection.children.link(child)
			if group in scene.HIDDEN_GROUPS:
				for layer in scene._layer_collections(bpy.context.view_layer.layer_collection, child):
					layer.hide_viewport = True
		groups[group] = child
	for obj in list(collection.objects):
		group = _group_of(collection, obj)
		if group is not None:
			groups[group].objects.link(obj)
			collection.objects.unlink(obj)


def _group_of(collection, obj):
	if obj.type == 'ARMATURE' or obj.get(attach_scene.ROLE_KEY) in (attach_scene.ANCHOR, attach_scene.HANDLE):
		return 'Rig'
	role = obj.ballistica_part.role
	if role in scene.PART_GROUPS:
		return scene.PART_GROUPS[role]
	return {'attachment': 'Attachments', 'eye': 'Eyes'}.get(role)


def _ensure_root(collection):
	arm = armature(collection)
	if root_object(collection) is None and arm is not None:
		world = arm.matrix_world.copy()
		scene.build_root(collection, arm)
		arm.matrix_world = world


def _fix_rig(collection):
	"""Bones back at the game's joints; a new rig if it's gone or bones are missing."""
	arm = armature(collection)
	joints = _rest()[1]
	problem = scene.rest_bone_problem(arm, joints) if arm is not None else 'missing'
	if problem == 'moved':
		with scene._edit_mode(arm):
			scene.set_rest_bones(arm, joints)
		return
	group = scene.group(collection, 'Rig') or collection
	if arm is not None:
		bpy.data.objects.remove(arm)
	arm = scene.build_armature(group, joints)
	root = root_object(collection)
	if root is None:
		scene.build_root(collection, arm)
	else:
		arm.parent = root
	scene.setup_offset_drivers(collection, arm)
	for obj in list(collection.all_objects):
		if _expected_parent(collection, obj, arm) is not None:
			_reattach(collection, obj)
	eyes = {o.ballistica_part.side: o for o in collection.all_objects if o.ballistica_part.role == 'eye' and o.name.startswith('eye.')}
	for obj in list(collection.all_objects):
		if obj.ballistica_part.role == 'eye' and obj.name.startswith('eyelid.') and obj.parent is None:
			obj.parent = eyes.get(obj.ballistica_part.side)
			obj.matrix_parent_inverse = scene.EYEBALL_PITCH.inverted()
	_rebuild_guides(collection)
	attach_scene.rebuild(collection)


def _rebuild_eyes(collection):
	arm = armature(collection)
	group = scene.group(collection, 'Eyes') or collection
	if arm is None:
		return
	placements, _ = _rest()
	created = scene.build_eyes(collection, arm, placements, collection.ballistica_character, group)
	scene.setup_spread_drivers(collection, created)


def _rebuild_guides(collection):
	arm = armature(collection)
	if arm is None:
		return
	old = _guides(collection)
	if old is not None:
		for obj in list(old.objects):
			bpy.data.objects.remove(obj)
		bpy.data.collections.remove(old)
	placements, joints = _rest()
	guides = scene.build_guides(collection, arm, placements, joints, collection.ballistica_character)
	scene.setup_spread_drivers(collection, list(guides.objects))
