"""Import, export and check characters in a local workspace folder."""

import json
import os
import re

import bpy
from bpy_extras.io_utils import ImportHelper

from . import attach_scene, bchar, clone, eye_scene, migrate, part_scene, texture_scene, objfile, pose, props, rig, scene, template, workspace
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
	settings.format_version = migrate.FORMAT_VERSION
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
	settings.body_material = body_material

	missing = []
	for part, field, _ in rig.PARTS:
		logical = getattr(settings, field)
		if not logical:
			continue
		mesh = meshes.get(part)
		if mesh is not None:
			attach_scene.tag_mesh(mesh, root, logical)  # in memory until export
		if mesh is None:
			path = workspace.file_path(root, logical, 'mesh')
			if path is None:
				missing.append(logical)
				continue
			mesh = attach_scene.mesh_for(root, logical)  # shared by path, tagged
		right = _part_object(groups[scene.PART_GROUPS[part]], f'{part}.R' if part in rig.PAIRED_PARTS else part, mesh, part, body_material)
		world = scene.placement_matrix(placements[part])
		scene.parent_to_bone(right, arm, scene.bone_name(part, 'R'), world)
		if part not in rig.PAIRED_PARTS:
			right.ballistica_part.side = 'CENTER'
			continue
		right.ballistica_part.side = 'R'
		left_logical = getattr(settings, f'left_{part}_mesh')
		# On disk or made in memory (a copied character's); else the right's.
		mesh = (attach_scene.mesh_for(root, left_logical) if left_logical else None) or right.data
		left = _part_object(groups[scene.PART_GROUPS[part]], f'{part}.L', mesh, part, body_material)
		left.ballistica_part.side = 'L'
		scene.parent_to_bone(left, arm, scene.bone_name(part, 'L'), scene.MIRROR_X @ world)

	part_scene.fill_rows(collection)
	texture_scene.fill_rows(collection)
	scene.build_eyes(collection, arm, placements, settings, groups['Eyes'])
	eye_scene.build(collection, arm, groups['Rig'])
	attach_scene.build(collection, placements, spread=False)
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
	scene.assign_material(obj, material)
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
		_place_and_activate(context, collection)
		if missing:
			self.report({'WARNING'}, f"Missing meshes: {', '.join(missing)}")
		else:
			self.report({'INFO'}, f"Imported {collection.name}")
		return {'FINISHED'}


def _place_and_activate(context, collection):
	"""Put a new character at the 3D cursor and make it the active one.

	Selects its root as the active object too, so the active-object
	handler (which picks the character of whatever is clicked) agrees.
	"""
	root = collection.objects[collection.name + scene.ROOT_SUFFIX]
	root.location = context.scene.cursor.location
	for obj in context.view_layer.objects.selected:
		obj.select_set(False)
	root.select_set(True)
	context.view_layer.objects.active = root
	context.scene.ballistica_active_character = collection
	for area in context.screen.areas if context.screen else ():
		area.tag_redraw()


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


def _template_image(root, logical, texture):
	"""A bundled template PNG as a new in-memory image for `logical`."""
	source = bpy.data.images.load(template.texture_path(texture))
	try:
		source.colorspace_settings.name = 'Non-Color' if 'mask' in texture else 'sRGB'
		size = source.size[0]
		pixels = [0.0] * (size * source.size[1] * 4)
		source.pixels.foreach_get(pixels)
	finally:
		bpy.data.images.remove(source)
	return _new_image(root, logical, pixels, size, data='mask' in texture)


def _new_image(root, logical, pixels, size, data, height=None):
	"""An in-memory PNG that export writes to the logical path's file."""
	image = bpy.data.images.new(logical.rsplit('/', 1)[-1], size, height or size, alpha=True)
	if data:
		# Before the pixels: changing a generated image's color space
		# regenerates it, wiping them.
		image.colorspace_settings.name = 'Non-Color'
	image.pixels.foreach_set(pixels)
	image.filepath_raw = workspace.new_file_path(root, logical, 'texture')
	image.file_format = 'PNG'
	image.ballistica_texture.path = logical
	image[scene.ROOT_KEY] = root
	if data:
		image.ballistica_texture['role'] = workspace.TEXTURE_SETTINGS['texture_role'][0].index('data')
	return image


BLANK = 'BLANK'
EMPTY = 'EMPTY'
_START_ITEMS = []  # dynamic enum items must stay referenced from Python


def _start_from_items(self, context):
	"""Blank, Empty, then every character in the dialog's workspace."""
	items = [
		(BLANK, "Blank (cuboids)", "A cuboid body in the game's proportions", 'MESH_CUBE', 0),
		(EMPTY, "Empty (no geometry)", "Rig, guides, eyes and part objects with empty meshes and plain textures, to model from scratch", 'MESH_DATA', 1),
	]
	root = workspace.find_root(self.directory) if self.directory else None
	if root is not None:
		for i, logical in enumerate(workspace.list_assets(root, 'character'), start=2):
			items.append((logical, logical.rsplit('/', 1)[-1], f"Copy {logical}: its meshes, textures and settings", 'OUTLINER_COLLECTION', i))
	_START_ITEMS[:] = items
	return _START_ITEMS


