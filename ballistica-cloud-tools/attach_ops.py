"""Operators for the Attachments panel: add, remove, reorder, select."""

import bpy

from . import attach_scene, attachments, props
from .ui import active_character

# A placeholder segment: a slim box along the segment's +z, about an
# antenna capsule's size (radius 0.04, length 0.13).
PLACEHOLDER = ((-0.035, -0.035, -0.08), (0.035, 0.035, 0.08))


def placeholder_mesh(collection, logical):
	"""An in-memory box mesh for a new segment; export writes it to `logical`."""
	from . import scene, template

	# UV'd into the head's (untinted) cell of the body atlas.
	mesh = scene.mesh_from_objmesh(template.box(*PLACEHOLDER, cell='head'), logical)
	attach_scene.tag_mesh(mesh, collection.ballistica_character.workspace_root, logical)
	return mesh


def _new_mesh_path(collection):
	taken = {s.mesh for a in collection.ballistica_character.attachments for s in a.segments}
	n = 0
	while f'meshes/{collection.name}_attachment{n}' in taken or bpy.data.meshes.get(f'meshes/{collection.name}_attachment{n}'):
		n += 1
	return f'meshes/{collection.name}_attachment{n}'


def restructure(collection, change):
	"""Change the attachment list, then rebuild every attachment's objects.

	Handles are read back first, before `change` shifts list positions (the
	handles are tagged with the old ones), and not again afterwards.
	"""
	attach_scene.sync_from_handles(collection)
	# Don't follow the active row to objects about to be rebuilt; select
	# the rebuilt ones afterwards instead.
	attach_scene._following = True
	try:
		change(collection.ballistica_character)
	finally:
		attach_scene._following = False
	attach_scene.clear(collection)
	attach_scene.build(collection)
	settings = collection.ballistica_character
	if 0 <= settings.active_attachment_index < len(settings.attachments):
		attach_scene.select(collection, settings.active_attachment_index, None)


class _AttachmentOperator:
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT' and active_character(context) is not None


def _template_items():
	from . import attach_templates

	items = [('EMPTY', "Empty", "A placeholder antenna on the head, to make your own", 'ADD', 0)]
	for number, item in enumerate(attach_templates.TEMPLATES, start=1):
		items.append((item.key, item.label, item.description, item.icon, number))
	return items


_TEMPLATE_ITEMS = _template_items()  # dynamic-free, but keep a reference anyway


def _free_path(collection, kind, base):
	"""`base`, or `base_2`… if a file or something in Blender already uses it."""
	from . import scene, workspace

	root = collection.ballistica_character.workspace_root
	blocks = bpy.data.meshes if kind == 'mesh' else bpy.data.images
	taken = {b.ballistica_asset.path if kind == 'mesh' else b.ballistica_texture.path for b in blocks}
	path, n = base, 2
	while path in taken or workspace.file_path(root, path, kind) or (kind == 'texture' and scene.find_image(workspace.new_file_path(root, path, kind))):
		path, n = f'{base}_{n}', n + 1
	return path


def template_record(collection, item):
	"""Copy a template's meshes and textures into the character; its record."""
	from . import attach_templates, scene
	from .operators import _new_image

	root = collection.ballistica_character.workspace_root
	name = collection.name.split('.')[0]
	count = len(item.segments)
	meshes = []
	for index in range(count):
		base = f'meshes/{name}_{item.key}' + (f'_{index}' if count > 1 else '')
		logical = _free_path(collection, 'mesh', base)
		mesh = scene.mesh_from_obj(attach_templates.obj_path(item.key, index, count), logical)
		attach_scene.tag_mesh(mesh, root, logical)
		meshes.append(logical)
	textures = []
	for is_mask in (False, True):
		logical = _free_path(collection, 'texture', f'textures/{name}_{item.key}' + ('_mask' if is_mask else ''))
		source = bpy.data.images.load(attach_templates.texture_path(item.key, is_mask))
		try:
			if is_mask:
				source.colorspace_settings.name = 'Non-Color'
			width, height = source.size
			pixels = [0.0] * (width * height * 4)
			source.pixels.foreach_get(pixels)
		finally:
			bpy.data.images.remove(source)
		_new_image(root, logical, pixels, width, data=is_mask, height=height)
		textures.append(logical)
	return item.record(meshes, *textures)


