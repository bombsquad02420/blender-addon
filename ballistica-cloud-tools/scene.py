"""Building a character in the Blender scene, and reading it back.

Mesh data is stored in Blender axes but in each part's own local space, so
export only has to convert axes. Objects are bone-parented to an armature
built in the rest pose; posing the armature never changes exported meshes.
"""

import hashlib
import math
from array import array

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from . import objfile, pose, rig, transforms, workspace

# Game -> Blender axes: (x, y, z) -> (x, -z, y).
TO_BLENDER = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
TO_GAME = TO_BLENDER.transposed()
MIRROR_X = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))

ARMATURE_SUFFIX = "_rig"
GUIDES_SUFFIX = " Guides"
# Child collections the character's objects are sorted into, in outliner
# order. Part -> group for the body part meshes.
GROUPS = ('Rig', 'Head', 'Body', 'Arms', 'Legs', 'Attachments', 'Eyes')
PART_GROUPS = {
	'head': 'Head',
	'torso': 'Body', 'pelvis': 'Body',
	'upper_arm': 'Arms', 'forearm': 'Arms', 'hand': 'Arms',
	'upper_leg': 'Legs', 'lower_leg': 'Legs', 'toes': 'Legs',
}


# Groups hidden in the viewport on import (like Guides); toggle them on in
# the N panel or the outliner.
HIDDEN_GROUPS = ('Rig', 'Eyes')


def make_groups(collection):
	"""Create the character's child collections; return name -> collection."""
	groups = {}
	for group in GROUPS:
		child = bpy.data.collections.new(f'{collection.name} {group}')
		collection.children.link(child)
		groups[group] = child
		if group in HIDDEN_GROUPS:
			for layer in _layer_collections(bpy.context.view_layer.layer_collection, child):
				layer.hide_viewport = True
	return groups
SIDES = (('R', 1.0), ('L', -1.0))

# Bone layout: name -> (head joint, tail joint, parent). Right side only;
# left bones mirror these.
BONES = (
	('pelvis', 'pelvis', 'spine', None),
	('torso', 'spine', 'neck', 'pelvis'),
	('head', 'neck', 'head', 'torso'),
	('shoulder_offset', 'shoulder', 'shoulder_tip', 'torso'),
	('upper_arm', 'shoulder', 'elbow', 'shoulder_offset'),
	('forearm', 'elbow', 'wrist', 'upper_arm'),
	('hand', 'wrist', 'hand_tip', 'forearm'),
	('upper_leg', 'hip', 'knee', 'pelvis'),
	('lower_leg', 'knee', 'ankle', 'upper_leg'),
	('toes', 'ankle', 'toe_tip', 'lower_leg'),
	('wing', 'torso', 'wing_tip', 'torso'),
	('eye_offset', 'head', 'eye_tip', 'head'),
)

# Offset bones: rest at the rig's base point (zero offset); their Pose Mode
# location is driven by the panel's .bchar values (see offset drivers).
# Constraints can be added to these without touching the posing chains.
OFFSET_BONES = ('shoulder_offset', 'eye_offset')
# Bones meant to be posed by moving, not just rotating.
MOVABLE_BONES = ('pelvis',)


# Parts with a bone per side (limbs, plus the wing spots).
SIDED_BONES = (*rig.PAIRED_PARTS, 'wing', *OFFSET_BONES)


def bone_name(part, side):
	return f'{part}.{side}' if part in SIDED_BONES else part


def game_point(v):
	return TO_BLENDER @ Vector(v)


def placement_matrix(placement):
	"""Blender object matrix for a game-space Placement."""
	m = Matrix(placement.rotation).to_4x4()
	m.translation = Vector(placement.location)
	return TO_BLENDER.to_4x4() @ m @ TO_GAME.to_4x4()


def transform_matrix(transform):
	"""Blender-axes matrix for a .bchar {translate, rotate, scale} (game space)."""
	if not transform:
		return Matrix.Identity(4)
	t = Matrix.Translation(game_point(transform.get('translate', (0, 0, 0))))
	r = Euler(transforms.rotate_to_blender_euler(transform.get('rotate', (0, 0, 0))), transforms.EULER_ORDER).to_matrix().to_4x4()
	sx, sy, sz = transform.get('scale', (1, 1, 1))
	s = Matrix.Diagonal((sx, sz, sy, 1.0))  # game (x, y, z) scale -> Blender (x, z, y)
	return t @ r @ s


