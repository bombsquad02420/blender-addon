"""Import, export and check characters in a local workspace folder."""

import json
import os
import re

import bpy
from bpy_extras.io_utils import ImportHelper

from . import bchar, objfile, pose, props, rig, scene, template, workspace
from .ui import active_character


def _build(context, root, character_path, character, meshes=None):
	"""Create the whole character scene; return its collection.

	`meshes` maps part name to a Blender mesh to use instead of reading the
	part's OBJ from the workspace (a new character's meshes aren't on disk
	until export).
	"""
	meshes = meshes or {}
	name = character_path.rsplit('/', 1)[-1]
	collection = bpy.data.collections.new(name)
	context.scene.collection.children.link(collection)
	settings = collection.ballistica_character
	settings.is_character = True
	settings.workspace_root = root
	settings.character_path = character_path
	props.load_into(settings, character)

	groups = scene.make_groups(collection)
	# Rest pose at zero offsets; the offset bones' drivers apply them.
	placements, joints = pose.compute()
	arm = scene.build_armature(groups['Rig'], joints)
	scene.build_root(collection, arm)

	materials = {}

	def material_for(texture, mask):
		key = (texture, mask)
		if key not in materials:
			label = name if key == (settings.color_texture, settings.color_mask_texture) else f'{name}_{texture.rsplit("/", 1)[-1]}'
			materials[key] = scene.build_material(label, root, texture, mask, collection)
		return materials[key]

	body_material = material_for(settings.color_texture, settings.color_mask_texture)

	missing = []
	for part, field, _ in rig.PARTS:
		logical = getattr(settings, field)
		if not logical:
			continue
		mesh = meshes.get(part)
		if mesh is None:
			path = workspace.file_path(root, logical, 'mesh')
			if path is None:
				missing.append(logical)
				continue
			mesh = scene.mesh_from_obj(path, logical)
		right = _part_object(groups[scene.PART_GROUPS[part]], f'{part}.R' if part in rig.PAIRED_PARTS else part, mesh, part, body_material)
		world = scene.placement_matrix(placements[part])
		scene.parent_to_bone(right, arm, scene.bone_name(part, 'R'), world)
		if part not in rig.PAIRED_PARTS:
			right.ballistica_part.side = 'CENTER'
			continue
		right.ballistica_part.side = 'R'
		left_logical = getattr(settings, f'left_{part}_mesh')
		left_path = workspace.file_path(root, left_logical, 'mesh') if left_logical else None
		mesh = scene.mesh_from_obj(left_path, left_logical) if left_path else right.data
		left = _part_object(groups[scene.PART_GROUPS[part]], f'{part}.L', mesh, part, body_material)
		left.ballistica_part.side = 'L'
		scene.parent_to_bone(left, arm, scene.bone_name(part, 'L'), scene.MIRROR_X @ world)

	scene.build_eyes(collection, arm, placements, settings, groups['Eyes'])
	scene.build_attachments(
		groups['Attachments'], arm, placements, character.attachments, root,
		lambda segment: material_for(segment.get('texture') or settings.color_texture,
			segment.get('mask_texture') or settings.color_mask_texture))
	scene.build_guides(collection, arm, placements, joints, settings)
	scene.setup_offset_drivers(collection, arm)
	scene.setup_spread_drivers(collection)
	return collection, missing


def _bundled_assets_ok(operator):
	"""Load the addon's bundled node groups, eye meshes and images.

	Done before building anything, so a broken install leaves no half-built
	scene. Reports and returns False on failure.
	"""
	from . import nodegroup

	try:
		nodegroup.get()
		nodegroup.get(nodegroup.EYE_GROUP_NAME)
		nodegroup.get_data('meshes', nodegroup.EYE_MESHES)
		nodegroup.get_data('images', nodegroup.EYE_IMAGES)
	except (nodegroup.MissingAssetError, OSError) as exc:
		operator.report({'ERROR'}, str(exc))
		return False
	return True


def _part_object(collection, name, mesh, part, material):
	obj = bpy.data.objects.new(name, mesh)
	collection.objects.link(obj)
	obj.ballistica_part.role = part
	if not mesh.materials:
		mesh.materials.append(material)
	return obj