# Placeholder textures for an empty character: (field, size, rgba).
EMPTY_TEXTURES = (
	('color_texture', 256, (1.0, 1.0, 1.0, 1.0)),
	('color_mask_texture', 256, (0.0, 0.0, 0.0, 1.0)),  # no tint
	('icon_texture', 64, (0.5, 0.5, 0.5, 1.0)),
	('icon_mask_texture', 64, (0.0, 0.0, 0.0, 1.0)),
)


def _empty_assets(root, character, name):
	"""Empty part meshes (with a UV map) and plain textures, in memory."""
	for field, size, rgba in EMPTY_TEXTURES:
		_new_image(root, character.get(field), list(rgba) * (size * size), size, data='mask' in field)
	meshes = {}
	for part, _, _ in rig.PARTS:
		mesh = bpy.data.meshes.new(f'meshes/{name}_{part}')
		mesh.uv_layers.new(name="UVMap")  # ready for modelling and painting
		meshes[part] = mesh
	return meshes


def _copy_assets(root, character, meshes, textures):
	"""In-memory copies of a source character's files under their new paths.

	Returns {part: mesh} for the body parts (what _build takes); every
	other copied mesh is found by attach_scene.mesh_for through its tag.
	Missing source files are skipped (Check reports them).
	"""
	copied = {}
	for old, new in meshes.items():
		path = workspace.file_path(root, old, 'mesh')
		if path is None:
			continue
		mesh = scene.mesh_from_obj(path, new)
		attach_scene.tag_mesh(mesh, root, new)
		copied[new] = mesh
	masks = clone.mask_textures(character)
	for old, new in textures.items():
		path = workspace.file_path(root, old, 'texture')
		if path is None:
			continue
		source = bpy.data.images.load(path)
		try:
			if new in masks:
				source.colorspace_settings.name = 'Non-Color'
			width, height = source.size
			pixels = [0.0] * (width * height * 4)
			source.pixels.foreach_get(pixels)
		finally:
			bpy.data.images.remove(source)
		_new_image(root, new, pixels, width, data=new in masks, height=height)
	return {part: copied[character.data[field]] for part, field, _ in rig.PARTS if character.data.get(field) in copied}


class BALLISTICA_OT_new_character(bpy.types.Operator):
	"""Start a character in a workspace: rig, guides and eyes, with a cuboid body in the game's proportions or a copy of another character. Nothing is written until you export"""
	bl_idname = 'ballistica.new_character'
	bl_label = "New Character"
	bl_options = {'REGISTER', 'UNDO'}

	directory: bpy.props.StringProperty(
		name="Workspace", subtype='DIR_PATH',
		description="A local workspace folder (one with a workspace.json, e.g. from bacloud workspace get)")
	name: bpy.props.StringProperty(
		name="Name", default="my_character",
		description="Lowercase id used for the character's files, e.g. characters/<name>.bchar and meshes/<name>_head.obj")
	start_from: bpy.props.EnumProperty(
		name="Start From", items=_start_from_items,
		description="Blank cuboids, or a copy of a character in the workspace (its own copies of the meshes and textures)")

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
		source = None
		if self.start_from and self.start_from not in (BLANK, EMPTY):
			source_path = workspace.file_path(root, self.start_from, 'character')
			if source_path is None:
				self.report({'ERROR'}, f"{self.start_from} isn't in this workspace.")
				return {'CANCELLED'}
			try:
				source = bchar.Character.load(source_path)
			except (OSError, ValueError) as exc:
				self.report({'ERROR'}, f"Couldn't read {self.start_from}: {exc}")
				return {'CANCELLED'}
			character, mesh_map, texture_map = clone.plan(source, name)
		else:
			character = new_character(name)
		# Only the files this character will write; copied sounds are shared.
		taken = [
			logical for _, kind, logical in character.referenced_assets()
			if kind in ('mesh', 'texture') and workspace.file_path(root, logical, kind)
		]
		if workspace.file_path(root, character_path, 'character'):
			taken.insert(0, character_path)
		if taken:
			self.report({'ERROR'}, f"{name} is taken in this workspace ({', '.join(taken[:3])}); pick another name.")
			return {'CANCELLED'}
		if not _bundled_assets_ok(self):
			return {'CANCELLED'}
		if context.object is not None and context.object.mode != 'OBJECT':
			bpy.ops.object.mode_set(mode='OBJECT')

		if self.start_from == EMPTY:
			meshes = _empty_assets(root, character, name)
			collection, _ = _build(context, root, character_path, character, meshes)
			_place_and_activate(context, collection)
			self.report({'INFO'}, f"Created {collection.name} with empty meshes; model each part, then Export Character")
			return {'FINISHED'}
		if source is not None:
			meshes = _copy_assets(root, character, mesh_map, texture_map)
			collection, _ = _build(context, root, character_path, character, meshes)
			_place_and_activate(context, collection)
			self.report({'INFO'}, f"Created {collection.name} from {self.start_from}; Export Character writes it to the workspace")
			return {'FINISHED'}

		# The starter body ships as files in assets/template/.
		missing = [p for p in [template.obj_path(part) for part in template.CUBOIDS] + [template.texture_path(t) for t in template.TEXTURES] if not os.path.isfile(p)]
		if missing:
			self.report({'ERROR'}, f"Bundled template files missing: {', '.join(os.path.basename(p) for p in missing)}. Rebuild the addon (make template).")
			return {'CANCELLED'}
		for texture, field in zip(template.TEXTURES, ('color_texture', 'color_mask_texture', 'icon_texture', 'icon_mask_texture')):
			_template_image(root, character.get(field), texture)
		meshes = {part: scene.mesh_from_obj(template.obj_path(part), f'meshes/{name}_{part}') for part in template.CUBOIDS}
		collection, _ = _build(context, root, character_path, character, meshes)
		_place_and_activate(context, collection)
		self.report({'INFO'}, f"Created {collection.name}; Export Character writes it to the workspace")
		return {'FINISHED'}


