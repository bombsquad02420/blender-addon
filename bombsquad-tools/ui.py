import bpy


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


classes = (
	VIEW3D_PT_bombsquad_character,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()


def unregister():
	_unregister()


if __name__ == "__main__":
	register()