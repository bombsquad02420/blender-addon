"""Sidebar panel (View3D > N panel > Ballistica), laid out like the web UI."""

import bpy

from . import rig


def characters(scene):
	"""Character collections in this scene, in outliner order."""
	return [c for c in scene.collection.children_recursive if c.ballistica_character.is_character]


def active_character(context):
	"""The character the panel shows and acts on.

	The scene's chosen character (the list at the top of the panel), else
	the character of the active object or collection (none chosen yet, or
	the chosen one was deleted), else the scene's first character.
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
		from .scene import _layer_collections

		row = layout.row(align=True)
		row.label(text=item.name, icon='OUTLINER_COLLECTION')
		layer = next(_layer_collections(context.view_layer.layer_collection, item), None)
		if layer is not None:
			visible = not layer.hide_viewport
			op = row.operator('ballistica.toggle_group', text="", icon='HIDE_OFF' if visible else 'HIDE_ON', emboss=False)
			op.collection = item.name

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
		row = layout.row()
		row.template_list(
			'BALLISTICA_UL_characters', '', bpy.data, 'collections', context.scene, 'ballistica_character_index',
			rows=2, maxrows=5)
		col = row.column(align=True)
		col.operator('ballistica.new_character', icon='ADD', text="")
		col.operator('ballistica.remove_character', icon='REMOVE', text="")
		row = layout.row(align=True)
		row.operator('ballistica.import_character', icon='IMPORT')
		row.operator('ballistica.export_character', icon='EXPORT')
		collection = active_character(context)
		if collection is None:
			layout.label(text="Import a .bchar, or + to start a new character.", icon='INFO')
			return
		settings = collection.ballistica_character
		from . import migrate

		if migrate.needs_update(collection):
			box = layout.box()
			box.label(text="Made with an older version of the addon.", icon='INFO')
			box.operator('ballistica.update_character', icon='FILE_REFRESH')
			return
		col = layout.column(align=True)
		col.label(text=collection.name, icon='OUTLINER_COLLECTION')
		col.prop(settings, 'workspace_root', text="")
		col.prop(settings, 'character_path', text="")
		row = layout.row(align=True)
		row.label(text=f"{_triangles(collection):,} triangles")
		row.operator('ballistica.check_character', icon='CHECKMARK')
		_repair_box(layout, collection)


# Problems listed in the Needs fixing box before "and N more".
SHOWN_ISSUES = 4


def _repair_box(layout, collection):
	"""What drifted in the scene, each with its fix, and the Repair buttons."""
	from . import repair

	issues = repair.issues(collection)
	if issues:
		box = layout.box()
		box.label(text=f"Needs fixing ({len(issues)})", icon='ERROR')
		for issue in issues[:SHOWN_ISSUES]:
			row = box.row(align=True)
			row.label(text=issue.label)
			op = row.operator('ballistica.fix_issue', text=issue.button)
			op.kind, op.name = issue.kind, issue.name
			if issue.keepable:
				op = row.operator('ballistica.fix_issue', text="Keep")
				op.kind, op.name, op.keep = issue.kind, issue.name, True
		if len(issues) > SHOWN_ISSUES:
			box.label(text=f"and {len(issues) - SHOWN_ISSUES} more")
		box.operator('ballistica.repair', text="Fix All", icon='TOOL_SETTINGS')
	row = layout.row(align=True)
	row.operator('ballistica.repair', text="Fix Selected", icon='RESTRICT_SELECT_OFF').selected = True
	row.operator('ballistica.repair', text="Fix Whole Character", icon='TOOL_SETTINGS').selected = False


# Button order in the Visibility grid (first column, then second).
VISIBILITY_ORDER = ('Head', 'Body', 'Arms', 'Legs', 'Attachments', 'Eyes', 'Rig', 'Guides')


class VIEW3D_PT_ballistica_visibility(_Panel, bpy.types.Panel):
	"""Viewport visibility of the character's child collections."""
	bl_label = "Visibility"
	bl_parent_id = 'VIEW3D_PT_ballistica_character'
	header_icon = 'RESTRICT_VIEW_OFF'

	@classmethod
	def poll(cls, context):
		return _current_character(context) is not None

	def draw_header(self, context):
		self.layout.label(icon=self.header_icon)

	def draw(self, context):
		from .scene import _layer_collections

		collection = active_character(context)
		row = self.layout.row(align=True)
		row.operator('ballistica.view_character', icon='ZOOM_SELECTED')
		row.operator('ballistica.reset_parts', icon='LOOP_BACK')
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
			# Pressed, with an open eye, while the collection is visible (as in
			# the outliner). An operator button, because a property toggle
			# shows the next icon while on, so it can't be pressed and show
			# an open eye at the same time.
			visible = not layer.hide_viewport
			op = grid.operator(
				'ballistica.toggle_group', text=label, icon='HIDE_OFF' if visible else 'HIDE_ON', depress=visible)
			op.collection = layer.collection.name