ERROR, WARNING = 'ERROR', 'WARNING'


class Problem(str):
	"""A Check message, with its level: ERROR (the cloud build would fail or
	the character would be broken) or WARNING (works, but may not look or
	behave as it does in Blender)."""

	def __new__(cls, text, level=ERROR):
		problem = super().__new__(cls, text)
		problem.level = level
		return problem


def report_problems(operator, problems):
	"""Report each problem, then a summary last (the status bar shows only the
	last report; clicking it lists them all)."""
	for problem in problems:
		operator.report({problem.level}, problem)
	if len(problems) > 1:
		operator.report({ERROR if any(p.level == ERROR for p in problems) else WARNING}, summary(problems))


def summary(problems):
	"""'3 errors and 5 warnings. Click to view all'."""
	errors = sum(1 for p in problems if p.level == ERROR)
	warnings = len(problems) - errors
	counts = [f"{n} {word}{'s' if n != 1 else ''}" for n, word in ((errors, "error"), (warnings, "warning")) if n]
	return f"{' and '.join(counts)}. Click to view all"


def check(collection):
	"""Problems that would make the cloud build fail (errors) or look wrong (warnings)."""
	settings = collection.ballistica_character
	root = settings.workspace_root
	problems = []
	if not root or not os.path.isfile(os.path.join(root, workspace.WORKSPACE_FILE)):
		return [Problem(f"Workspace folder not found: {root or '(none)'}")]
	attach_scene.mirror_paths(collection)
	fields = {**part_scene.fields(collection), **texture_scene.fields(collection)}
	character = props.to_character(settings, fields)
	part_names = {f: part_scene.label(r) for r in settings.parts for f in [part_scene.field(r)]}
	for field in rig.REQUIRED_REFS:
		if not character.get(field):
			problems.append(Problem(f"{part_names[field]} needs a mesh" if field in part_names else f"{field} is required"))
	for row in settings.parts:
		if row.enabled and row.mesh is None and row.side != 'L':
			problems.append(Problem(f"{part_scene.label(row)}: no mesh picked (pick one, press + for a box, or turn the part off)"))
	hint = rig.flippers_hint(settings.flippers, character.get('forearm_mesh'), character.get('hand_mesh'))
	if hint:
		problems.append(Problem(hint, WARNING))
	exported = {f for p, f, _ in rig.PARTS if any(o.ballistica_part.role == p for o in _exportable_parts(collection))}
	from . import attachments as attach_rules
	for index, attachment in enumerate(settings.attachments):
		problems += [Problem(p) for p in attach_rules.problems(props.attachment_record(attachment), index)]
	in_blender = _blocks_in_blender(settings)
	for field, kind, logical in character.referenced_assets():
		if field in exported or workspace.file_path(root, logical, kind) is not None:
			continue
		if (kind, logical) in in_blender:
			continue  # A mesh or image in Blender; export writes it.
		if kind == 'texture' and scene.find_image(workspace.new_file_path(root, logical, kind)):
			continue  # Made in Blender (an icon); export writes it.
		problems.append(Problem(f"{field}: {logical} not found in the workspace"))
	path = workspace.file_path(root, character.get('icon_mask_texture') or '', 'texture') if character.get('icon_mask_texture') else None
	if path and workspace.texture_role(root, path) not in workspace.DATA_ROLES:
		problems.append(Problem(f"icon_mask_texture: {character.get('icon_mask_texture')} is not marked texture_role: data (export will fix this)", WARNING))
	mask = texture_scene.row(settings, 'color_mask_texture')
	if mask is not None and mask.image is not None and mask.image.ballistica_texture.role not in workspace.DATA_ROLES:
		problems.append(Problem(f"Color Mask: {mask.image.name} should have the Data role (export will set it)", WARNING))
	for obj in _exportable_parts(collection):
		if not obj.data.polygons:
			problems.append(Problem(f"{obj.name}: mesh is empty (model it, or turn the part off if it's optional)"))
		elif not obj.data.uv_layers:
			problems.append(Problem(f"{obj.name}: mesh has no UVs"))
	# What export writes (modifiers applied): body parts and attachment
	# segments. Left copies share the right side's mesh.
	attachment_meshes = [o for o in attach_scene.tagged(collection, attach_scene.MESH) if o.get(attach_scene.SIDE_KEY) != 'L']
	for obj in _exportable_parts(collection) + attachment_meshes:
		problem = _uv_problem(obj)
		if problem:
			problems.append(Problem(problem))
	from . import sharing

	problems += [Problem(p) for p in sharing.duplicate_paths(collection)]
	# Things that drifted in the scene: export still works, but may not
	# give what the scene shows (Repair fixes them).
	from . import repair

	problems += [Problem(f"{issue.label}: {issue.explanation}", WARNING) for issue in repair.issues(collection)]
	return problems