# ---- meshes ----

def mesh_from_obj(path, name):
	"""A Blender mesh (Blender axes, part-local) from a workspace OBJ."""
	obj = objfile.read(path)
	mesh = bpy.data.meshes.new(name)
	positions = [tuple(game_point(p)) for p in obj.positions]
	mesh.from_pydata(positions, [], [[c[0] for c in face] for face in obj.faces])
	if obj.uvs:
		uv_layer = mesh.uv_layers.new(name="UVMap")
		loop = 0
		for face in obj.faces:
			for _, ti, _ in face:
				uv_layer.data[loop].uv = obj.uvs[ti] if ti is not None else (0.0, 0.0)
				loop += 1
	if obj.normals:
		normals = []
		for face in obj.faces:
			for _, _, ni in face:
				normals.append(tuple(game_point(obj.normals[ni])) if ni is not None else (0.0, 0.0, 0.0))
		mesh.normals_split_custom_set(normals)
	mesh.validate()
	mesh.update()
	mesh[SIGNATURE_KEY] = mesh_signature(mesh)
	return mesh


SIGNATURE_KEY = 'bct_signature'


def mesh_signature(mesh):
	"""Fingerprint of what export writes (positions, UVs, normals, faces)."""
	digest = hashlib.sha1()
	for collection, attr, size in (
		(mesh.vertices, 'co', 3),
		(mesh.loops, 'vertex_index', 1),
		(mesh.corner_normals if hasattr(mesh, 'corner_normals') else mesh.loops, 'vector' if hasattr(mesh, 'corner_normals') else 'normal', 3),
	):
		values = array('f' if attr != 'vertex_index' else 'i', [0]) * (len(collection) * size)
		collection.foreach_get(attr, values)
		digest.update(values.tobytes())
	uv_layer = mesh.uv_layers.active
	if uv_layer is not None:
		values = array('f', [0.0]) * (len(uv_layer.data) * 2)
		uv_layer.data.foreach_get('uv', values)
		digest.update(values.tobytes())
	return digest.hexdigest()


def obj_from_mesh(mesh):
	"""An ObjMesh (game axes) from a Blender mesh's own local data."""
	tmp = bmesh.new()
	tmp.from_mesh(mesh)
	bmesh.ops.triangulate(tmp, faces=tmp.faces[:])
	triangulated = bpy.data.meshes.new('_bct_export')
	tmp.to_mesh(triangulated)
	tmp.free()
	try:
		uv_layer = triangulated.uv_layers.active
		out = objfile.ObjMesh()
		out.positions = [tuple(TO_GAME @ v.co) for v in triangulated.vertices]
		for poly in triangulated.polygons:
			face = []
			for li in poly.loop_indices:
				loop = triangulated.loops[li]
				ti = None
				if uv_layer is not None:
					ti = len(out.uvs)
					out.uvs.append(tuple(uv_layer.data[li].uv))
				out.normals.append(tuple(TO_GAME @ loop.normal))
				face.append((loop.vertex_index, ti, len(out.normals) - 1))
			out.faces.append(tuple(face))
		return out
	finally:
		bpy.data.meshes.remove(triangulated)


# ---- armature ----

ROOT_SUFFIX = "_root"


def build_root(collection, arm):
	"""A flat circle at the feet, parent of the armature.

	Lives in the character's own collection (not Rig), so the whole
	character can be moved while the Rig collection is hidden. It's a curve
	drawn in the ground (XY) plane rather than a circle empty, which Blender
	draws standing up (XZ): the root needs no rotation, so clearing its
	transforms (Alt+G/R/S) puts the character back upright at the origin.
	"""
	radius = rig.ROLLER_RADIUS * 1.5
	curve = bpy.data.curves.new(collection.name + ROOT_SUFFIX, 'CURVE')
	curve.dimensions = '2D'
	spline = curve.splines.new('POLY')
	segments = 32
	spline.points.add(segments - 1)
	for i, point in enumerate(spline.points):
		angle = 2 * math.pi * i / segments
		point.co = (radius * math.cos(angle), radius * math.sin(angle), 0.0, 1.0)
	spline.use_cyclic_u = True
	root = bpy.data.objects.new(collection.name + ROOT_SUFFIX, curve)
	root.hide_render = True
	root.ballistica_part.role = 'NONE'
	collection.objects.link(root)
	arm.parent = root
	return root