class BALLISTICA_OT_attachment_add(_AttachmentOperator, bpy.types.Operator):
	"""Add an attachment: a ready-made one (hat, tail, wings…) or an empty placeholder to make your own"""
	bl_idname = 'ballistica.attachment_add'
	bl_label = "Add Attachment"

	template: bpy.props.EnumProperty(
		name="Template", items=_TEMPLATE_ITEMS, default='EMPTY', options={'SKIP_SAVE'},
		description="What to add")

	@classmethod
	def description(cls, context, properties):
		return next((i[2] for i in _TEMPLATE_ITEMS if i[0] == properties.template), cls.__doc__)

	def execute(self, context):
		from . import attach_templates

		collection = active_character(context)
		settings = collection.ballistica_character
		if self.template != 'EMPTY':
			record = template_record(collection, attach_templates.BY_KEY[self.template])
		else:
			logical = _new_mesh_path(collection)
			placeholder_mesh(collection, logical)
			record = attachments.new_attachment('head', 'antenna', logical)
			record['translate'] = (0.0, 0.25, 0.0)  # on top of the head
			record['rotate'] = (0.0, 90.0, 0.0)  # pointing up

		def add(settings):
			props.set_attachment(settings.attachments.add(), record)
			settings.active_attachment_index = len(settings.attachments) - 1

		restructure(collection, add)
		return {'FINISHED'}


class BALLISTICA_OT_attachment_remove(_AttachmentOperator, bpy.types.Operator):
	"""Remove the selected attachment (its files in the workspace are left alone)"""
	bl_idname = 'ballistica.attachment_remove'
	bl_label = "Remove Attachment"

	@classmethod
	def poll(cls, context):
		collection = active_character(context)
		return super().poll(context) and len(collection.ballistica_character.attachments) > 0

	def execute(self, context):
		collection = active_character(context)
		index = collection.ballistica_character.active_attachment_index

		def remove(settings):
			settings.attachments.remove(index)
			settings.active_attachment_index = max(min(index, len(settings.attachments) - 1), 0)

		restructure(collection, remove)
		return {'FINISHED'}


class BALLISTICA_OT_attachment_move(_AttachmentOperator, bpy.types.Operator):
	"""Move the selected attachment up or down the list"""
	bl_idname = 'ballistica.attachment_move'
	bl_label = "Move Attachment"

	direction: bpy.props.EnumProperty(items=(('UP', "Up", ""), ('DOWN', "Down", "")))

	def execute(self, context):
		collection = active_character(context)
		settings = collection.ballistica_character
		index = settings.active_attachment_index
		target = index - 1 if self.direction == 'UP' else index + 1
		if not 0 <= target < len(settings.attachments):
			return {'CANCELLED'}
		def move(settings):
			settings.attachments.move(index, target)
			settings.active_attachment_index = target

		restructure(collection, move)
		return {'FINISHED'}


class BALLISTICA_OT_attachment_select(_AttachmentOperator, bpy.types.Operator):
	"""Select the attachment's placement handle (its anchor, or a segment's handle) to move it in the viewport"""
	bl_idname = 'ballistica.attachment_select'
	bl_label = "Select Handle"

	segment: bpy.props.IntProperty(default=-1, options={'SKIP_SAVE'})

	def execute(self, context):
		collection = active_character(context)
		index = collection.ballistica_character.active_attachment_index
		obj = attach_scene.anchor(collection, index) if self.segment < 0 else attach_scene.handle(collection, index, self.segment)
		if obj is None:
			self.report({'ERROR'}, "This attachment has no handle; Repair rebuilds it.")
			return {'CANCELLED'}
		rig_group = obj.users_collection[0]
		_show(context.view_layer.layer_collection, rig_group)
		obj.hide_set(False)
		for other in context.view_layer.objects:
			other.select_set(False)
		obj.select_set(True)
		context.view_layer.objects.active = obj
		return {'FINISHED'}


def _show(layer, collection):
	"""Make `collection`'s layer visible (the Rig group is hidden by default)."""
	if layer.collection == collection:
		layer.hide_viewport = False
		return True
	return any(_show(child, collection) for child in layer.children)


classes = (
	BALLISTICA_OT_attachment_add,
	BALLISTICA_OT_attachment_remove,
	BALLISTICA_OT_attachment_move,
	BALLISTICA_OT_attachment_select,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	attach_scene.register()


def unregister():
	attach_scene.unregister()
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
