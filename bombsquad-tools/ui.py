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
		scene = context.scene
		
		col = layout.column(align=True)
		col.label(text="Arrange selected character parts")
		col.operator_enum('SCENE_OT_bombsquad_arrange_character', "style")

		col = layout.column(align=True)
		col.label(text="Create character exporter")
		col.operator('COLLECTION_OT_bombsquad_create_character_exporter')


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


classes = (
	VIEW3D_PT_bombsquad_character,
	SCENE_PG_bombsquad_map,
	VIEW3D_PT_bombsquad_map,
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