def build_armature(collection, joints):
	"""(`collection` is where the armature object is linked: the Rig group.)"""
	"""Rest-pose armature, built at zero shoulder and eye offsets.

	Chains are connected so posing keeps them joined. The offset bones
	start at the rig's base points; drivers move them by the .bchar
	offsets, carrying the arms and eyes along.
	"""
	data = bpy.data.armatures.new(collection.name + ARMATURE_SUFFIX)
	data.display_type = 'STICK'
	arm = bpy.data.objects.new(collection.name + ARMATURE_SUFFIX, data)
	collection.objects.link(arm)
	arm.show_in_front = True
	arm.ballistica_part.role = 'NONE'

	points = dict(joints)
	points['shoulder_tip'] = tuple(Vector(points['shoulder']) + Vector((0.0, 0.06, 0.0)))  # a short stub up
	points['eye_tip'] = tuple(Vector(points['head']) + Vector((0.0, 0.0, 0.08)))  # looking forward (+Z)

	tails = {}
	with _edit_mode(arm):
		bones = data.edit_bones
		for part, head_joint, tail_joint, parent in BONES:
			sides = SIDES if part in SIDED_BONES else (('C', 1.0),)
			for side, sign in sides:
				name = bone_name(part, side)
				bone = bones.new(name)
				bone.head = game_point(_mirror(points[head_joint], sign))
				bone.tail = game_point(_mirror(points[tail_joint], sign))
				bone.roll = 0.0
				tails[name] = tail_joint
				if parent:
					parent_name = bone_name(parent, side)
					bone.parent = bones[parent_name]
					# Offset bones must stay free: connected bones ignore location.
					bone.use_connect = tails[parent_name] == head_joint and part not in OFFSET_BONES
	for bone in arm.pose.bones:
		if bone.name not in MOVABLE_BONES:
			bone.lock_location = (True, True, True)
	return arm


def _mirror(point, sign):
	return point if sign > 0 else pose.mirror(point)


class _edit_mode:
	def __init__(self, obj):
		self.obj = obj

	def __enter__(self):
		view_layer = bpy.context.view_layer
		self.previous = view_layer.objects.active
		view_layer.objects.active = self.obj
		bpy.ops.object.mode_set(mode='EDIT')

	def __exit__(self, *exc):
		bpy.ops.object.mode_set(mode='OBJECT')
		bpy.context.view_layer.objects.active = self.previous


def parent_to_bone(obj, arm, bone, world_matrix):
	"""Bone-parent `obj` so it sits at `world_matrix` with an identity transform.

	The rest placement goes into the parent inverse, leaving the object's
	own location/rotation/scale at zero. Moving a part to get at it is then
	undone by Alt+G/R/S (or Reset Parts), and export never reads transforms.
	"""
	obj.parent = arm
	obj.parent_type = 'BONE'
	obj.parent_bone = bone
	bpy.context.view_layer.update()
	obj.matrix_world = world_matrix
	# world = bone @ parent_inverse @ basis: move the basis into the inverse.
	obj.matrix_parent_inverse = obj.matrix_basis.copy()
	obj.matrix_basis = Matrix.Identity(4)


# ---- material ----

# Group input -> collection setting that drives it.
TINT_DRIVERS = (('Highlight 1', 'color'), ('Highlight 2', 'highlight'), ('Highlight 3', 'highlight2'))


def build_material(name, root, texture, mask, collection):
	"""Textures through the bundled "Ballistica Colorize" group.

	The group's Highlight 1/2/3 inputs are driven by the collection's
	color / highlight / highlight2 settings, so the preview follows the
	panel (and keeps working without the addon).
	"""
	from . import nodegroup

	mat = bpy.data.materials.new(name)
	mat.use_nodes = True
	nodes, links = mat.node_tree.nodes, mat.node_tree.links
	nodes.clear()
	out = nodes.new('ShaderNodeOutputMaterial')
	out.location = (300, 0)
	group = nodes.new('ShaderNodeGroup')
	group.node_tree = nodegroup.get()
	group.location = (0, 0)
	group.width = 200
	# The colorized color straight into the output, unlit like the web UI.
	links.new(group.outputs['Color'], out.inputs['Surface'])
	tex = nodes.new('ShaderNodeTexImage')
	tex.image = _image(root, texture, data=False)
	tex.location = (-350, 150)
	links.new(tex.outputs['Color'], group.inputs['Color'])
	mask_node = nodes.new('ShaderNodeTexImage')
	mask_node.image = _image(root, mask, data=True)
	mask_node.location = (-350, -150)
	links.new(mask_node.outputs['Color'], group.inputs['Color Mask'])
	for socket_name, field in TINT_DRIVERS:
		drive_color(group.inputs[socket_name], collection, f'ballistica_character.{field}')
	return mat