def _uv_problem(obj):
	"""A message if the object's exported UVs fall outside the texture."""
	from array import array

	with scene.evaluated_mesh(obj) as mesh:
		layer = scene.export_uv_layer(mesh) if mesh.uv_layers else None
		if layer is None or not mesh.polygons:
			return None
		uvs = array('f', [0.0]) * (len(layer.data) * 2)
		layer.data.foreach_get('uv', uvs)
	out = objfile.uv_range_problem(uvs)
	if out is None:
		return None
	return (f"{obj.name}: UVs go outside the texture ({out[0]:.2f} to {out[1]:.2f}); the cloud "
		"build only accepts 0 to 1, with no tiling, so move them back inside the 0-1 square")


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
	"""Put the rig back in its T-pose: clear every bone's pose and move the rig back onto its root. Parts moved in Object Mode stay where they are (Repair puts them back)"""
	bl_idname = 'ballistica.reset_parts'
	bl_label = "Reset to T-Pose"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return active_character(context) is not None

	def execute(self, context):
		collection = active_character(context)
		arm = next((o for o in collection.all_objects if o.type == 'ARMATURE'), None)
		if arm is None:
			self.report({'ERROR'}, f"{collection.name} has no rig; Repair rebuilds it.")
			return {'CANCELLED'}
		_clear_transform(arm)  # Back onto the root (the root itself stays put).
		for bone in arm.pose.bones:
			_clear_transform(bone)  # Offset bones' location is re-applied by drivers.
		collection.update_tag()  # Re-run drivers (offsets, eye scale).
		self.report({'INFO'}, f"Reset {collection.name} to its T-pose")
		return {'FINISHED'}


class BALLISTICA_OT_repair(bpy.types.Operator):
	"""Fix what drifted: parts moved in Object Mode, detached or hidden, a deleted rig, missing eyes, guides or handles. Never changes the pose, mesh shapes or paint"""
	bl_idname = 'ballistica.repair'
	bl_label = "Repair"
	bl_options = {'REGISTER', 'UNDO'}

	selected: bpy.props.BoolProperty(
		name="Only Selected", default=False, options={'SKIP_SAVE'},
		description="Only the selected parts, eyes and attachment objects")

	@classmethod
	def description(cls, context, properties):
		if properties.selected:
			return "Put the selected parts, eyes and attachment objects back on the rig, and fix their material and visibility"
		return ("Fix everything that drifted in the character: parts moved in Object Mode, detached or hidden, "
			"a deleted rig, missing eyes, guides or handles. Never changes the pose, mesh shapes or paint")

	@classmethod
	def poll(cls, context):
		if context.mode != 'OBJECT':
			cls.poll_message_set("Only in Object Mode")
			return False
		return active_character(context) is not None

	def execute(self, context):
		from . import repair

		collection = active_character(context)
		objects = None
		if self.selected:
			objects = [o for o in collection.all_objects if o.select_get()]
			if not objects:
				self.report({'WARNING'}, "Select the parts to fix first.")
				return {'CANCELLED'}
		fixed = repair.repair(collection, objects)
		self.report({'INFO'}, f"Fixed {fixed} problem(s)" if fixed else "Nothing to fix")
		return {'FINISHED'}