def _group_toggles(layout, context, collection, groups):
	"""Show/hide buttons for some of the character's groups, as in Visibility."""
	from .scene import _layer_collections, group

	row = layout.row(align=True)
	for name in groups:
		child = group(collection, name)
		layer = next(_layer_collections(context.view_layer.layer_collection, child), None) if child else None
		if layer is None:
			continue
		visible = not layer.hide_viewport
		op = row.operator(
			'ballistica.toggle_group', text=name,
			icon='HIDE_OFF' if visible else 'HIDE_ON', depress=visible)
		op.collection = child.name


def _current_character(context):
	"""The active character, if it's in the current format (else only Update shows)."""
	from . import migrate

	collection = active_character(context)
	return collection if collection is not None and not migrate.needs_update(collection) else None


class _Section(_Panel):
	bl_parent_id = 'VIEW3D_PT_ballistica_character'
	bl_options = {'DEFAULT_CLOSED'}
	fields = ()
	header_icon = 'NONE'

	def draw_header(self, context):
		self.layout.label(icon=self.header_icon)

	@classmethod
	def poll(cls, context):
		return _current_character(context) is not None

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
	header_icon = 'USER'
	# Who it is: its name and its menu icon. (Its colors are in Textures.)
	groups = (
		('name', 'icon_texture', 'icon_mask_texture'),
	)
	fields = tuple(f for group in groups for f in group)

	def draw(self, context):
		settings = active_character(context).ballistica_character
		layout = self.layout
		layout.use_property_split = True
		layout.use_property_decorate = False
		for i, group in enumerate(self.groups):
			if i:
				layout.separator()
			col = layout.column(align=True)
			for field in group:
				col.prop(settings, field)


def _standard_colors_note(layout, context):
	"""Whether the viewport shows colors as the game does, with the fix."""
	from .operators import uses_standard_colors

	if uses_standard_colors(context.scene):
		return  # nothing to fix
	box = layout.box()
	box.label(text="Blender's default view transform washes colors out.", icon='INFO')
	box.operator('ballistica.standard_colors', icon='COLOR')


def _colors(layout, context, settings):
	"""The character's tints and reflection, above the textures they color."""
	header, body = layout.panel('BALLISTICA_texture_colors', default_closed=False)
	header.label(text="Colors", icon='COLOR')
	if body is None:
		return
	row = body.row(align=True)
	for label, field in (("Player Color", 'color'), ("Highlight", 'highlight'), ("Highlight 2", 'highlight2')):
		col = row.column(align=True)
		col.label(text=label)
		col.prop(settings, field, text="")
	body.prop(settings, 'reflection_scale', slider=True)
	header, profile = body.panel('BALLISTICA_texture_profile', default_closed=True)
	header.label(text="Profile Editor")
	if profile is not None:
		_split(profile)
		for field in ('highlight_name', 'highlight_editing', 'highlight2_name', 'highlight2_editing'):
			profile.prop(settings, field)
	_standard_colors_note(body, context)


def _shared_note(layout, block, collection, kind):
	"""'Used by N characters' with Make Unique, when another character uses it too."""
	from . import sharing

	users = sharing.users(block)
	if len(users) < 2:
		return
	row = layout.row(align=True)
	others = ', '.join(c.name for c in users if c != collection)
	row.label(text=f"Also used by {others}", icon='LINKED')
	row.operator('ballistica.make_unique', text="Make Unique").kind = kind


