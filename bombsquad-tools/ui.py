import bpy

from . import utils


class SCENE_PG_bombsquad_map(bpy.types.PropertyGroup):
	known_location_type: bpy.props.EnumProperty(
		items=utils.known_location_type_items,
		name="Location Type",
		options=set(),  # Remove ANIMATABLE default option.
	)
	custom_location_type: bpy.props.EnumProperty(
		items=utils.custom_location_type_items,
		name="Location Type",
		options=set(),  # Remove ANIMATABLE default option.
	)
	custom_location_name: bpy.props.StringProperty(
		name="Location Name",
		default="custom",
		options=set(),  # Remove ANIMATABLE default option.
	)


class SCENE_PG_bombsquad_texture(bpy.types.PropertyGroup):
	active_image_index: bpy.props.IntProperty(
		name="Active Image Index",
		default=0,
		options=set(),  # Remove ANIMATABLE default option.
	)
	export_directory: bpy.props.StringProperty(
		name="Export Directory",
		subtype='DIR_PATH',
		options=set(),  # Remove ANIMATABLE default option.
	)


class SCENE_PG_bombsquad(bpy.types.PropertyGroup):
	map: bpy.props.PointerProperty(type=SCENE_PG_bombsquad_map, name="BombSquad Map")
	texture: bpy.props.PointerProperty(type=SCENE_PG_bombsquad_texture, name="BombSquad Texture")


class IMAGE_PG_bombsquad(bpy.types.PropertyGroup):
	export_enabled: bpy.props.BoolProperty(
		name="Export?",
		default=False
	)


class VIEW3D_PT_bombsquad_character(bpy.types.Panel):
	bl_idname = "VIEW3D_PT_bombsquad_character"
	bl_label = "BombSquad Character"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "BombSquad"
	bl_context = "objectmode"

	def draw(self, context):
		layout = self.layout
		
		col = layout.column(align=True)
		col.label(text="Arrange selected character parts")
		col.operator_enum('scene.bombsquad_arrange_character', "style")


class VIEW3D_PT_bombsquad_map(bpy.types.Panel):
	bl_idname = "VIEW3D_PT_bombsquad_map"
	bl_label = "BombSquad Map"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "BombSquad"
	bl_context = "objectmode"

	def draw(self, context):
		layout = self.layout
		scene = context.scene
		
		col = layout.column(align=True)
		col.label(text="Add known location")
		sp = col.split(factor=0.8)
		sp.prop(scene.bombsquad.map, "known_location_type", text="")
		sp = sp.split(factor=1.0)
		props = sp.operator("object.add_bombsquad_map_location", text="Add")
		props.location_type = scene.bombsquad.map.known_location_type
		
		col = layout.column(align=True)
		col.label(text="Add custom location")
		sp = col.split(factor=0.8)
		row = sp.row()
		row.prop(scene.bombsquad.map, "custom_location_type", text="")
		row.prop(scene.bombsquad.map, "custom_location_name", text="")
		sp = sp.split(factor=1.0)
		props = sp.operator("object.add_bombsquad_map_location_custom", text="Add")
		props.location_type = scene.bombsquad.map.custom_location_type
		props.location_name = scene.bombsquad.map.custom_location_name


class VIEW3D_PT_add_bombsquad_shader(bpy.types.Panel):
	bl_idname = "VIEW3D_PT_add_bombsquad_shader"
	bl_label = "BombSquad Shader"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "BombSquad"
	bl_context = "objectmode"

	def draw(self, context):
		layout = self.layout

		col = layout.column(align=True)
		col.operator('material.add_bombsquad_shader')
		col.operator('material.add_bombsquad_colorize_shader')


class BOMBSQUAD_TEXTURE_UL_items(bpy.types.UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			layout.prop(item.bombsquad, "export_enabled", text="")
			layout.prop(item, "name", text="", emboss=False, icon_value=icon)
			if not item.has_data:
				layout.label(text="(No Data)")
		elif self.layout_type == 'GRID':
			layout.alignment = 'CENTER'
			layout.label(text="", icon_value=icon)


class VIEW3D_PT_bombsquad_batch_export(bpy.types.Panel):
	bl_idname = "VIEW3D_PT_bombsquad_batch_export"
	bl_label = "Batch Export"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "BombSquad"
	bl_context = "objectmode"

	def draw(self, context):
		layout = self.layout

		scene = context.scene
		selected_objects = context.selected_objects
		collection = context.view_layer.active_layer_collection.collection
		active_object = context.active_object

		col = layout.column(align=True)
		box = col.box()
		box_col = box.column(align=True)
		if active_object is not None and collection not in active_object.users_collection:
			box_col.label(text=f"Collection '{collection.name}' is selected which is different from the active object's collection", icon='WARNING_LARGE')
		box_col.label(text="You can configure the exporter from the Collection Properties panel", icon='INFO_LARGE')
		col.separator()
		col.operator('collection.bombsquad_create_character_exporter')
		col.operator('collection.bombsquad_create_bob_exporter')
		col.operator('collection.bombsquad_create_cob_exporter')
		col.separator()
		col.operator("wm.collection_export_all")

		layout.separator()

		col = layout.column(align=True)
		col.label(text="Textures to Export")
		col.template_list("BOMBSQUAD_TEXTURE_UL_items", "custom_def_list", bpy.data, "images", scene.bombsquad.texture, "active_image_index", rows=5)
		col.separator()
		col.prop(scene.bombsquad.texture, "export_directory")
		col.separator()
		col.operator('scene.bombsquad_export_textures').export_directory = scene.bombsquad.texture.export_directory


class VIEW3D_PT_bombsquad_debug(bpy.types.Panel):
	bl_idname = "VIEW3D_PT_bombsquad_debug"
	bl_label = "Debug"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "BombSquad"
	bl_context = "objectmode"

	def draw(self, context):
		layout = self.layout

		col = layout.column(align=True)
		col.operator('mesh.bombsquad_convert_to_bob')


classes = (
	SCENE_PG_bombsquad_map,
	SCENE_PG_bombsquad_texture,
	SCENE_PG_bombsquad,
	IMAGE_PG_bombsquad,
	VIEW3D_PT_bombsquad_character,
	VIEW3D_PT_bombsquad_map,
	VIEW3D_PT_add_bombsquad_shader,
	BOMBSQUAD_TEXTURE_UL_items,
	VIEW3D_PT_bombsquad_batch_export,
	VIEW3D_PT_bombsquad_debug,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()

	# PROPERTY
	bpy.types.Scene.bombsquad = bpy.props.PointerProperty(type=SCENE_PG_bombsquad)
	bpy.types.Image.bombsquad = bpy.props.PointerProperty(type=IMAGE_PG_bombsquad)


def unregister():
	# PROPERTY
	del bpy.types.Scene.bombsquad
	del bpy.types.Image.bombsquad

	_unregister()


if __name__ == "__main__":
	register()