def drive_color(socket, collection, data_path):
	"""Drive an RGBA socket's RGB from a collection's 3-float property."""
	for index in range(3):
		fcurve = socket.driver_add('default_value', index)
		driver = fcurve.driver
		driver.type = 'AVERAGE'
		var = driver.variables[0] if driver.variables else driver.variables.new()
		var.name = 'value'
		var.type = 'SINGLE_PROP'
		var.targets[0].id_type = 'COLLECTION'
		var.targets[0].id = collection
		var.targets[0].data_path = f'{data_path}[{index}]'


def _image(root, logical, data):
	path = workspace.file_path(root, logical, 'texture') if logical else None
	if path is None:
		return None
	image = bpy.data.images.load(path, check_existing=True)
	if data:
		image.colorspace_settings.name = 'Non-Color'
	return image


# ---- guides ----

def build_guides(collection, arm, placements, joints, settings):
	guides = bpy.data.collections.new(collection.name + GUIDES_SUFFIX)
	collection.children.link(guides)
	guides.hide_render = True
	# Hidden in the viewport until toggled on in the outliner.
	for layer in _layer_collections(bpy.context.view_layer.layer_collection, guides):
		layer.hide_viewport = True
	# Per-character sizes are built at their defaults and scaled by drivers
	# (see GUIDE_SCALE_DRIVERS), so the panel resizes them live.
	thigh, ankle = rig.DEFAULTS['thigh_radius'], rig.DEFAULTS['ankle_radius']
	shapes = [
		('head', 'C', _sphere(rig.HEAD_RADIUS)),
		('torso', 'C', _sphere(rig.DEFAULTS['torso_radius'])),
		('pelvis', 'C', _box(rig.PELVIS_SIZE)),
	]
	limbs = [
		('upper_arm', _capsule(rig.UPPER_ARM_RADIUS, rig.UPPER_ARM_LENGTH)),
		('forearm', _capsule(rig.LOWER_ARM_RADIUS, rig.LOWER_ARM_LENGTH)),
		('upper_leg', _capsule(thigh, rig.UPPER_LEG_LENGTH)),
		('lower_leg', _capsule(ankle, rig.LOWER_LEG_SPAN - 2 * ankle)),
		('toes', _sphere(rig.TOES_RADIUS)),
	]
	for part, mesh in limbs:
		for side, _ in SIDES:
			shapes.append((part, side, mesh))
	for part, side, mesh in shapes:
		obj = bpy.data.objects.new(f'guide_{bone_name(part, side)}', mesh)
		guides.objects.link(obj)
		obj.display_type = 'WIRE'
		obj.hide_render = True
		obj.hide_select = True
		obj.ballistica_part.role = 'guide'
		world = placement_matrix(placements[part])
		if side == 'L':
			world = MIRROR_X @ world
		parent_to_bone(obj, arm, bone_name(part, side), world)
		for axis, expression, field in GUIDE_SCALE_DRIVERS.get(part, ()):
			drive_value(obj, 'scale', axis, collection, field, expression)
	roller = bpy.data.objects.new('guide_roller', _sphere(rig.ROLLER_RADIUS))
	guides.objects.link(roller)
	roller.display_type = 'WIRE'
	roller.hide_select = True
	roller.ballistica_part.role = 'guide'
	parent_to_bone(roller, arm, 'pelvis', Matrix.Translation(game_point(joints['roller'])))
	return guides