def _paint_box(layout, context, item, image):
	"""Paint the selected texture; for the mask, its channel brushes."""
	from . import paint, texture_scene

	box = layout.box()
	painting = context.mode == 'PAINT_TEXTURE'
	canvas = context.scene.tool_settings.image_paint.canvas
	row = box.row(align=True)
	label = "Painting" if painting and canvas == image else "Paint"
	row.operator('ballistica.paint_texture', text=label, icon='BRUSH_DATA', depress=painting and canvas == image)
	if painting:
		row.operator('object.mode_set', text="Done", icon='OBJECT_DATA').mode = 'OBJECT'
	if painting and canvas == image:
		box.label(text="Tip: paints on the selected part; pick others in Parts.", icon='INFO')
	if not texture_scene.is_mask(item) or not (painting and canvas == image):
		return  # the mask brushes only while painting the mask
	unified = context.scene.tool_settings.image_paint.unified_paint_settings
	box.prop(unified, 'use_unified_color', text="Shared Brush Color")
	if unified.use_unified_color:
		warning = box.column(align=True)
		warning.label(text="Brushes picked from the shelf will paint the shared", icon='ERROR')
		warning.label(text="color, not their tint. Turn Shared Brush Color off.", icon='BLANK1')
	brush = context.scene.tool_settings.image_paint.brush if painting else None

	def button(layout, key, text, icon):
		active = brush is not None and brush.name == paint.PREFIX + paint.BRUSHES[key][0]
		layout.operator('ballistica.mask_brush', text=text, icon=icon, depress=active).brush = key

	col = box.column(align=True)
	for tint, (tint_name, _) in paint.TINTS.items():
		split = col.split(factor=0.38, align=True)
		split.label(text=tint_name)
		row = split.row(align=True)
		button(row, f'ADD_{tint}', "Add", 'ADD')
		button(row, f'ERASE_{tint}', "Erase", 'REMOVE')
		button(row, f'ONLY_{tint}', "Only", 'SNAP_FACE')
	# Erasing every tint is one more brush: the Erase column's last row.
	split = col.split(factor=0.38, align=True)
	split.label(text="All Tints")
	row = split.row(align=True)
	row.label(text="")
	button(row, 'ERASE_ALL', "Erase", 'REMOVE')
	row.label(text="")


class BALLISTICA_UL_textures(bpy.types.UIList):
	"""The body's two textures: color and color mask."""

	def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
		from . import texture_scene

		row = layout.row()
		row.label(text=texture_scene.LABELS[item.field], icon='IMAGE_DATA' if item.image else 'ERROR')
		sub = row.row()
		sub.active = False
		sub.label(text=item.image.name if item.image else "(none)")


class VIEW3D_PT_ballistica_textures(_Section, bpy.types.Panel):
	bl_label = "Textures"
	header_icon = 'TEXTURE'

	def draw(self, context):
		from . import texture_scene, workspace

		collection = active_character(context)
		settings = collection.ballistica_character
		layout = self.layout
		_colors(layout, context, settings)
		layout.template_list(
			'BALLISTICA_UL_textures', '', settings, 'textures', settings, 'active_texture_index', rows=2, maxrows=2)
		index = settings.active_texture_index
		if not 0 <= index < len(settings.textures):
			return
		item = settings.textures[index]
		col = layout.column()
		_split(col)
		line = col.row(align=True)
		line.prop(item, 'image')
		line.operator('ballistica.new_texture_image', text="", icon='ADD')
		image = item.image
		if image is None:
			return
		_paint_box(layout, context, item, image)
		_shared_note(col, image, collection, 'TEXTURE')
		texture = image.ballistica_texture
		col.prop(texture, 'path', placeholder=texture_scene.default_path(collection, item.field))
		header, body = layout.panel('BALLISTICA_texture_settings', default_closed=True)
		header.label(text="Build Settings")
		if body is not None:
			_split(body)
			body.prop(texture, 'role')
			if texture_scene.is_mask(item) and texture.role not in workspace.DATA_ROLES:
				body.label(text="Masks need a Data role (export sets it).", icon='ERROR')
			for name in ('quality', 'wrap_h', 'wrap_v', 'alpha'):
				body.prop(texture, name)


class BALLISTICA_UL_parts(bpy.types.UIList):
	"""The body parts, in rig order; optional ones can be turned off."""

	def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
		from . import part_scene

		row = layout.row(align=True)
		if part_scene.is_optional(item):
			row.prop(item, 'enabled', text="")
		else:
			row.label(text="", icon='CHECKBOX_HLT')  # always used
		sub = row.row()
		sub.active = item.enabled
		missing = item.enabled and item.mesh is None and item.side != 'L'
		sub.label(text=part_scene.label(item), icon='ERROR' if missing else 'MESH_DATA')


