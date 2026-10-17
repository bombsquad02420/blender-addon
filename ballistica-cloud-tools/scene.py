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
SIDES = (('R', 1.0), ('L', -1.0))

# Bone layout: name -> (head joint, tail joint, parent). Right side only;
# left bones mirror these.
BONES = (
	('pelvis', 'pelvis', 'spine', None),
	('torso', 'spine', 'neck', 'pelvis'),
	('head', 'neck', 'head', 'torso'),
	('upper_arm', 'shoulder', 'elbow', 'torso'),
	('forearm', 'elbow', 'wrist', 'upper_arm'),
	('hand', 'wrist', 'hand_tip', 'forearm'),
	('upper_leg', 'hip', 'knee', 'pelvis'),
	('lower_leg', 'knee', 'ankle', 'upper_leg'),
	('toes', 'ankle', 'toe_tip', 'lower_leg'),
	('wing', 'torso', 'wing_tip', 'torso'),
)


# Parts with a bone per side (limbs, plus the wing spots).
SIDED_BONES = (*rig.PAIRED_PARTS, 'wing')


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

def build_armature(collection, joints):
	data = bpy.data.armatures.new(collection.name + ARMATURE_SUFFIX)
	data.display_type = 'STICK'
	arm = bpy.data.objects.new(collection.name + ARMATURE_SUFFIX, data)
	collection.objects.link(arm)
	arm.show_in_front = True
	arm.ballistica_part.role = 'NONE'

	points = dict(joints)
	wrist, elbow = Vector(points['wrist']), Vector(points['elbow'])
	points['hand_tip'] = tuple(wrist + (wrist - elbow).normalized() * 0.06)

	with _edit_mode(arm):
		bones = data.edit_bones
		for part, head, tail, parent in BONES:
			sides = SIDES if part in SIDED_BONES else (('C', 1.0),)
			for side, sign in sides:
				bone = bones.new(bone_name(part, side))
				bone.head = game_point(_mirror(points[head], sign))
				bone.tail = game_point(_mirror(points[tail], sign))
				if parent:
					bone.parent = bones[bone_name(parent, side)]
					bone.use_connect = False
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
	obj.parent = arm
	obj.parent_type = 'BONE'
	obj.parent_bone = bone
	bpy.context.view_layer.update()
	obj.matrix_world = world_matrix


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
	links.new(group.outputs['BSDF'], out.inputs['Surface'])
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
	shapes = [
		('head', 'C', _sphere(rig.HEAD_RADIUS)),
		('torso', 'C', _sphere(settings.torso_radius)),
		('pelvis', 'C', _box(rig.PELVIS_SIZE)),
	]
	limbs = [
		('upper_arm', _capsule(rig.UPPER_ARM_RADIUS, rig.UPPER_ARM_LENGTH)),
		('forearm', _capsule(rig.LOWER_ARM_RADIUS, rig.LOWER_ARM_LENGTH)),
		('upper_leg', _capsule(settings.thigh_radius, rig.UPPER_LEG_LENGTH)),
		('lower_leg', _capsule(settings.ankle_radius, rig.LOWER_LEG_SPAN - 2 * settings.ankle_radius)),
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
	roller = bpy.data.objects.new('guide_roller', _sphere(rig.ROLLER_RADIUS))
	guides.objects.link(roller)
	roller.display_type = 'WIRE'
	roller.hide_select = True
	roller.ballistica_part.role = 'guide'
	parent_to_bone(roller, arm, 'pelvis', Matrix.Translation(game_point(joints['roller'])))
	return guides


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

def build_eyes(collection, arm, placements, settings):
	eyes = []
	head = placements['head']
	for side, sign, style in (('L', 1.0, settings.eye_style_left), ('R', -1.0, settings.eye_style_right)):
		if style == 'none':
			continue
		ox, oy, oz = settings.eye_offset
		local = (sign * abs(ox), oy, oz)  # eye_offset is mirrored to both eyes
		obj = bpy.data.objects.new(f'eye.{side}', _sphere(rig.EYE_MESH_SCALE * 0.5 * settings.eye_scale))
		collection.objects.link(obj)
		obj.hide_render = True
		obj.ballistica_part.role = 'eye'
		obj.ballistica_part.side = side
		obj.color = (*settings.eyeball_color, 1.0)
		parent_to_bone(obj, arm, 'head', Matrix.Translation(game_point(head.point(local))))
		eyes.append(obj)
	return eyes


# ---- attachments ----

LIMB_TARGETS = ('upper_arm', 'forearm', 'hand', 'upper_leg', 'lower_leg', 'toes', 'wing')


def build_attachments(collection, arm, placements, attachments, root, material_for):
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
				collection.objects.link(obj)
				obj.ballistica_part.role = 'attachment'
				obj.data.materials.append(material_for(segment))
				parent_to_bone(obj, arm, bone_name(body_part, 'R' if side_name == 'C' else side_name), world)
				objects.append(obj)
	return objects
