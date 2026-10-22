"""Building a character in the Blender scene, and reading it back.

Mesh data is stored in Blender axes but in each part's own local space, so
export only has to convert axes. Objects are bone-parented to an armature
built in the rest pose; posing the armature never changes exported meshes.
"""

import hashlib
import math
import os
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


def group(collection, name):
	"""The character's child collection for group `name` (e.g. 'Rig'), or None.

	Found among its children by the name's ending, so it survives the
	character collection being renamed.
	"""
	for child in collection.children:
		if child.name == f'{collection.name} {name}' or child.name.endswith(f' {name}') or child.name.rsplit('.', 1)[0].endswith(f' {name}'):
			return child
	return None


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
	('lower_leg', 'knee', 'heel', 'upper_leg'),
	# The ankle sits off the shin's axis (ankle_on_lower_leg); this fixed
	# jog from the heel to it draws the leg like the web UI's pose view.
	('heel', 'heel', 'ankle', 'lower_leg'),
	('toes', 'ankle', 'toe_tip', 'heel'),
	('wing', 'torso', 'wing_tip', 'torso'),
	('eye_offset', 'head', 'eye_tip', 'head'),
)

# Offset bones: rest at the rig's base point (zero offset); their Pose Mode
# location is driven by the panel's .bchar values (see offset drivers).
# Constraints can be added to these without touching the posing chains.
OFFSET_BONES = ('shoulder_offset', 'eye_offset')
# Bones meant to be posed by moving, not just rotating.
MOVABLE_BONES = ('pelvis',)
# Bones that are fixed parts of their body: no rotation either.
RIGID_BONES = ('heel',)


# Parts with a bone per side (limbs, plus the wing spots).
SIDED_BONES = (*rig.PAIRED_PARTS, 'heel', 'wing', *OFFSET_BONES)


def bone_name(part, side):
	return f'{part}.{side}' if part in SIDED_BONES else part


def game_point(v):
	return TO_BLENDER @ Vector(v)


def placement_matrix(placement):
	"""Blender object matrix for a game-space Placement."""
	m = Matrix(placement.rotation).to_4x4()
	m.translation = Vector(placement.location)
	return TO_BLENDER.to_4x4() @ m @ TO_GAME.to_4x4()


# ---- meshes ----

def mesh_from_obj(path, name):
	"""A Blender mesh (Blender axes, part-local) from a workspace OBJ."""
	return mesh_from_objmesh(objfile.read(path), name)


def mesh_from_objmesh(obj, name):
	"""A Blender mesh (Blender axes, part-local) from an in-memory ObjMesh."""
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
	"""Fingerprint of what export writes (positions, UVs, normals, faces).

	Taken of the evaluated mesh (modifiers applied), so changing a modifier
	counts as a change.
	"""
	digest = hashlib.sha1()
	for collection, attr, size in (
		(mesh.vertices, 'co', 3),
		(mesh.loops, 'vertex_index', 1),
		(mesh.corner_normals if hasattr(mesh, 'corner_normals') else mesh.loops, 'vector' if hasattr(mesh, 'corner_normals') else 'normal', 3),
	):
		values = array('f' if attr != 'vertex_index' else 'i', [0]) * (len(collection) * size)
		collection.foreach_get(attr, values)
		digest.update(values.tobytes())
	uv_layer = export_uv_layer(mesh)
	if uv_layer is not None:
		values = array('f', [0.0]) * (len(uv_layer.data) * 2)
		uv_layer.data.foreach_get('uv', values)
		digest.update(values.tobytes())
	return digest.hexdigest()


def export_uv_layer(mesh):
	"""The UV map export writes: the render-active one (Blender's camera icon)."""
	return next((layer for layer in mesh.uv_layers if layer.active_render), mesh.uv_layers.active)