class VIEW3D_PT_ballistica_parts(_Section, bpy.types.Panel):
	bl_label = "Parts"
	header_icon = 'MESH_DATA'

	def draw(self, context):
		from . import part_scene

		collection = active_character(context)
		settings = collection.ballistica_character
		layout = self.layout
		layout.template_list(
			'BALLISTICA_UL_parts', '', settings, 'parts', settings, 'active_part_index', rows=5, maxrows=15)
		index = settings.active_part_index
		if not 0 <= index < len(settings.parts):
			return
		row = settings.parts[index]
		col = layout.column()
		_split(col)
		if row.side == 'L' and not row.enabled:
			col.label(text=f"Mirrors the {part_scene.label(row)[5:]}.", icon='MOD_MIRROR')
			col.label(text="Tick it to give the left side its own mesh.")
		elif not row.enabled:
			col.label(text=f"No {part_scene.label(row).lower()}. Tick it to add one.", icon='INFO')
		else:
			if row.side == 'L':
				col.label(text="Model it as a right part: the game mirrors it.", icon='MOD_MIRROR')
			line = col.row(align=True)
			line.prop(row, 'mesh')
			line.operator('ballistica.pick_part_mesh', text="", icon='EYEDROPPER')
			line.operator('ballistica.new_part_mesh', text="", icon='ADD')
			if row.mesh is not None:
				_shared_note(col, row.mesh, collection, 'PART')
				asset = row.mesh.ballistica_asset
				col.prop(asset, 'export_uv')
				col.prop(asset, 'path', placeholder=part_scene.default_path(collection, row))
		if row.part in ('upper_arm', 'forearm', 'hand') and row.side != 'L':
			col.separator()
			col.prop(settings, 'flippers')
			fields = part_scene.fields(collection)
			hint = rig.flippers_hint(
				settings.flippers, fields.get('forearm_mesh', settings.forearm_mesh), fields.get('hand_mesh', settings.hand_mesh))
			if hint:
				box = col.box()
				box.label(text="Forearm or hand used with Flippers on", icon='INFO')
				box.label(text="They'll still be drawn; turn them off for flipper arms.")


def _missing_sounds(settings, field):
	from . import props, workspace

	root = settings.workspace_root
	return [s for s in props.sound_list(getattr(settings, field)) if workspace.file_path(root, s, 'sound') is None]


class BALLISTICA_UL_sounds(bpy.types.UIList):
	"""The six sound lists: jump, attack, impact, death, pickup, fall."""

	def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
		from . import props

		count = len(props.sound_list(getattr(data, item.field)))
		missing = _missing_sounds(data, item.field)
		row = layout.row()
		row.label(text=item.field.replace('_sounds', '').title(), icon='ERROR' if missing else 'SOUND')
		sub = row.row()
		sub.active = False
		sub.label(text=f"{len(missing)} of {count} missing" if missing else str(count))


class VIEW3D_PT_ballistica_sounds(_Section, bpy.types.Panel):
	bl_label = "Sounds"
	header_icon = 'SOUND'

	def draw(self, context):
		from . import props

		settings = active_character(context).ballistica_character
		layout = self.layout
		layout.template_list(
			'BALLISTICA_UL_sounds', '', settings, 'sounds', settings, 'active_sound_index', rows=6, maxrows=6)
		index = settings.active_sound_index
		if not 0 <= index < len(settings.sounds):
			return
		field = settings.sounds[index].field
		col = layout.column()
		col.prop(settings, field, text="")
		col.prop(settings, 'sound_to_add', text="", icon='ADD', placeholder="Add a sound from the workspace")
		for path in _missing_sounds(settings, field):
			col.label(text=f"{path}: not in the workspace", icon='ERROR')


class VIEW3D_PT_ballistica_physique(_Section, bpy.types.Panel):
	bl_label = "Physique"
	header_icon = 'MOD_PHYSICS'
	fields = (
		'torso_radius', 'shoulder_offset', 'thigh_radius', 'ankle_radius',
		'step_separation', 'idle_arm_stiffness', 'arm_swing', 'idle_sway',
	)

	def draw(self, context):
		_group_toggles(self.layout, context, active_character(context), ('Guides', 'Rig'))
		_Section.draw(self, context)