# Guide part -> (object scale axis, expression of `v`, setting). Capsules lie
# along their local Y; X and Z are their radius. A capsule's full length is
# its length plus both round caps; scaling unevenly makes the caps a little
# oval, which is fine for a guide.
_THIGH, _ANKLE = rig.DEFAULTS['thigh_radius'], rig.DEFAULTS['ankle_radius']
_THIGH_SPAN = rig.UPPER_LEG_LENGTH + 2 * _THIGH
GUIDE_SCALE_DRIVERS = {
	'torso': [(i, f"v/{rig.DEFAULTS['torso_radius']}", 'torso_radius') for i in range(3)],
	'upper_leg': [
		(0, f'v/{_THIGH}', 'thigh_radius'),
		(2, f'v/{_THIGH}', 'thigh_radius'),
		(1, f'({rig.UPPER_LEG_LENGTH} + 2*v)/{_THIGH_SPAN}', 'thigh_radius'),
	],
	# The lower leg's whole span is fixed; only its thickness changes.
	'lower_leg': [(0, f'v/{_ANKLE}', 'ankle_radius'), (2, f'v/{_ANKLE}', 'ankle_radius')],
}


def drive_value(obj, path, index, collection, field, expression):
	"""Drive obj.path[index] by `expression` of a collection setting `v`."""
	driver = obj.driver_add(path, index).driver
	driver.type = 'SCRIPTED'
	var = driver.variables.new()
	var.name = 'v'
	var.type = 'SINGLE_PROP'
	var.targets[0].id_type = 'COLLECTION'
	var.targets[0].id = collection
	var.targets[0].data_path = f'ballistica_character.{field}'
	driver.expression = expression


def _layer_collections(layer, collection):
	if layer.collection == collection:
		yield layer
	for child in layer.children:
		yield from _layer_collections(child, collection)


def _bm_mesh(name, build):
	bm = bmesh.new()
	build(bm)
	mesh = bpy.data.meshes.new(name)
	bm.to_mesh(mesh)
	bm.free()
	return mesh


def _sphere(radius):
	return _bm_mesh('guide_sphere', lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=radius))


def _box(size):
	def build(bm):
		bmesh.ops.create_cube(bm, size=1.0)
		# Game (w, h, d) -> Blender (x, y, z) = (w, d, h).
		bmesh.ops.scale(bm, vec=(size[0], size[2], size[1]), verts=bm.verts)
	return _bm_mesh('guide_box', build)


def _capsule(radius, length):
	"""A capsule along the part's own +Z (game), i.e. Blender -Y."""
	def build(bm):
		bmesh.ops.create_cone(bm, cap_ends=False, segments=12, radius1=radius, radius2=radius, depth=length)
		for end in (-0.5, 0.5):
			geom = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=radius)
			bmesh.ops.translate(bm, vec=(0, 0, end * length), verts=geom['verts'])
		bmesh.ops.rotate(bm, matrix=Matrix.Rotation(math.radians(90), 3, 'X'), verts=bm.verts)
	return _bm_mesh('guide_capsule', build)


# ---- eyes ----

# Game rotation about +X by -eyeball_pitch (nose down), in Blender axes.
EYEBALL_PITCH = (TO_BLENDER @ Matrix.Rotation(math.radians(-rig.EYEBALL_PITCH), 3, 'X') @ TO_GAME).to_4x4()


def build_eyes(collection, arm, placements, settings, target):
	"""The game's eyes (bundled meshes), linked into `target`.

	Per side: an eyeball (ball + iris) on its eye_offset bone, and an
	eyelid as its child. Drivers read `collection`: eye_scale sizes them,
	the eye style hides them (eyeball for None, eyelid unless Regular, as
	DrawEyeLids does at rest) and eyelid_angle turns the lid about the
	forward axis. The -X (left) eye is the right one mirrored; as the
	lid's parent it also mirrors the lid, so one rotation driver serves
	both sides (the engine negates the angle and mirrors the left lid).
	"""
	from . import nodegroup

	ball_mesh, lid_mesh = nodegroup.get_data('meshes', nodegroup.EYE_MESHES)
	texture, mask = nodegroup.get_data('images', nodegroup.EYE_IMAGES)
	name = collection.name
	eye_material = build_eye_material(f'{name}_eye', collection, texture, mask, 'eye_color', 'eyeball_color')
	lid_material = build_eye_material(f'{name}_eyelid', collection, texture, None, None, 'eyelid_color')
	head = placements['head']
	none = rig.EYE_STYLES.index('none')
	regular = rig.EYE_STYLES.index('regular')
	eyes = []
	for side, field in (('R', 'eye_style_right'), ('L', 'eye_style_left')):
		eye = _eye_object(f'eye.{side}', ball_mesh, eye_material, side, target)
		# The eyeball rests pitched (rig eyeball_pitch: looking slightly down);
		# the lid doesn't, so it undoes the pitch below.
		parent_to_bone(eye, arm, f'eye_offset.{side}', Matrix.Translation(game_point(head.location)) @ EYEBALL_PITCH)
		for axis in range(3):
			drive_value(eye, 'scale', axis, collection, 'eye_scale', '-v' if side == 'L' and axis == 0 else 'v')
		for path in ('hide_viewport', 'hide_render'):
			drive_value(eye, path, -1, collection, field, f'v == {none}')

		lid = _eye_object(f'eyelid.{side}', lid_mesh, lid_material, side, target)
		lid.parent = eye
		lid.matrix_parent_inverse = EYEBALL_PITCH.inverted()
		# Game rotation about the forward axis (+Z) is Blender's -Y.
		drive_value(lid, 'rotation_euler', 1, collection, 'eyelid_angle', '-radians(v)')
		for path in ('hide_viewport', 'hide_render'):
			drive_value(lid, path, -1, collection, field, f'v != {regular}')
		eyes += [eye, lid]
	return eyes