class BALLISTICA_OT_import_character(bpy.types.Operator, ImportHelper):
	"""Import a character (.bchar) from a local workspace folder"""
	bl_idname = 'ballistica.import_character'
	bl_label = "Import Character"
	bl_options = {'REGISTER', 'UNDO'}

	filename_ext = '.bchar'
	filter_glob: bpy.props.StringProperty(default='*.bchar', options={'HIDDEN'})

	def execute(self, context):
		root = workspace.find_root(self.filepath)
		if root is None:
			self.report({'ERROR'}, "Not inside a workspace: no workspace.json found above this file.")
			return {'CANCELLED'}
		try:
			character = bchar.Character.load(self.filepath)
		except (OSError, ValueError) as exc:
			self.report({'ERROR'}, f"Couldn't read {os.path.basename(self.filepath)}: {exc}")
			return {'CANCELLED'}
		if character.type != rig.CHARACTER_TYPE:
			self.report({'WARNING'}, f"Unknown character type '{character.type}'; importing as {rig.CHARACTER_TYPE}.")
		if not _bundled_assets_ok(self):
			return {'CANCELLED'}
		if context.object is not None and context.object.mode != 'OBJECT':
			bpy.ops.object.mode_set(mode='OBJECT')
		collection, missing = _build(context, root, workspace.logical_path(root, self.filepath), character)
		if missing:
			self.report({'WARNING'}, f"Missing meshes: {', '.join(missing)}")
		else:
			self.report({'INFO'}, f"Imported {collection.name}")
		return {'FINISHED'}


NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')


def new_character(name):
	"""A .bchar for a from-scratch character whose files all use `name`."""
	character = bchar.Character()
	character.set('name', f'strings/characters/{name}')
	for field, logical in (
		('color_texture', f'textures/{name}_color'),
		('color_mask_texture', f'textures/{name}_color_mask'),
		('icon_texture', f'textures/{name}_icon'),
		('icon_mask_texture', f'textures/{name}_icon_color_mask'),
	):
		character.set(field, logical)
	for part, field, _ in rig.PARTS:
		character.set(field, f'meshes/{name}_{part}')
	character.set('color', [0.3, 0.5, 0.9])
	character.set('highlight', [1.0, 0.8, 0.1])
	return character


def _new_image(root, logical, pixels, size, data):
	"""An in-memory PNG that export writes to the logical path's file."""
	image = bpy.data.images.new(logical.rsplit('/', 1)[-1], size, size, alpha=True)
	if data:
		# Before the pixels: changing a generated image's color space
		# regenerates it, wiping them.
		image.colorspace_settings.name = 'Non-Color'
	image.pixels.foreach_set(pixels)
	image.filepath_raw = workspace.new_file_path(root, logical, 'texture')
	image.file_format = 'PNG'
	return image


class BALLISTICA_OT_new_character(bpy.types.Operator):
	"""Start a character from scratch in a workspace: rig, guides, eyes and a cuboid body in the game's proportions. Nothing is written until you export"""
	bl_idname = 'ballistica.new_character'
	bl_label = "New Character"
	bl_options = {'REGISTER', 'UNDO'}

	directory: bpy.props.StringProperty(
		name="Workspace", subtype='DIR_PATH',
		description="A local workspace folder (one with a workspace.json, e.g. from bacloud workspace get)")
	name: bpy.props.StringProperty(
		name="Name", default="my_character",
		description="Lowercase id used for the character's files, e.g. characters/<name>.bchar and meshes/<name>_head.obj")

	def invoke(self, context, event):
		current = active_character(context)
		if current is not None and not self.directory:
			self.directory = current.ballistica_character.workspace_root
		return context.window_manager.invoke_props_dialog(self, width=420)

	def execute(self, context):
		root = workspace.find_root(self.directory) if self.directory else None
		if root is None:
			self.report({'ERROR'}, "Pick a workspace folder: no workspace.json found there or above it.")
			return {'CANCELLED'}
		name = self.name.strip()
		if not NAME_PATTERN.match(name):
			self.report({'ERROR'}, "Name must be lowercase letters, digits and underscores, starting with a letter.")
			return {'CANCELLED'}
		character_path = f'characters/{name}'
		character = new_character(name)
		taken = [logical for _, kind, logical in character.referenced_assets() if workspace.file_path(root, logical, kind)]
		if workspace.file_path(root, character_path, 'character'):
			taken.insert(0, character_path)
		if taken:
			self.report({'ERROR'}, f"{name} is taken in this workspace ({', '.join(taken[:3])}); pick another name.")
			return {'CANCELLED'}
		if not _bundled_assets_ok(self):
			return {'CANCELLED'}
		if context.object is not None and context.object.mode != 'OBJECT':
			bpy.ops.object.mode_set(mode='OBJECT')

		color, mask = template.textures(256)
		icon, icon_mask = template.icon(64)
		_new_image(root, character.get('color_texture'), color, 256, data=False)
		_new_image(root, character.get('color_mask_texture'), mask, 256, data=True)
		_new_image(root, character.get('icon_texture'), icon, 64, data=False)
		_new_image(root, character.get('icon_mask_texture'), icon_mask, 64, data=True)
		meshes = {part: scene.mesh_from_objmesh(template.cuboid(part), f'meshes/{name}_{part}') for part in template.CUBOIDS}
		collection, _ = _build(context, root, character_path, character, meshes)
		self.report({'INFO'}, f"Created {collection.name}; Export Character writes it to the workspace")
		return {'FINISHED'}


