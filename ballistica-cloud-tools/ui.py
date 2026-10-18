"""Sidebar panel (View3D > N panel > Ballistica), laid out like the web UI."""

import bpy

from . import rig


def active_character(context):
	"""The character collection for the active object or collection."""
	obj = context.active_object
	if obj is not None:
		for collection in obj.users_collection:
			if collection.ballistica_character.is_character:
				return collection
			for parent in bpy.data.collections:
				if collection.name in parent.children and parent.ballistica_character.is_character:
					return parent
	layer = context.view_layer.active_layer_collection
	if layer is not None and layer.collection.ballistica_character.is_character:
		return layer.collection
	return None


class _Panel:
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "Ballistica"


class VIEW3D_PT_ballistica_character(_Panel, bpy.types.Panel):
	bl_label = "Ballistica Character"

	def draw(self, context):
		layout = self.layout
		row = layout.row(align=True)
		row.operator('ballistica.new_character', icon='ADD')
		row.operator('ballistica.import_character', icon='IMPORT')
		row.operator('ballistica.export_character', icon='EXPORT')
		collection = active_character(context)
		if collection is None:
			layout.label(text="Import a .bchar or start a new character.", icon='INFO')
			return
		settings = collection.ballistica_character
		col = layout.column(align=True)
		col.label(text=collection.name, icon='OUTLINER_COLLECTION')
		col.prop(settings, 'workspace_root', text="")
		col.prop(settings, 'character_path', text="")
		row = layout.row(align=True)
		row.label(text=f"{_triangles(collection):,} triangles")
		row.operator('ballistica.check_character', icon='CHECKMARK')
		row = layout.row(align=True)
		row.operator('ballistica.view_character', icon='ZOOM_SELECTED')
		row.operator('ballistica.reset_parts', icon='LOOP_BACK')
		row.operator('ballistica.standard_colors', icon='COLOR')
		layout.prop(settings, 'show_all_assets')


# Button order in the Visibility grid (first column, then second).
VISIBILITY_ORDER = ('Head', 'Body', 'Arms', 'Legs', 'Attachments', 'Eyes', 'Rig', 'Guides')


class VIEW3D_PT_ballistica_visibility(_Panel, bpy.types.Panel):
	"""Viewport visibility of the character's child collections."""
	bl_label = "Visibility"
	bl_parent_id = 'VIEW3D_PT_ballistica_character'

	@classmethod
	def poll(cls, context):
		return active_character(context) is not None

	def draw(self, context):
		from .scene import _layer_collections

		collection = active_character(context)
		self.layout.prop(collection.ballistica_character, 'spread', slider=True)
		# Filled column by column: body groups on the left, the rest on the right.
		grid = self.layout.grid_flow(row_major=False, columns=2, even_columns=True, align=True)
		prefix = collection.name + ' '
		buttons = []
		for child in collection.children:
			layer = next(_layer_collections(context.view_layer.layer_collection, child), None)
			if layer is not None:
				label = child.name[len(prefix):] if child.name.startswith(prefix) else child.name
				buttons.append((label, layer))
		order = {label: i for i, label in enumerate(VISIBILITY_ORDER)}
		buttons.sort(key=lambda button: order.get(button[0], len(order)))  # stable: others keep their order
		for label, layer in buttons:
			# The button is pressed while the collection is visible.
			grid.prop(layer, 'hide_viewport', text=label, toggle=True, invert_checkbox=True)


class _Section(_Panel):
	bl_parent_id = 'VIEW3D_PT_ballistica_character'
	bl_options = {'DEFAULT_CLOSED'}
	fields = ()

	@classmethod
	def poll(cls, context):
		return active_character(context) is not None

	def draw(self, context):
		settings = active_character(context).ballistica_character
		layout = self.layout
		layout.use_property_split = True
		layout.use_property_decorate = False
		for field in self.fields:
			layout.prop(settings, field)


class VIEW3D_PT_ballistica_identity(_Section, bpy.types.Panel):
	bl_label = "Identity"
	bl_options = set()
	fields = (
		'name', 'icon_texture', 'icon_mask_texture', 'color', 'highlight',
		'highlight_name', 'highlight_editing', 'highlight2', 'highlight2_name', 'highlight2_editing',
	)


class VIEW3D_PT_ballistica_textures(_Section, bpy.types.Panel):
	bl_label = "Textures"
	fields = ('color_texture', 'color_mask_texture')


class VIEW3D_PT_ballistica_meshes(_Section, bpy.types.Panel):
	bl_label = "Meshes"
	fields = tuple(field for _, field, _ in rig.PARTS)


class VIEW3D_PT_ballistica_sounds(_Section, bpy.types.Panel):
	bl_label = "Sounds"
	fields = rig.SOUND_FIELDS


class VIEW3D_PT_ballistica_physique(_Section, bpy.types.Panel):
	bl_label = "Physique"
	fields = (
		'torso_radius', 'shoulder_offset', 'thigh_radius', 'ankle_radius',
		'step_separation', 'idle_arm_stiffness', 'arm_swing', 'idle_sway',
	)