def _eye_object(name, mesh, material, side, target):
	obj = bpy.data.objects.new(name, mesh)
	target.objects.link(obj)
	obj.ballistica_part.role = 'eye'
	obj.ballistica_part.side = side
	# The meshes are shared between characters; materials are per object.
	obj.material_slots[0].link = 'OBJECT'
	obj.material_slots[0].material = material
	return obj


def build_eye_material(name, collection, texture, mask, iris_field, base_field):
	"""Eye texture through the bundled "Ballistica Eye" group, colors driven."""
	from . import nodegroup

	mat = bpy.data.materials.new(name)
	mat.use_nodes = True
	nodes, links = mat.node_tree.nodes, mat.node_tree.links
	nodes.clear()
	out = nodes.new('ShaderNodeOutputMaterial')
	out.location = (300, 0)
	group = nodes.new('ShaderNodeGroup')
	group.node_tree = nodegroup.get(nodegroup.EYE_GROUP_NAME)
	group.width = 200
	links.new(group.outputs['Color'], out.inputs['Surface'])
	tex = nodes.new('ShaderNodeTexImage')
	tex.image = texture
	tex.location = (-350, 150)
	links.new(tex.outputs['Color'], group.inputs['Color'])
	if mask is not None:
		mask_node = nodes.new('ShaderNodeTexImage')
		mask_node.image = mask
		mask_node.location = (-350, -150)
		links.new(mask_node.outputs['Color'], group.inputs['Tint Mask'])
	if iris_field:
		drive_color(group.inputs['Iris Color'], collection, f'ballistica_character.{iris_field}')
	drive_color(group.inputs['Base Color'], collection, f'ballistica_character.{base_field}')
	return mat


# ---- attachments ----

LIMB_TARGETS = ('upper_arm', 'forearm', 'hand', 'upper_leg', 'lower_leg', 'toes', 'wing')


def build_attachments(into, arm, placements, attachments, root, material_for):
	"""Attachment segment meshes, linked into the `into` collection."""
	"""Place attachment segment meshes on their target parts (rest pose).

	A first segment hangs from the attachment's spot (its transform on the
	target body); each later one from the segment before, via the kind's
	joint anchors. A segment's own transform places its art on its body.
	Static attachments have no bodies: art goes straight on the spot.
	"""
	objects = []
	for index, attachment in enumerate(attachments):
		target = attachment.get('target', 'head')
		kind = attachment.get('kind', 'static')
		side = attachment.get('side', 'both')
		body_part = target
		if target in LIMB_TARGETS:
			sides = [s for s, _ in SIDES if side == 'both' or (side, s) in (('right', 'R'), ('left', 'L'))]
		else:
			sides = ['C']
		spot = placement_matrix(placements[body_part]) @ transform_matrix(attachment.get('transform'))
		anchors = rig.ATTACHMENT_ANCHORS.get(kind, ())
		for side_name in sides:
			body = spot
			for seg_index, segment in enumerate(attachment.get('segments', [])):
				if kind != 'static' and seg_index < len(anchors):
					parent_anchor, child_anchor = anchors[seg_index]
					if seg_index > 0:
						body = body @ Matrix.Translation(game_point(parent_anchor))
					body = body @ Matrix.Translation(-game_point(child_anchor))
				world = body @ transform_matrix(segment.get('transform'))
				if side_name == 'L':
					world = MIRROR_X @ world
				path = workspace.file_path(root, segment.get('mesh', ''), 'mesh')
				if path is None:
					continue
				name = f"attachment{index}.{seg_index}" + (f".{side_name}" if side_name != 'C' else '')
				obj = bpy.data.objects.new(name, mesh_from_obj(path, segment['mesh']))
				into.objects.link(obj)
				obj.ballistica_part.role = 'attachment'
				obj.data.materials.append(material_for(segment))
				parent_to_bone(obj, arm, bone_name(body_part, 'R' if side_name == 'C' else side_name), world)
				objects.append(obj)
	return objects