def check(collection):
	"""Problems that would make the cloud build fail or look wrong."""
	settings = collection.ballistica_character
	root = settings.workspace_root
	problems = []
	if not root or not os.path.isfile(os.path.join(root, workspace.WORKSPACE_FILE)):
		return [f"Workspace folder not found: {root or '(none)'}"]
	character = props.to_character(settings)
	for field in rig.REQUIRED_REFS:
		if not character.get(field):
			problems.append(f"{field} is required")
	exported = {f for p, f, _ in rig.PARTS if any(o.ballistica_part.role == p for o in _exportable_parts(collection))}
	for field, kind, logical in character.referenced_assets():
		if field in exported or workspace.file_path(root, logical, kind) is not None:
			continue
		if kind == 'texture' and scene.find_image(workspace.new_file_path(root, logical, kind)) is not None:
			continue  # Made in Blender; export writes it.
		problems.append(f"{field}: {logical} not found in the workspace")
	for field in ('color_mask_texture', 'icon_mask_texture'):
		path = workspace.file_path(root, character.get(field) or '', 'texture') if character.get(field) else None
		if path and workspace.texture_role(root, path) != 'data':
			problems.append(f"{field}: {character.get(field)} is not marked texture_role: data (export will fix this)")
	for obj in _exportable_parts(collection):
		if obj.data.uv_layers.active is None:
			problems.append(f"{obj.name}: mesh has no UVs")
	return problems


def _exportable_parts(collection):
	"""Right-side and center part objects (left limbs mirror the right).

	A list, not a generator: export writes ID properties on the meshes as it
	goes, which makes Blender rebuild `all_objects` and would cut a live
	iteration short.
	"""
	return [
		obj for obj in collection.all_objects
		if obj.type == 'MESH' and obj.ballistica_part.role in rig.ATTACH_TARGETS and obj.ballistica_part.side != 'L'
	]


# Objects Reset Parts puts back: everything placed on the rig except guides.
RESETTABLE_ROLES = (*(p for p, _, _ in rig.PARTS), 'attachment', 'eye')


class BALLISTICA_OT_view_character(bpy.types.Operator):
	"""Frame the active character's rig with View Selected"""
	bl_idname = 'ballistica.view_character'
	bl_label = "Frame Character"

	@classmethod
	def poll(cls, context):
		if context.mode != 'OBJECT':
			cls.poll_message_set("Only in Object Mode")
			return False
		return context.region_data is not None and active_character(context) is not None

	def execute(self, context):
		arm, rig_layer, problem = _framable_rig(context, active_character(context))
		if problem:
			# View Selected would silently frame nothing (or fail, if the
			# rig isn't in the view layer), so say what's in the way.
			self.report({'ERROR'}, problem)
			return {'CANCELLED'}
		view_layer = context.view_layer
		# Show the rig and select only it, run View Selected, then put
		# everything back. The target view is computed when the operator
		# runs, so restoring right away doesn't disturb the (smooth) move.
		was_hidden = rig_layer.hide_viewport
		selected = [o for o in view_layer.objects if o.select_get()]
		active = view_layer.objects.active
		try:
			rig_layer.hide_viewport = False
			for obj in selected:
				obj.select_set(False)
			arm.select_set(True)
			view_layer.objects.active = arm
			view_layer.update()
			bpy.ops.view3d.view_selected()
		finally:
			arm.select_set(False)
			for obj in selected:
				obj.select_set(True)
			view_layer.objects.active = active
			rig_layer.hide_viewport = was_hidden
		return {'FINISHED'}


