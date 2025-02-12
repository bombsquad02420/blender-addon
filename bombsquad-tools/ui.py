import bpy

from . import utils


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
		sp.prop(scene.bombsquad_map, "known_location_type", text="")
		sp = sp.split(factor=1.0)
		props = sp.operator("object.add_bombsquad_map_location", text="Add")
		props.location_type = scene.bombsquad_map.known_location_type
		
		col = layout.column(align=True)
		col.label(text="Add custom location")
		sp = col.split(factor=0.8)
		row = sp.row()
		row.prop(scene.bombsquad_map, "custom_location_type", text="")
		row.prop(scene.bombsquad_map, "custom_location_name", text="")
		sp = sp.split(factor=1.0)
		props = sp.operator("object.add_bombsquad_map_location_custom", text="Add")
		props.location_type = scene.bombsquad_map.custom_location_type
		props.location_name = scene.bombsquad_map.custom_location_name


class VIEW3D_PT_bombsquad_batch_export(bpy.types.Panel):
	bl_idname = "VIEW3D_PT_bombsquad_batch_export"
	bl_label = "Batch Export"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "BombSquad"
	bl_context = "objectmode"

	def draw(self, context):
		layout = self.layout

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

		layout.separator()

		col = layout.column(align=True)
		col.operator("wm.collection_export_all")


class MATERIAL_PT_add_bombsquad_shader(bpy.types.Panel):
	bl_idname = "MATERIAL_PT_add_bombsquad_shader"
	bl_label = "BombSquad Shader"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "material"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		layout = self.layout

		col = layout.column(align=True)
		col.operator('material.add_bombsquad_shader')
		col.operator('material.add_bombsquad_colorize_shader')


classes = (
	VIEW3D_PT_bombsquad_character,
	SCENE_PG_bombsquad_map,
	VIEW3D_PT_bombsquad_map,
	VIEW3D_PT_bombsquad_batch_export,
	MATERIAL_PT_add_bombsquad_shader,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()

	# PROPERTY
	bpy.types.Scene.bombsquad_map = bpy.props.PointerProperty(type=SCENE_PG_bombsquad_map, name="BombSquad Map")


def unregister():
	# PROPERTY
	del bpy.types.Scene.bombsquad_map

	_unregister()


if __name__ == "__main__":
	register()