# ---- offset drivers ----

# Bone -> (collection setting, mirrored, scaled by). Mirrored bones use the
# value with x negated. The shoulder value is the right arm's (-X). The
# engine draws the eye at +eye_offset.x with eye_style_right and the one at
# -x with eye_style_left (spaz_node.cc DrawEyeBalls), and scales the eye
# offset by eye_scale (it scales about the head centre before moving out).
OFFSET_DRIVERS = (
	('shoulder_offset.R', 'shoulder_offset', False, None),
	('shoulder_offset.L', 'shoulder_offset', True, None),
	('eye_offset.R', 'eye_offset', False, 'eye_scale'),
	('eye_offset.L', 'eye_offset', True, 'eye_scale'),
)


def setup_offset_drivers(collection, arm):
	"""Drive each offset bone's Pose Mode location from the panel value.

	A pose bone's location is in its own rest frame, so each component is a
	fixed linear map of the game-space value: simple driver expressions,
	no Python scripts needed.
	"""
	for bone, field, mirrored, scaled_by in OFFSET_DRIVERS:
		to_local = arm.data.bones[bone].matrix_local.to_3x3().inverted() @ TO_BLENDER
		if mirrored:
			to_local = to_local @ Matrix.Diagonal((-1.0, 1.0, 1.0))
		pose_bone = arm.pose.bones[bone]
		pose_bone.lock_location = (False, False, False)
		for i in range(3):
			driver = pose_bone.driver_add('location', i).driver
			driver.type = 'SCRIPTED'
			terms = []
			for j in range(3):
				var = driver.variables.new()
				var.name = 'xyz'[j]
				var.type = 'SINGLE_PROP'
				var.targets[0].id_type = 'COLLECTION'
				var.targets[0].id = collection
				var.targets[0].data_path = f'ballistica_character.{field}[{j}]'
				if abs(to_local[i][j]) > 1e-9:
					terms.append(f'{to_local[i][j]:.6f}*{var.name}')
			expression = ' + '.join(terms) or '0'
			if scaled_by:
				var = driver.variables.new()
				var.name = 's'
				var.type = 'SINGLE_PROP'
				var.targets[0].id_type = 'COLLECTION'
				var.targets[0].id = collection
				var.targets[0].data_path = f'ballistica_character.{scaled_by}'
				expression = f's*({expression})'
			driver.expression = expression


# ---- exploded view ----


def setup_spread_drivers(collection):
	"""Drive each bone-parented object's delta location by the Spread slider.

	Offsets are the web UI's per-part spread (pose.SPREAD), mirrored for
	left-side bones; eyes and head attachments follow the head, and the
	roller the pelvis (its parent). delta_location is applied in the
	object's rest frame (its parent inverse), so the world offset is mapped
	into that frame once here; location stays free for moving parts.
	"""
	for obj in collection.all_objects:
		if obj.parent_type != 'BONE' or not obj.parent_bone:
			continue
		part, _, side = obj.parent_bone.partition('.')
		part = 'head' if part == 'eye_offset' else part
		offset = pose.SPREAD.get(part)
		if offset is None or not any(offset):
			continue
		if side == 'L':
			offset = pose.mirror(offset)
		rest = (obj.matrix_world @ obj.matrix_basis.inverted()).to_3x3()
		local = rest.inverted() @ game_point(offset)
		for i in range(3):
			if abs(local[i]) > 1e-9:
				drive_value(obj, 'delta_location', i, collection, 'spread', f'{local[i]:.6f}*v')