def _framable_rig(context, collection):
	"""(armature, its Rig layer collection, None), or (None, None, problem).

	The Rig collection's own eye icon is fine: Frame Character turns it on
	for the moment. Anything else hiding the rig is reported, since View
	Selected can't frame it.
	"""
	arm = next((o for o in collection.all_objects if o.type == 'ARMATURE'), None)
	if arm is None:
		return None, None, f"{collection.name} has no rig."
	path = _layer_path(context.view_layer.layer_collection, arm.users_collection[0])
	if path is None:
		return None, None, f"{arm.name} isn't in this view layer."
	for layer in path:
		if layer.exclude:
			return None, None, f"{layer.collection.name} is excluded from the view layer; include it in the outliner to frame the character."
		if layer.collection.hide_viewport:
			return None, None, f"{layer.collection.name} is disabled in viewports; enable it in the outliner to frame the character."
	if arm.name not in context.view_layer.objects:
		return None, None, f"{arm.name} isn't in this view layer."
	for layer in path[:-1]:
		if layer.hide_viewport:
			return None, None, f"{layer.collection.name} is hidden; show it in the outliner to frame the character."
	if arm.hide_viewport:
		return None, None, f"{arm.name} is disabled in viewports; enable it in the outliner to frame the character."
	if arm.hide_get():
		return None, None, f"{arm.name} is hidden; unhide it in the outliner (Alt+H) to frame the character."
	return arm, path[-1], None


def _layer_path(layer, collection):
	"""Layer collections from the view layer root down to `collection`."""
	if layer.collection == collection:
		return [layer]
	for child in layer.children:
		path = _layer_path(child, collection)
		if path is not None:
			return [layer, *path]
	return None


class BALLISTICA_OT_reset_parts(bpy.types.Operator):
	"""Put the character back in its T-pose: move the rig back onto its root, clear its pose and move body parts, attachments and eyes back onto their bones (only the selected parts if any are selected)"""
	bl_idname = 'ballistica.reset_parts'
	bl_label = "Reset to T-Pose"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return active_character(context) is not None

	def execute(self, context):
		collection = active_character(context)
		parts = [o for o in collection.all_objects if o.ballistica_part.role in RESETTABLE_ROLES]
		# Rest placement lives in each part's parent inverse, so an identity
		# transform puts a part back on its bone.
		selected = [o for o in parts if o.select_get()]
		for obj in selected or parts:
			_clear_transform(obj)
		if not selected:
			arm = next((o for o in collection.all_objects if o.type == 'ARMATURE'), None)
			if arm is not None:
				_clear_transform(arm)  # Back onto the root (the root itself stays put).
				for bone in arm.pose.bones:
					_clear_transform(bone)  # Offset bones' location is re-applied by drivers.
		collection.update_tag()  # Re-run drivers (offsets, eye scale).
		self.report({'INFO'}, f"Reset {len(selected)} part(s)" if selected else f"Reset {collection.name} to its T-pose")
		return {'FINISHED'}


def _clear_transform(item):
	item.location = (0.0, 0.0, 0.0)
	item.rotation_euler = (0.0, 0.0, 0.0)
	item.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
	item.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
	item.scale = (1.0, 1.0, 1.0)


class BALLISTICA_OT_standard_colors(bpy.types.Operator):
	"""Show colors as the web UI and game do: set this scene's view transform to Standard (no look, exposure 0, gamma 1). Blender's default AgX washes colors out"""
	bl_idname = 'ballistica.standard_colors'
	bl_label = "Use Standard Colors"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return not uses_standard_colors(context.scene)

	def execute(self, context):
		view = context.scene.view_settings
		view.view_transform = 'Standard'
		view.look = 'None'
		view.exposure = 0.0
		view.gamma = 1.0
		return {'FINISHED'}