class BALLISTICA_OT_fix_issue(bpy.types.Operator):
	"""Fix this problem"""
	bl_idname = 'ballistica.fix_issue'
	bl_label = "Fix"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	kind: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
	name: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
	keep: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

	@classmethod
	def description(cls, context, properties):
		from . import repair

		text = repair.TEXT.get(properties.kind)
		if text is None:
			return cls.__doc__
		if properties.keep:
			return f"Apply the move to {properties.name}'s mesh, so it is exported as it looks now"
		return text[2].format(name=properties.name) + '.'

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT' and active_character(context) is not None

	def execute(self, context):
		from . import repair

		collection = active_character(context)
		issue = next((i for i in repair.issues(collection) if i.kind == self.kind and i.name == self.name), None)
		if issue is None:
			return {'CANCELLED'}
		repair.fix(collection, issue, keep=self.keep)
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
		report_problems(self, problems)
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
		attach_scene.sync_from_handles(collection)
		eye_scene.pull(collection)

		# Meshes: each part's mesh to its export path (unchanged ones skipped).
		part_scene.assign_paths(collection)
		for obj in _exportable_parts(collection):
			_write_mesh(root, getattr(settings, part_scene.FIELDS[obj.ballistica_part.role]), obj, written)
		for row in settings.parts:
			if row.side == 'L' and row.enabled and row.mesh is not None:
				obj = next((o for o in part_scene.objects_of(collection, row) if o.data == row.mesh), None)
				if obj is not None:
					_write_mesh(root, row.mesh.ballistica_asset.path, obj, written)
		# Attachment segments: their meshes and images to their export paths.
		attach_scene.mirror_paths(collection)
		done = set()
		for index, attachment in enumerate(settings.attachments):
			for j, segment in enumerate(attachment.segments):
				if segment.mesh_block is None or segment.mesh in done:
					continue
				obj = next((
					o for o in attach_scene.tagged(collection, attach_scene.MESH, index)
					if o.get(attach_scene.SEGMENT_KEY) == j and o.get(attach_scene.SIDE_KEY) != 'L'), None)
				if obj is not None:
					_write_mesh(root, segment.mesh, obj, written)
					done.add(segment.mesh)

		# Textures: the body's from the Textures list, with their settings;
		# icons and attachment textures by path (edited or made in Blender).
		texture_scene.assign_paths(collection)
		texture_settings = {}
		for item in settings.textures:
			if item.image is not None:
				if texture_scene.is_mask(item) and item.image.ballistica_texture.role not in workspace.DATA_ROLES:
					item.image.ballistica_texture.role = 'data'
				path = _save_image(root, item.image, written)
				texture_settings[path] = props.texture_settings_of(item.image)
		masks = []
		for field, data in (('icon_texture', False), ('icon_mask_texture', True)):
			_save_texture(root, getattr(settings, field), data, written, masks)
		for attachment in settings.attachments:
			for segment in attachment.segments:
				for image, mask in ((segment.texture_block, False), (segment.mask_block, True)):
					if image is None:
						continue
					if mask and image.ballistica_texture.role not in workspace.DATA_ROLES:
						image.ballistica_texture.role = 'data'
					path = _save_image(root, image, written)
					texture_settings[path] = props.texture_settings_of(image)
		changed = workspace.set_texture_settings(root, texture_settings) if texture_settings else False
		if workspace.mark_data_textures(root, masks) or changed:
			written.append(workspace.WORKSPACE_FILE)

		character = props.to_character(settings)
		bchar_path = workspace.file_path(root, settings.character_path, 'character') or workspace.new_file_path(root, settings.character_path, 'character')
		if character.save(bchar_path):
			written.append(os.path.relpath(bchar_path, root))
		settings.raw_json = json.dumps(character.raw)
		for attachment, raw in zip(settings.attachments, character.attachments):
			attachment.raw_json = json.dumps(raw)

		self.report({'INFO'}, f"Wrote {len(written)} file(s)" + (f": {', '.join(written)}" if written else " (nothing changed)"))
		report_problems(self, check(collection))
		return {'FINISHED'}


def _write_mesh(root, logical, obj, written):
	"""Write an object's mesh, modifiers applied, unless unchanged on disk.

	The fingerprint of what was last written is kept on the object's own
	mesh data, so a mesh is skipped while neither it nor its modifiers
	have changed.
	"""
	path = workspace.file_path(root, logical, 'mesh')
	with scene.evaluated_mesh(obj) as mesh:
		signature = scene.mesh_signature(mesh)
		if path is not None and obj.data.get(scene.SIGNATURE_KEY) == signature:
			return  # Unchanged since import or last export.
		path = path or workspace.new_file_path(root, logical, 'mesh')
		os.makedirs(os.path.dirname(path), exist_ok=True)
		objfile.write(path, scene.obj_from_mesh(mesh))
	obj.data[scene.SIGNATURE_KEY] = signature
	written.append(os.path.relpath(path, root))


def _save_image(root, image, written):
	"""Save an image to its export path if it's new, edited or moved; return the file."""
	logical = image.ballistica_texture.path
	path = workspace.file_path(root, logical, 'texture') or workspace.new_file_path(root, logical, 'texture')
	current = os.path.abspath(bpy.path.abspath(image.filepath_raw)) if image.filepath_raw else None
	if image.is_dirty or not os.path.isfile(path) or current != os.path.abspath(path):
		os.makedirs(os.path.dirname(path), exist_ok=True)
		image.file_format = 'PNG'
		if current == os.path.abspath(path):
			image.save()
		else:
			image.save(filepath=path)  # now this image's file
		image[scene.ROOT_KEY] = root
		written.append(os.path.relpath(path, root))
	return path


def _save_texture(root, logical, data, written, masks):
	"""Save an image edited (or made) in Blender to its logical path."""
	if not logical:
		return
	path = workspace.file_path(root, logical, 'texture') or workspace.new_file_path(root, logical, 'texture')
	image = scene.find_image(path)
	exists = os.path.isfile(path)
	if image is not None and (image.is_dirty or not exists):
		os.makedirs(os.path.dirname(path), exist_ok=True)
		image.save()
		written.append(os.path.relpath(path, root))
	elif not exists:
		return
	if data and path not in masks:
		masks.append(path)


def _blocks_in_blender(settings):
	"""(kind, export path) of every mesh and image the character's pickers hold."""
	found = set()
	for row in settings.parts:
		if row.mesh is not None:
			found.add(('mesh', row.mesh.ballistica_asset.path))
	for item in settings.textures:
		if item.image is not None:
			found.add(('texture', item.image.ballistica_texture.path))
	for attachment in settings.attachments:
		for segment in attachment.segments:
			if segment.mesh_block is not None:
				found.add(('mesh', segment.mesh_block.ballistica_asset.path))
			for image in (segment.texture_block, segment.mask_block):
				if image is not None:
					found.add(('texture', image.ballistica_texture.path))
	return found