class evaluated_mesh:
	"""The mesh an object exports: its modifiers applied, in its local space.

	Object transforms, bone parents and the armature pose never affect it
	(parts are bone-parented, not armature-deformed). Without modifiers it's
	the object's own mesh; otherwise a temporary mesh removed on exit.
	"""

	def __init__(self, obj):
		self.obj = obj
		self.temporary = None

	def __enter__(self):
		if not any(m.show_viewport for m in self.obj.modifiers):
			return self.obj.data
		depsgraph = bpy.context.evaluated_depsgraph_get()
		self.temporary = bpy.data.meshes.new_from_object(
			self.obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
		return self.temporary

	def __exit__(self, *exc):
		if self.temporary is not None:
			bpy.data.meshes.remove(self.temporary)


def obj_from_mesh(mesh):
	"""An ObjMesh (game axes) from a Blender mesh's own local data."""
	uv_name = export_uv_layer(mesh).name if mesh.uv_layers else None
	tmp = bmesh.new()
	tmp.from_mesh(mesh)
	bmesh.ops.triangulate(tmp, faces=tmp.faces[:])
	triangulated = bpy.data.meshes.new('_bct_export')
	tmp.to_mesh(triangulated)
	tmp.free()
	try:
		uv_layer = triangulated.uv_layers.get(uv_name) if uv_name else None
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
	"""Rest-pose armature, built at zero shoulder and eye offsets.

	`collection` is where the armature object is linked (the Rig group).
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
	with _edit_mode(arm):
		set_rest_bones(arm, joints)
	lock_bones(arm)
	return arm


def rest_bones(joints):
	"""Bone name -> (head, tail, parent, connected), Blender axes, rig space."""
	points = dict(joints)
	points['shoulder_tip'] = tuple(Vector(points['shoulder']) + Vector((0.0, 0.06, 0.0)))  # a short stub up
	points['eye_tip'] = tuple(Vector(points['head']) + Vector((0.0, 0.0, 0.08)))  # looking forward (+Z)
	bones = {}
	tails = {}
	for part, head_joint, tail_joint, parent in BONES:
		sides = SIDES if part in SIDED_BONES else (('C', 1.0),)
		for side, sign in sides:
			name = bone_name(part, side)
			parent_name = bone_name(parent, side) if parent else None
			# Offset bones must stay free: connected bones ignore location.
			connected = parent_name is not None and tails[parent_name] == head_joint and part not in OFFSET_BONES
			bones[name] = (
				game_point(_mirror(points[head_joint], sign)),
				game_point(_mirror(points[tail_joint], sign)),
				parent_name, connected)
			tails[name] = tail_joint
	return bones


def set_rest_bones(arm, joints):
	"""Put the rig's bones (in Edit Mode) at the game's joints, adding missing ones."""
	edit_bones = arm.data.edit_bones
	layout = rest_bones(joints)
	for name, (head, tail, _, _) in layout.items():
		bone = edit_bones.get(name) or edit_bones.new(name)
		bone.head = head
		bone.tail = tail
		bone.roll = 0.0
	for name, (_, _, parent, connected) in layout.items():
		bone = edit_bones[name]
		bone.parent = edit_bones[parent] if parent else None
		bone.use_connect = connected


def rest_bone_problem(arm, joints):
	"""None if the rig's bones are at rest where the game's joints are.

	Else 'missing' (a bone was deleted) or 'moved' (moved in Edit Mode).
	"""
	bones = arm.data.bones
	for name, (head, tail, parent, _) in rest_bones(joints).items():
		bone = bones.get(name)
		if bone is None:
			return 'missing'
		if (bone.head_local - head).length > 1e-4 or (bone.tail_local - tail).length > 1e-4:
			return 'moved'
		if (bone.parent.name if bone.parent else None) != parent:
			return 'moved'
	return None


def lock_bones(arm):
	for bone in arm.pose.bones:
		if bone.name not in MOVABLE_BONES and bone.name.partition('.')[0] not in OFFSET_BONES:
			bone.lock_location = (True, True, True)
		if bone.name.partition('.')[0] in RIGID_BONES:
			bone.lock_rotation = (True, True, True)
			bone.lock_rotation_w = True
			bone.lock_scale = (True, True, True)


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


def parent_to_bone(obj, arm, bone, rest_matrix):
	"""Bone-parent `obj` so it sits at `rest_matrix` with an identity transform.

	`rest_matrix` is where the object belongs with the rig at rest, in the
	rig's own space. The rest placement goes into the parent inverse,
	leaving the object's own location/rotation/scale at zero. Moving a part
	to get at it is then undone by Alt+G/R/S (or Repair), and export never
	reads transforms. Computed from the bone's rest, so it's right whatever
	the pose is or wherever the character has been moved.
	"""
	obj.parent = arm
	obj.parent_type = 'BONE'
	obj.parent_bone = bone
	obj.matrix_parent_inverse = bone_rest_parent_inverse(arm, bone, rest_matrix)
	obj.matrix_basis = Matrix.Identity(4)


def bone_rest_parent_inverse(arm, bone, rest_matrix):
	"""The parent inverse that puts a child of `bone` at `rest_matrix`.

	A bone-parented object hangs from the bone's tail: its world matrix is
	rig @ pose bone @ (0, length, 0) @ parent inverse @ own transform.
	"""
	data = arm.data.bones[bone]
	tail = data.matrix_local @ Matrix.Translation((0.0, data.length, 0.0))
	return tail.inverted() @ rest_matrix


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
	tex.name = 'bct_color'
	tex.image = _image(root, texture, data=False)
	tex.location = (-350, 150)
	links.new(tex.outputs['Color'], group.inputs['Color'])
	mask_node = nodes.new('ShaderNodeTexImage')
	mask_node.name = 'bct_color_mask'
	mask_node.image = _image(root, mask, data=True)
	mask_node.location = (-350, -150)
	links.new(mask_node.outputs['Color'], group.inputs['Color Mask'])
	for socket_name, field in TINT_DRIVERS:
		drive_color(group.inputs[socket_name], collection, f'ballistica_character.{field}')
	add_reflection(mat, group, nodegroup.REFLECTION_CHAR)
	drive_float(group.inputs['Reflection Scale'], collection, 'ballistica_character.reflection_scale')
	return mat


def add_reflection(mat, group, image_name):
	"""Feed `group`'s Reflection from a bundled environment, looked up along
	the reflected view direction (the engine's vReflect, in world space)."""
	from . import nodegroup

	nodes, links = mat.node_tree.nodes, mat.node_tree.links
	coords = nodes.new('ShaderNodeTexCoord')
	coords.location = (-650, -420)
	env = nodes.new('ShaderNodeTexEnvironment')
	env.image = nodegroup.get_data('images', [image_name])[0]
	env.location = (-400, -420)
	links.new(coords.outputs['Reflection'], env.inputs['Vector'])
	links.new(env.outputs['Color'], group.inputs['Reflection'])


def drive_float(socket, collection, data_path):
	"""Drive a float socket from a collection's float property."""
	driver = socket.driver_add('default_value').driver
	driver.type = 'AVERAGE'
	var = driver.variables[0] if driver.variables else driver.variables.new()
	var.name = 'value'
	var.type = 'SINGLE_PROP'
	var.targets[0].id_type = 'COLLECTION'
	var.targets[0].id = collection
	var.targets[0].data_path = data_path


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
	if not logical:
		return None
	path = workspace.file_path(root, logical, 'texture')
	if path is None:
		# Not on disk yet: an image made in Blender for this path (a new
		# character's textures), saved there on export.
		return find_image(workspace.new_file_path(root, logical, 'texture')) or find_texture(root, logical)
	image = find_image(path)
	if image is None:
		image = bpy.data.images.load(path, check_existing=True)
		image.ballistica_texture.path = logical
		image[ROOT_KEY] = root
		from .props import load_texture_settings

		load_texture_settings(image, workspace.texture_settings(root, path))
	if data:
		set_colorspace(image, 'Non-Color')
	return image


ROOT_KEY = 'bct_root'


def find_texture(root, logical):
	"""An image in Blender whose export path is `logical` (made or renamed here)."""
	return next(
		(i for i in bpy.data.images if i.ballistica_texture.path == logical and i.get(ROOT_KEY, root) == root),
		None)


def set_colorspace(image, name):
	"""Change how Blender reads an image's colors, keeping unsaved paint.

	Changing a generated or edited image's color space regenerates or
	reloads it, which would wipe what was painted, so its pixels are kept.
	"""
	if image.colorspace_settings.name == name:
		return
	keep = image.source == 'GENERATED' or image.is_dirty
	pixels = None
	if keep and image.has_data:
		pixels = [0.0] * len(image.pixels)
		image.pixels.foreach_get(pixels)
	image.colorspace_settings.name = name
	if pixels is not None:
		image.pixels.foreach_set(pixels)


def find_image(path):
	"""The loaded image whose file is `path`, or None."""
	path = os.path.abspath(path)
	return next((i for i in bpy.data.images if i.filepath and os.path.abspath(bpy.path.abspath(i.filepath)) == path), None)


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
	mesh['bct_internal'] = True  # preview only: never offered as a part's mesh
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

# The eyeball's rest turn about game +X by eyeball_pitch (-10 degrees), as
# the web UI's preview places it; in Blender axes.
EYEBALL_PITCH = (TO_BLENDER @ Matrix.Rotation(math.radians(rig.EYEBALL_PITCH), 3, 'X') @ TO_GAME).to_4x4()


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
	for mesh in (ball_mesh, lid_mesh):
		mesh['bct_internal'] = True  # bundled: never offered as a part's mesh
	texture, mask = nodegroup.get_data('images', nodegroup.EYE_IMAGES)
	name = collection.name
	eye_material = build_eye_material(f'{name}_eye', collection, texture, mask, 'eye_color', 'eyeball_color', nodegroup.EYEBALL_REFLECTION)
	iris_material = build_eye_material(f'{name}_iris', collection, texture, mask, 'eye_color', 'eyeball_color', nodegroup.IRIS_REFLECTION)
	lid_material = build_eye_material(f'{name}_eyelid', collection, texture, None, None, 'eyelid_color', nodegroup.EYELID_REFLECTION)
	head = placements['head']
	none = rig.EYE_STYLES.index('none')
	regular = rig.EYE_STYLES.index('regular')
	eyes = []
	for side, field in (('R', 'eye_style_right'), ('L', 'eye_style_left')):
		eye = _eye_object(f'eye.{side}', ball_mesh, (eye_material, iris_material), side, target)
		# The eyeball rests pitched (rig eyeball_pitch: looking slightly down);
		# the lid doesn't, so it undoes the pitch below.
		parent_to_bone(eye, arm, f'eye_offset.{side}', Matrix.Translation(game_point(head.location)) @ EYEBALL_PITCH)
		for axis in range(3):
			drive_value(eye, 'scale', axis, collection, 'eye_scale', '-v' if side == 'L' and axis == 0 else 'v')
		for path in ('hide_viewport', 'hide_render'):
			drive_value(eye, path, -1, collection, field, f'v == {none}')

		lid = _eye_object(f'eyelid.{side}', lid_mesh, (lid_material,), side, target)
		lid.parent = eye
		lid.matrix_parent_inverse = EYEBALL_PITCH.inverted()
		# Game rotation about the forward axis (+Z) is Blender's -Y.
		drive_value(lid, 'rotation_euler', 1, collection, 'eyelid_angle', '-radians(v)')
		for path in ('hide_viewport', 'hide_render'):
			drive_value(lid, path, -1, collection, field, f'v != {regular}')
		eyes += [eye, lid]
	return eyes


def assign_material(obj, material):
	"""Give `obj` its character's material on the object, not the mesh.

	Meshes are shared by file path, between parts and between characters
	using the same files, so a material on the mesh would make one
	character's tints show on another. The mesh keeps a slot (with a
	fallback material) for the object-linked one to fill.
	"""
	if not obj.data.materials:
		obj.data.materials.append(material)
	obj.material_slots[0].link = 'OBJECT'
	obj.material_slots[0].material = material


def _eye_object(name, mesh, materials, side, target):
	obj = bpy.data.objects.new(name, mesh)
	target.objects.link(obj)
	obj.ballistica_part.role = 'eye'
	obj.ballistica_part.side = side
	# The meshes are shared between characters; materials are per object.
	# The eyeball mesh has two slots: ball, then iris.
	if len(obj.material_slots) != len(materials):
		from .nodegroup import MissingAssetError
		raise MissingAssetError(f"{mesh.name} has {len(obj.material_slots)} material slots, expected {len(materials)}; rebuild the addon (make assets)")
	for slot, material in zip(obj.material_slots, materials):
		slot.link = 'OBJECT'
		slot.material = material
	return obj


def build_eye_material(name, collection, texture, mask, iris_field, base_field, reflection):
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
	# The eyeball and iris reflect the sharp environment strongly; the lid barely.
	eyeball = base_field == 'eyeball_color'
	add_reflection(mat, group, nodegroup.REFLECTION_SHARPEST if eyeball else nodegroup.REFLECTION_CHAR)
	group.inputs['Reflection Scale'].default_value = reflection
	return mat


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


def setup_spread_drivers(collection, objects=None):
	"""Drive each bone-parented object's delta location by the Spread slider.

	Offsets are the web UI's per-part spread (pose.SPREAD), mirrored for
	left-side bones; eyes and head attachments follow the head, and the
	roller the pelvis (its parent). delta_location is applied in the
	object's rest frame (its parent inverse), so the world offset is mapped
	into that frame once here; location stays free for moving parts.
	"""
	for obj in collection.all_objects if objects is None else objects:
		if obj.parent_type != 'BONE' or not obj.parent_bone or obj.parent is None or obj.parent_bone not in obj.parent.data.bones:
			continue
		part, _, side = obj.parent_bone.partition('.')
		part = 'head' if part == 'eye_offset' else part
		offset = pose.SPREAD.get(part)
		if offset is None or not any(offset):
			continue
		if side == 'L':
			offset = pose.mirror(offset)
		# The object's rest frame in rig space (pose and rig placement don't matter).
		bone = obj.parent.data.bones[obj.parent_bone]
		tail = bone.matrix_local @ Matrix.Translation((0.0, bone.length, 0.0))
		rest = (tail @ obj.matrix_parent_inverse).to_3x3()
		local = rest.inverted() @ game_point(offset)
		for i in range(3):
			if abs(local[i]) > 1e-9:
				drive_value(obj, 'delta_location', i, collection, 'spread', f'{local[i]:.6f}*v')


from . import props as _props  # noqa: E402  (props must not import scene)

_props.ATTACHMENT_REBUILD_HOOKS['colorspace'] = set_colorspace