class VIEW3D_PT_ballistica_eyes(_Section, bpy.types.Panel):
	bl_label = "Eyes"
	header_icon = 'MATSPHERE'
	fields = (
		'eye_style_left', 'eye_style_right', 'eye_size', 'eye_position',
		'eye_color', 'eyeball_color', 'eyelid_color', 'eyelid_angle',
	)

	def draw(self, context):
		_group_toggles(self.layout, context, active_character(context), ('Eyes', 'Rig'))
		self.layout.operator('ballistica.select_eye_handle', icon='RESTRICT_SELECT_OFF')
		_Section.draw(self, context)


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
	header_icon = 'LINKED'

	def draw(self, context):
		from . import attachments

		collection = active_character(context)
		settings = collection.ballistica_character
		layout = self.layout
		_group_toggles(layout, context, collection, ('Attachments', 'Rig'))
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
		for key, attr, kind in (
			('mesh', 'mesh_block', 'SEGMENT_MESH'),
			('texture', 'texture_block', 'SEGMENT_TEXTURE'),
			('mask_texture', 'mask_block', 'SEGMENT_MASK'),
		):
			line = col.row(align=True)
			line.prop(segment, attr)
			if key == 'mesh':
				line.operator('ballistica.pick_part_mesh', text="", icon='EYEDROPPER').target = 'SEGMENT'
			line.operator('ballistica.new_segment_block', text="", icon='ADD').key = key
			block = getattr(segment, attr)
			if block is not None:
				_shared_note(col, block, collection, kind)
				asset = block.ballistica_asset if key == 'mesh' else block.ballistica_texture
				col.prop(asset, 'path', text="Export Path")
			elif getattr(segment, key):
				col.label(text=f"{getattr(segment, key)} isn't in the workspace", icon='ERROR')
		if segment.texture_block is None and segment.mask_block is None:
			col.label(text="No texture or mask of its own: uses the body's.", icon='INFO')
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


ISSUES_URL = "https://github.com/bombsquad02420/blender-addon/issues/new"
ISSUE_TEMPLATE = "ballistica_cloud_tools.yml"


def _os_name():
	import platform

	if platform.system() == 'Darwin':
		return f"macOS {platform.mac_ver()[0]}"
	if platform.system() == 'Windows':
		return f"Windows {platform.release()} ({platform.version()})"
	return f"{platform.system()} {platform.release()}"


def issue_url():
	"""A new issue with the Cloud Tools form, its version fields filled in."""
	from urllib.parse import urlencode

	return ISSUES_URL + '?' + urlencode({
		'template': ISSUE_TEMPLATE,
		'addon_version': _addon_version(),
		'blender_version': bpy.app.version_string,
		'os': _os_name(),
	})


def _addon_version():
	import os
	import re

	manifest = os.path.join(os.path.dirname(__file__), 'blender_manifest.toml')
	try:
		with open(manifest, encoding='utf-8') as infile:
			found = re.search(r'^version = "(.*)"', infile.read(), re.M)
	except OSError:
		return "unknown"
	return found.group(1) if found else "unknown"


class VIEW3D_PT_ballistica_help(_Panel, bpy.types.Panel):
	"""Where to ask for help or report a problem (always last)."""
	bl_label = "Help"
	bl_parent_id = 'VIEW3D_PT_ballistica_character'
	bl_options = {'DEFAULT_CLOSED'}
	header_icon = 'HELP'

	def draw_header(self, context):
		self.layout.label(icon=self.header_icon)

	def draw(self, context):
		layout = self.layout
		col = layout.column(align=True)
		col.label(text="Stuck, or found a bug? Tell us on GitHub.")
		col.label(text="The report starts with these filled in:")
		col.label(text=f"Addon {_addon_version()} · Blender {bpy.app.version_string}")
		col.label(text=_os_name())
		layout.operator('wm.url_open', text="Report a Problem", icon='URL').url = issue_url()


classes = (
	BALLISTICA_UL_characters,
	BALLISTICA_UL_sounds,
	BALLISTICA_UL_textures,
	BALLISTICA_UL_parts,
	BALLISTICA_UL_attachments,
	BALLISTICA_UL_segments,
	VIEW3D_PT_ballistica_character,
	# Sections appear in registration order.
	VIEW3D_PT_ballistica_visibility,
	VIEW3D_PT_ballistica_identity,
	VIEW3D_PT_ballistica_parts,
	VIEW3D_PT_ballistica_textures,
	VIEW3D_PT_ballistica_physique,
	VIEW3D_PT_ballistica_eyes,
	VIEW3D_PT_ballistica_attachments,
	VIEW3D_PT_ballistica_sounds,
	VIEW3D_PT_ballistica_help,  # last: at the very bottom
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