def remove_character(collection):
	"""Delete a character and the data only it used.

	Objects and collections go first; then the meshes, armatures,
	materials and images they used, each only if nothing else still uses
	it (characters can share images; the bundled node groups are never
	touched). Deleting just the collection would leave the materials'
	tint drivers pointing at nothing.
	"""
	objects = list(collection.all_objects)
	data = {o.data for o in objects if o.data is not None}
	materials = {s.material for o in objects for s in o.material_slots if s.material is not None}
	images = {
		n.image for m in materials if m.node_tree
		for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image is not None
	}
	for obj in objects:
		bpy.data.objects.remove(obj)
	for child in list(collection.children_recursive):
		bpy.data.collections.remove(child)
	bpy.data.collections.remove(collection)
	for block in data:
		if block.users == 0:
			if isinstance(block, bpy.types.Mesh):
				bpy.data.meshes.remove(block)
			elif isinstance(block, bpy.types.Armature):
				bpy.data.armatures.remove(block)
	for material in materials:
		if material.users == 0:
			bpy.data.materials.remove(material)
	for image in images:
		if image.users == 0:
			bpy.data.images.remove(image)


class BALLISTICA_OT_remove_character(bpy.types.Operator):
	"""Delete the active character from this scene, with its objects, meshes and materials (files in the workspace are left alone)"""
	bl_idname = 'ballistica.remove_character'
	bl_label = "Remove Character"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT' and active_character(context) is not None

	def invoke(self, context, event):
		return context.window_manager.invoke_confirm(
			self, event, title=f"Remove {active_character(context).name}?",
			message="Unsaved edits to its meshes and textures in Blender are lost. Workspace files stay.",
			confirm_text="Remove")

	def execute(self, context):
		collection = active_character(context)
		name = collection.name
		remove_character(collection)
		context.scene.ballistica_active_character = None
		self.report({'INFO'}, f"Removed {name}")
		return {'FINISHED'}


class BALLISTICA_OT_select_eye_handle(bpy.types.Operator):
	"""Select the eye handle: move it to move the eyes, scale it to size them, turn it to tilt the eyelids (the other eye mirrors it)"""
	bl_idname = 'ballistica.select_eye_handle'
	bl_label = "Select Eye Handle"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT' and active_character(context) is not None

	def execute(self, context):
		obj = eye_scene.handle(active_character(context))
		if obj is None:
			self.report({'ERROR'}, "This character has no eye handle; Repair adds it.")
			return {'CANCELLED'}
		from .scene import _layer_collections

		for layer in _layer_collections(context.view_layer.layer_collection, obj.users_collection[0]):
			layer.hide_viewport = False  # the Rig group starts hidden
		for other in context.view_layer.objects.selected:
			other.select_set(False)
		obj.select_set(True)
		context.view_layer.objects.active = obj
		return {'FINISHED'}


class BALLISTICA_OT_new_part_mesh(bpy.types.Operator):
	"""Give the selected part a new mesh: a box in the part's size, to model from"""
	bl_idname = 'ballistica.new_part_mesh'
	bl_label = "New Mesh"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		collection = active_character(context)
		if collection is None or context.mode != 'OBJECT':
			return False
		settings = collection.ballistica_character
		return 0 <= settings.active_part_index < len(settings.parts)

	def execute(self, context):
		collection = active_character(context)
		settings = collection.ballistica_character
		row = settings.parts[settings.active_part_index]
		name = f'{collection.name}_left_{row.part}' if row.side == 'L' else f'{collection.name}_{row.part}'
		mesh = part_scene.new_mesh(collection, row.part)
		mesh.name = name
		row.mesh = mesh
		return {'FINISHED'}


class BALLISTICA_OT_new_texture_image(bpy.types.Operator):
	"""Give the selected texture a new blank image to paint: white for the color texture, black (no tint) for the mask"""
	bl_idname = 'ballistica.new_texture_image'
	bl_label = "New Image"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		collection = active_character(context)
		if collection is None:
			return False
		settings = collection.ballistica_character
		return 0 <= settings.active_texture_index < len(settings.textures)

	def execute(self, context):
		collection = active_character(context)
		settings = collection.ballistica_character
		item = settings.textures[settings.active_texture_index]
		item.image = texture_scene.new_image(collection, item.field)
		return {'FINISHED'}