class VIEW3D_PT_ballistica_eyes(_Section, bpy.types.Panel):
	bl_label = "Eyes"
	fields = (
		'eye_style_left', 'eye_style_right', 'eye_scale', 'eye_offset',
		'eye_color', 'eyeball_color', 'eyelid_color', 'eyelid_angle',
	)


class VIEW3D_PT_ballistica_surface(_Section, bpy.types.Panel):
	bl_label = "Surface"
	fields = ('reflection_scale',)


class VIEW3D_PT_ballistica_advanced(_Section, bpy.types.Panel):
	bl_label = "Advanced"
	fields = ('flippers', *(f'left_{p}_mesh' for p in rig.PAIRED_PARTS))



class BALLISTICA_UL_attachments(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
		from . import attachments

		sides = '' if item.target in rig.UNSIDED_TARGETS else f' · {item.side}'
		label = f"{item.target.replace('_', ' ')} · {item.kind.replace('_', ' ')}{sides}"
		problems = attachments.problems(_record(item))
		layout.label(text=label, icon='ERROR' if problems else 'LINKED')


class BALLISTICA_UL_segments(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
		layout.label(text=f"{index + 1}: {item.mesh or '(no mesh)'}", icon='MESH_DATA' if item.mesh else 'ERROR')


def _record(attachment):
	from . import props

	return props.attachment_record(attachment)


class VIEW3D_PT_ballistica_attachments(_Section, bpy.types.Panel):
	bl_label = "Attachments"

	def draw(self, context):
		from . import attachments

		collection = active_character(context)
		settings = collection.ballistica_character
		layout = self.layout
		row = layout.row()
		row.template_list(
			'BALLISTICA_UL_attachments', '', settings, 'attachments', settings, 'active_attachment_index', rows=3)
		col = row.column(align=True)
		col.operator('ballistica.attachment_add', icon='ADD', text="")
		col.operator('ballistica.attachment_remove', icon='REMOVE', text="")
		col.separator()
		col.operator('ballistica.attachment_move', icon='TRIA_UP', text="").direction = 'UP'
		col.operator('ballistica.attachment_move', icon='TRIA_DOWN', text="").direction = 'DOWN'

		index = settings.active_attachment_index
		if not 0 <= index < len(settings.attachments):
			return
		attachment = settings.attachments[index]
		for problem in attachments.problems(_record(attachment), index):
			layout.label(text=problem, icon='ERROR')

		col = layout.column()
		col.use_property_split = True
		col.use_property_decorate = False
		col.prop(attachment, 'target')
		col.prop(attachment, 'side')
		col.prop(attachment, 'kind')

		box = layout.box()
		header = box.row()
		header.label(text="Placement on the target part", icon='EMPTY_ARROWS')
		header.operator('ballistica.attachment_select', text="Select", icon='RESTRICT_SELECT_OFF').segment = -1
		box.use_property_split = True
		box.use_property_decorate = False
		box.prop(attachment, 'translate')
		box.prop(attachment, 'rotate', text="Rotate (H, P, R)")

		if attachments.is_springy(attachment.kind):
			box = layout.box()
			box.label(text="Spring", icon='FORCE_HARMONIC')
			box.use_property_split = True
			box.use_property_decorate = False
			for field in attachments.TUNING:
				box.prop(attachment, field)
			if attachments.segment_count(attachment.kind) > 1:
				box.label(text="Change per segment")
				for field in attachments.TUNING_CHANGES:
					box.prop(attachment, field)

		layout.label(text="Segments")
		layout.template_list(
			'BALLISTICA_UL_segments', '', attachment, 'segments', attachment, 'active_segment_index',
			rows=1, maxrows=4)
		j = attachment.active_segment_index
		if 0 <= j < len(attachment.segments):
			segment = attachment.segments[j]
			col = layout.column()
			col.use_property_split = True
			col.use_property_decorate = False
			col.prop(segment, 'mesh')
			col.prop(segment, 'texture')
			col.prop(segment, 'mask_texture')
			row = col.row()
			row.label(text="Art on the segment")
			row.operator('ballistica.attachment_select', text="Select", icon='RESTRICT_SELECT_OFF').segment = j
			col.prop(segment, 'translate')
			col.prop(segment, 'rotate', text="Rotate (H, P, R)")
			col.prop(segment, 'scale')


classes = (
	VIEW3D_PT_ballistica_character,
	VIEW3D_PT_ballistica_visibility,
	VIEW3D_PT_ballistica_identity,
	VIEW3D_PT_ballistica_textures,
	VIEW3D_PT_ballistica_meshes,
	VIEW3D_PT_ballistica_sounds,
	VIEW3D_PT_ballistica_physique,
	VIEW3D_PT_ballistica_eyes,
	VIEW3D_PT_ballistica_surface,
	VIEW3D_PT_ballistica_advanced,
	BALLISTICA_UL_attachments,
	BALLISTICA_UL_segments,
	VIEW3D_PT_ballistica_attachments,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
