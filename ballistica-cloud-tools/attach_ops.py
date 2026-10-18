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
	change(collection.ballistica_character)
	attach_scene.clear(collection)
	attach_scene.build(collection)


class _AttachmentOperator:
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT' and active_character(context) is not None


class BALLISTICA_OT_attachment_add(_AttachmentOperator, bpy.types.Operator):
	"""Add an attachment: a placeholder antenna on the head"""
	bl_idname = 'ballistica.attachment_add'
	bl_label = "Add Attachment"

	def execute(self, context):
		collection = active_character(context)
		settings = collection.ballistica_character
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
			self.report({'ERROR'}, "This attachment has no handle; check its mesh.")
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