class BALLISTICA_OT_make_unique(bpy.types.Operator):
	"""Give this character its own copy, so editing it doesn't change the other characters using it"""
	bl_idname = 'ballistica.make_unique'
	bl_label = "Make Unique"
	bl_options = {'REGISTER', 'UNDO'}

	kind: bpy.props.EnumProperty(items=[
		('PART', "Part", ""), ('TEXTURE', "Texture", ""),
		('SEGMENT_MESH', "Segment Mesh", ""), ('SEGMENT_TEXTURE', "Segment Texture", ""), ('SEGMENT_MASK', "Segment Mask", ""),
	], options={'HIDDEN', 'SKIP_SAVE'})

	@classmethod
	def poll(cls, context):
		return active_character(context) is not None

	def execute(self, context):
		from . import sharing

		collection = active_character(context)
		settings = collection.ballistica_character
		if self.kind.startswith('SEGMENT'):
			segment = active_segment(collection)
			key = {'SEGMENT_MESH': 'mesh', 'SEGMENT_TEXTURE': 'texture', 'SEGMENT_MASK': 'mask_texture'}[self.kind]
			if segment is None or getattr(segment, props.SEGMENT_BLOCKS[key]) is None:
				return {'CANCELLED'}
			copy = sharing.make_unique_segment(segment, key)
		elif self.kind == 'PART':
			if not 0 <= settings.active_part_index < len(settings.parts) or settings.parts[settings.active_part_index].mesh is None:
				return {'CANCELLED'}
			copy = sharing.make_unique_mesh(collection, settings.parts[settings.active_part_index])
		else:
			if not 0 <= settings.active_texture_index < len(settings.textures) or settings.textures[settings.active_texture_index].image is None:
				return {'CANCELLED'}
			copy = sharing.make_unique_image(collection, settings.textures[settings.active_texture_index])
		self.report({'INFO'}, f"{copy.name} is {collection.name}'s own now")
		return {'FINISHED'}


def active_segment(collection):
	"""The selected segment of the selected attachment, or None."""
	settings = collection.ballistica_character
	if not 0 <= settings.active_attachment_index < len(settings.attachments):
		return None
	attachment = settings.attachments[settings.active_attachment_index]
	if not 0 <= attachment.active_segment_index < len(attachment.segments):
		return None
	return attachment.segments[attachment.active_segment_index]


class BALLISTICA_OT_pick_part_mesh(bpy.types.Operator):
	"""Click an object in the viewport to use its mesh here"""
	bl_idname = 'ballistica.pick_part_mesh'
	bl_label = "Take Mesh From Object"
	bl_options = {'REGISTER', 'UNDO'}

	target: bpy.props.EnumProperty(
		items=[('PART', "Part", "The selected part"), ('SEGMENT', "Segment", "The selected attachment segment")],
		options={'HIDDEN', 'SKIP_SAVE'})

	@classmethod
	def poll(cls, context):
		collection = active_character(context)
		return collection is not None and context.mode == 'OBJECT'

	def invoke(self, context, event):
		context.window.cursor_modal_set('EYEDROPPER')
		context.workspace.status_text_set("Click an object to use its mesh · Esc or right-click: cancel")
		context.window_manager.modal_handler_add(self)
		return {'RUNNING_MODAL'}

	def _finish(self, context):
		context.window.cursor_modal_restore()
		context.workspace.status_text_set(None)

	def modal(self, context, event):
		if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
			self._finish(context)
			return {'CANCELLED'}
		if event.type != 'LEFTMOUSE' or event.value != 'PRESS':
			return {'RUNNING_MODAL'}
		self._finish(context)
		obj = _object_under_mouse(context, event)
		if obj is None or obj.type != 'MESH':
			self.report({'WARNING'}, "No mesh object there.")
			return {'CANCELLED'}
		collection = active_character(context)
		settings = collection.ballistica_character
		if self.target == 'SEGMENT':
			segment = active_segment(collection)
			if segment is None:
				return {'CANCELLED'}
			segment.mesh_block = obj.data
			note, what = part_scene.left_behind_note(obj), "The segment"
		else:
			if not 0 <= settings.active_part_index < len(settings.parts):
				return {'CANCELLED'}
			row = settings.parts[settings.active_part_index]
			note, what = part_scene.use_object_mesh(row, obj), part_scene.label(row)
		self.report({'WARNING'} if note else {'INFO'}, note or f"{what} now uses {obj.data.name}")
		return {'FINISHED'}


def _object_under_mouse(context, event):
	"""The object drawn under the mouse in any 3D viewport, or None."""
	from bpy_extras import view3d_utils

	for area in context.window.screen.areas:
		if area.type != 'VIEW_3D':
			continue
		for region in area.regions:
			if region.type != 'WINDOW':
				continue
			x, y = event.mouse_x - region.x, event.mouse_y - region.y
			if not (0 <= x < region.width and 0 <= y < region.height):
				continue
			rv3d = area.spaces.active.region_3d
			origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, (x, y))
			direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, (x, y))
			hit, _, _, _, obj, _ = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)
			return obj.original if hit else None
	return None


class BALLISTICA_OT_update_character(bpy.types.Operator):
	"""Update this character to the addon's current format (it was made with an older version)"""
	bl_idname = 'ballistica.update_character'
	bl_label = "Update Character"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		collection = active_character(context)
		return context.mode == 'OBJECT' and collection is not None and migrate.needs_update(collection)

	def execute(self, context):
		collection = active_character(context)
		migrate.update(collection)
		self.report({'INFO'}, f"Updated {collection.name}")
		return {'FINISHED'}


