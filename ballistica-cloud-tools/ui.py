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
		row.operator('ballistica.import_character', icon='IMPORT')
		row.operator('ballistica.export_character', icon='EXPORT')
		collection = active_character(context)
		if collection is None:
			layout.label(text="Import a .bchar to get started.", icon='INFO')
			return
		settings = collection.ballistica_character
		col = layout.column(align=True)
		col.label(text=collection.name, icon='OUTLINER_COLLECTION')
		col.prop(settings, 'workspace_root', text="")
		col.prop(settings, 'character_path', text="")
		row = layout.row(align=True)
		row.label(text=f"{_triangles(collection):,} triangles")
		row.operator('ballistica.check_character', icon='CHECKMARK')
		layout.prop(settings, 'show_all_assets')


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

	def draw(self, context):
		super().draw(context)
		collection = active_character(context)
		count = len(_attachments(collection))
		self.layout.label(text=f"{count} attachment(s), kept as loaded", icon='LINKED')


def _attachments(collection):
	import json

	raw = collection.ballistica_character.raw_json
	return json.loads(raw).get('data', {}).get('attachments', []) if raw else []


def _triangles(collection):
	total = 0
	for obj in collection.all_objects:
		if obj.type == 'MESH' and obj.ballistica_part.role not in ('guide', 'eye', 'NONE'):
			total += sum(len(p.vertices) - 2 for p in obj.data.polygons)
	return total


classes = (
	VIEW3D_PT_ballistica_character,
	VIEW3D_PT_ballistica_identity,
	VIEW3D_PT_ballistica_textures,
	VIEW3D_PT_ballistica_meshes,
	VIEW3D_PT_ballistica_sounds,
	VIEW3D_PT_ballistica_physique,
	VIEW3D_PT_ballistica_eyes,
	VIEW3D_PT_ballistica_surface,
	VIEW3D_PT_ballistica_advanced,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