def uses_standard_colors(scene):
	view = scene.view_settings
	return view.view_transform == 'Standard' and view.look == 'None' and view.exposure == 0.0 and view.gamma == 1.0


class BALLISTICA_OT_check_character(bpy.types.Operator):
	"""Check the active character for problems before uploading"""
	bl_idname = 'ballistica.check_character'
	bl_label = "Check"

	@classmethod
	def poll(cls, context):
		return active_character(context) is not None

	def execute(self, context):
		problems = check(active_character(context))
		for problem in problems:
			self.report({'WARNING'}, problem)
		if not problems:
			self.report({'INFO'}, "No problems found.")
		return {'FINISHED'}


class BALLISTICA_OT_export_character(bpy.types.Operator):
	"""Write the active character's meshes, textures and .bchar into its workspace folder (overwrites local files)"""
	bl_idname = 'ballistica.export_character'
	bl_label = "Export Character"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context):
		return active_character(context) is not None

	def execute(self, context):
		collection = active_character(context)
		settings = collection.ballistica_character
		root = settings.workspace_root
		if not root or not os.path.isfile(os.path.join(root, workspace.WORKSPACE_FILE)):
			self.report({'ERROR'}, f"Workspace folder not found: {root or '(none)'}")
			return {'CANCELLED'}
		written = []

		# Meshes: write each part's mesh data to the file its field names.
		for obj in _exportable_parts(collection):
			part = obj.ballistica_part.role
			field = dict((p, f) for p, f, _ in rig.PARTS)[part]
			logical = getattr(settings, field) or f'meshes/{collection.name}_{part}'
			setattr(settings, field, logical)
			path = workspace.file_path(root, logical, 'mesh')
			signature = scene.mesh_signature(obj.data)
			if path is not None and obj.data.get(scene.SIGNATURE_KEY) == signature:
				continue  # Unchanged since import or last export.
			path = path or workspace.new_file_path(root, logical, 'mesh')
			os.makedirs(os.path.dirname(path), exist_ok=True)
			objfile.write(path, scene.obj_from_mesh(obj.data))
			obj.data[scene.SIGNATURE_KEY] = signature
			written.append(os.path.relpath(path, root))

		# Textures: save images edited in Blender back as PNG, and write ones
		# made in Blender that aren't on disk yet (a new character's).
		masks = []
		for field, data in (
			('color_texture', False), ('color_mask_texture', True),
			('icon_texture', False), ('icon_mask_texture', True),
		):
			logical = getattr(settings, field)
			if not logical:
				continue
			path = workspace.file_path(root, logical, 'texture') or workspace.new_file_path(root, logical, 'texture')
			image = scene.find_image(path)
			exists = os.path.isfile(path)
			if image is not None and (image.is_dirty or not exists):
				os.makedirs(os.path.dirname(path), exist_ok=True)
				image.save()
				written.append(os.path.relpath(path, root))
			elif not exists:
				continue
			if data:
				masks.append(path)
		if workspace.mark_data_textures(root, masks):
			written.append(workspace.WORKSPACE_FILE)

		character = props.to_character(settings)
		bchar_path = workspace.file_path(root, settings.character_path, 'character') or workspace.new_file_path(root, settings.character_path, 'character')
		if character.save(bchar_path):
			written.append(os.path.relpath(bchar_path, root))
		settings.raw_json = json.dumps(character.raw)

		for problem in check(collection):
			self.report({'WARNING'}, problem)
		self.report({'INFO'}, f"Wrote {len(written)} file(s)" + (f": {', '.join(written)}" if written else " (nothing changed)"))
		return {'FINISHED'}


def menu_import(self, context):
	self.layout.operator(BALLISTICA_OT_import_character.bl_idname, text="Ballistica Character (.bchar)")


classes = (
	BALLISTICA_OT_import_character,
	BALLISTICA_OT_new_character,
	BALLISTICA_OT_standard_colors,
	BALLISTICA_OT_view_character,
	BALLISTICA_OT_reset_parts,
	BALLISTICA_OT_check_character,
	BALLISTICA_OT_export_character,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister():
	bpy.types.TOPBAR_MT_file_import.remove(menu_import)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