class BALLISTICA_OT_new_segment_block(bpy.types.Operator):
	"""Give the selected segment a new mesh (a small box) or a new blank image to paint"""
	bl_idname = 'ballistica.new_segment_block'
	bl_label = "New"
	bl_options = {'REGISTER', 'UNDO'}

	key: bpy.props.EnumProperty(
		items=[('mesh', "Mesh", ""), ('texture', "Texture", ""), ('mask_texture', "Mask", "")], options={'HIDDEN', 'SKIP_SAVE'})

	@classmethod
	def poll(cls, context):
		collection = active_character(context)
		return collection is not None and context.mode == 'OBJECT' and active_segment(collection) is not None

	def execute(self, context):
		from . import attach_ops

		collection = active_character(context)
		segment = active_segment(collection)
		_, index, j = attach_scene._locate(segment)
		path = attach_scene.default_path(collection, index, j, self.key)
		if self.key == 'mesh':
			mesh = attach_ops.placeholder_mesh(collection, path)
			mesh.ballistica_asset.path = attach_scene._free(path, mesh)
			segment.mesh_block = mesh
			return {'FINISHED'}
		image = texture_scene.new_image(collection, 'color_mask_texture' if self.key == 'mask_texture' else 'color_texture')
		image.name = path.rsplit('/', 1)[-1]
		image.ballistica_texture.path = attach_scene._free(path, image)
		setattr(segment, props.SEGMENT_BLOCKS[self.key], image)
		return {'FINISHED'}


class BALLISTICA_OT_paint_texture(bpy.types.Operator):
	"""Paint the selected texture in Texture Paint mode, on the selected part (or the torso)"""
	bl_idname = 'ballistica.paint_texture'
	bl_label = "Paint"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		collection = active_character(context)
		if collection is None:
			return False
		settings = collection.ballistica_character
		index = settings.active_texture_index
		return 0 <= index < len(settings.textures) and settings.textures[index].image is not None

	def execute(self, context):
		from . import paint

		collection = active_character(context)
		settings = collection.ballistica_character
		item = settings.textures[settings.active_texture_index]
		if not paint.start(context, collection, item.image):
			self.report({'ERROR'}, "This character has no body part to paint on.")
			return {'CANCELLED'}
		if texture_scene.is_mask(item):
			paint.use_brush(context, 'ADD_COLOR')
		return {'FINISHED'}


def _mask_brush_items():
	from . import paint

	return [(key, value[0], "") for key, value in paint.BRUSHES.items()]


_MASK_BRUSH_ITEMS = _mask_brush_items()  # dynamic enum items must stay referenced


class BALLISTICA_OT_mask_brush(bpy.types.Operator):
	"""Paint the color mask with this brush"""
	bl_idname = 'ballistica.mask_brush'
	bl_label = "Mask Brush"
	bl_options = {'REGISTER', 'UNDO'}

	brush: bpy.props.EnumProperty(
		items=lambda self, context: _MASK_BRUSH_ITEMS,
		options={'HIDDEN', 'SKIP_SAVE'})

	@classmethod
	def description(cls, context, properties):
		from . import paint

		return paint.BRUSHES[properties.brush][4]

	@classmethod
	def poll(cls, context):
		collection = active_character(context)
		if collection is None:
			return False
		mask = texture_scene.row(collection.ballistica_character, 'color_mask_texture')
		return mask is not None and mask.image is not None

	def execute(self, context):
		from . import paint

		collection = active_character(context)
		mask = texture_scene.row(collection.ballistica_character, 'color_mask_texture')
		if not paint.start(context, collection, mask.image):
			self.report({'ERROR'}, "This character has no body part to paint on.")
			return {'CANCELLED'}
		paint.use_brush(context, self.brush)
		return {'FINISHED'}


class BALLISTICA_OT_toggle_group(bpy.types.Operator):
	"""Show or hide this in the viewport"""
	bl_idname = 'ballistica.toggle_group'
	bl_label = "Toggle Visibility"
	bl_options = {'INTERNAL'}

	collection: bpy.props.StringProperty(options={'HIDDEN'})

	def execute(self, context):
		from .scene import _layer_collections

		collection = bpy.data.collections.get(self.collection)
		layer = next(_layer_collections(context.view_layer.layer_collection, collection), None) if collection else None
		if layer is None:
			return {'CANCELLED'}
		layer.hide_viewport = not layer.hide_viewport
		return {'FINISHED'}


def menu_import(self, context):
	self.layout.operator(BALLISTICA_OT_import_character.bl_idname, text="Ballistica Character (.bchar)")


classes = (
	BALLISTICA_OT_toggle_group,
	BALLISTICA_OT_select_eye_handle,
	BALLISTICA_OT_new_part_mesh,
	BALLISTICA_OT_pick_part_mesh,
	BALLISTICA_OT_new_texture_image,
	BALLISTICA_OT_make_unique,
	BALLISTICA_OT_new_segment_block,
	BALLISTICA_OT_paint_texture,
	BALLISTICA_OT_mask_brush,
	BALLISTICA_OT_update_character,
	BALLISTICA_OT_import_character,
	BALLISTICA_OT_remove_character,
	BALLISTICA_OT_new_character,
	BALLISTICA_OT_standard_colors,
	BALLISTICA_OT_view_character,
	BALLISTICA_OT_reset_parts,
	BALLISTICA_OT_repair,
	BALLISTICA_OT_fix_issue,
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
