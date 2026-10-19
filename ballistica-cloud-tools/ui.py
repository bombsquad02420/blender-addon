"""Sidebar panel (View3D > N panel > Ballistica), laid out like the web UI."""

import bpy

from . import rig


def characters(scene):
	"""Character collections in this scene, in outliner order."""
	return [c for c in scene.collection.children_recursive if c.ballistica_character.is_character]


def active_character(context):
	"""The character the panel shows and acts on.

	The scene's chosen character (the list at the top of the panel), else
	the character of the active object or collection (files from before
	the list), else the scene's first character.
	"""
	scene = context.scene
	chosen = getattr(scene, 'ballistica_active_character', None)
	if chosen is not None and chosen.ballistica_character.is_character and chosen in characters(scene):
		return chosen
	found = _character_from_selection(context)
	if found is not None:
		return found
	return next(iter(characters(scene)), None)


def _character_from_selection(context):
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


class BALLISTICA_UL_characters(bpy.types.UIList):
	"""The scene's characters (character collections from bpy.data)."""

	def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
		layout.label(text=item.name, icon='OUTLINER_COLLECTION')

	def filter_items(self, context, data, property):
		in_scene = set(characters(context.scene))
		items = getattr(data, property)
		flags = [self.bitflag_filter_item if c in in_scene else 0 for c in items]
		if self.filter_name:
			needle = self.filter_name.lower()
			flags = [f if needle in c.name.lower() else 0 for f, c in zip(flags, items)]
		return flags, []


class VIEW3D_PT_ballistica_character(_Panel, bpy.types.Panel):
	bl_label = "Ballistica Character"

	def draw(self, context):
		layout = self.layout
		layout.template_list(
			'BALLISTICA_UL_characters', '', bpy.data, 'collections', context.scene, 'ballistica_character_index',
			rows=2, maxrows=5)
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
	# Flippers sits with the arm meshes it describes.
	fields = tuple(
		name for _, field, _ in rig.PARTS
		for name in ((field, 'flippers') if field == 'upper_arm_mesh' else (field,))
	)

	def draw(self, context):
		_Section.draw(self, context)
		settings = active_character(context).ballistica_character
		header, body = self.layout.panel('BALLISTICA_meshes_left', default_closed=True)
		header.label(text="Left Side")
		if body is not None:
			body.use_property_split = True
			body.use_property_decorate = False
			body.label(text="Own meshes for the left limbs (still authored as right-side parts).")
			for part in rig.PAIRED_PARTS:
				body.prop(settings, f'left_{part}_mesh')


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

		# Collapsible sub-sections (layout panels remember open/closed per
		# id, so each attachment field group keeps its state).
		header, body = layout.panel('BALLISTICA_attach_placement', default_closed=False)
		header.label(text="Placement", icon='EMPTY_ARROWS')
		if body is not None:
			_split(body)
			body.label(text="Where it hangs on the target part (game axes: Y up, Z forward).")
			body.operator('ballistica.attachment_select', text="Select Anchor", icon='RESTRICT_SELECT_OFF').segment = -1
			body.prop(attachment, 'translate')
			body.prop(attachment, 'rotate', text="Heading, Pitch, Roll")

		if attachments.is_springy(attachment.kind):
			header, body = layout.panel('BALLISTICA_attach_spring', default_closed=True)
			header.label(text="Spring", icon='FORCE_HARMONIC')
			if body is not None:
				_split(body)
				for field in attachments.TUNING:
					body.prop(attachment, field)
				if attachments.segment_count(attachment.kind) > 1:
					body.label(text="Change per segment")
					for field in attachments.TUNING_CHANGES:
						body.prop(attachment, field)

		header, body = layout.panel('BALLISTICA_attach_segments', default_closed=False)
		header.label(text=f"Segments ({len(attachment.segments)})", icon='MESH_DATA')
		if body is None:
			return
		body.template_list(
			'BALLISTICA_UL_segments', '', attachment, 'segments', attachment, 'active_segment_index',
			rows=1, maxrows=4)
		j = attachment.active_segment_index
		if not 0 <= j < len(attachment.segments):
			return
		segment = attachment.segments[j]
		col = body.column()
		_split(col)
		col.prop(segment, 'mesh')
		col.prop(segment, 'texture')
		col.prop(segment, 'mask_texture')
		header, art = body.panel('BALLISTICA_attach_art', default_closed=True)
		header.label(text="Art Offset")
		if art is not None:
			_split(art)
			art.label(text="Moves the mesh on its segment; use Placement to move the attachment.")
			art.operator('ballistica.attachment_select', text="Select Art", icon='RESTRICT_SELECT_OFF').segment = j
			art.prop(segment, 'translate')
			art.prop(segment, 'rotate', text="Heading, Pitch, Roll")
			art.prop(segment, 'scale')


def _split(layout):
	layout.use_property_split = True
	layout.use_property_decorate = False


def _triangles(collection):
	total = 0
	for obj in collection.all_objects:
		if obj.type == 'MESH' and obj.ballistica_part.role not in ('guide', 'eye', 'NONE'):
			total += sum(len(p.vertices) - 2 for p in obj.data.polygons)
	return total


classes = (
	BALLISTICA_UL_characters,
	VIEW3D_PT_ballistica_character,
	VIEW3D_PT_ballistica_visibility,
	VIEW3D_PT_ballistica_identity,
	VIEW3D_PT_ballistica_textures,
	VIEW3D_PT_ballistica_meshes,
	VIEW3D_PT_ballistica_sounds,
	VIEW3D_PT_ballistica_physique,
	VIEW3D_PT_ballistica_eyes,
	VIEW3D_PT_ballistica_surface,
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
