"""Import, export and check characters in a local workspace folder."""

import json
import os

import bpy
from bpy_extras.io_utils import ImportHelper

from . import bchar, objfile, pose, props, rig, scene, workspace
from .ui import active_character


def _build(context, root, character_path, character):
	"""Create the whole character scene; return its collection."""
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
		path = workspace.file_path(root, logical, 'mesh')
		if path is None:
			missing.append(logical)
			continue
		right = _part_object(groups[scene.PART_GROUPS[part]], f'{part}.R' if part in rig.PAIRED_PARTS else part, scene.mesh_from_obj(path, logical), part, body_material)
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
	return collection, missing


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
		from . import nodegroup
		try:
			nodegroup.get()  # Before building anything, so a broken install leaves no half-built scene.
		except (nodegroup.MissingAssetError, OSError) as exc:
			self.report({'ERROR'}, str(exc))
			return {'CANCELLED'}
		if context.object is not None and context.object.mode != 'OBJECT':
			bpy.ops.object.mode_set(mode='OBJECT')
		collection, missing = _build(context, root, workspace.logical_path(root, self.filepath), character)
		if missing:
			self.report({'WARNING'}, f"Missing meshes: {', '.join(missing)}")
		else:
			self.report({'INFO'}, f"Imported {collection.name}")
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
		if field not in exported and workspace.file_path(root, logical, kind) is None:
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
	"""Right-side and center part objects (left limbs mirror the right)."""
	for obj in collection.all_objects:
		part = obj.ballistica_part
		if obj.type == 'MESH' and part.role in rig.ATTACH_TARGETS and part.side != 'L':
			yield obj


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

		# Textures: save images edited in Blender back as PNG.
		masks = []
		for field, data in (('color_texture', False), ('color_mask_texture', True)):
			logical = getattr(settings, field)
			path = workspace.file_path(root, logical, 'texture') if logical else None
			if path is None:
				continue
			image = next((i for i in bpy.data.images if i.filepath and os.path.abspath(bpy.path.abspath(i.filepath)) == os.path.abspath(path)), None)
			if image is not None and image.is_dirty:
				image.save()
				written.append(os.path.relpath(path, root))
			if data:
				masks.append(path)
		icon_mask = workspace.file_path(root, settings.icon_mask_texture, 'texture') if settings.icon_mask_texture else None
		if icon_mask:
			masks.append(icon_mask)
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
