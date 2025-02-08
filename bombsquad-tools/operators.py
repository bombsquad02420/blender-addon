import bpy

from . import utils

class SCENE_OT_bombsquad_arrange_character(bpy.types.Operator):
	"""Arrange selected character parts"""
	bl_idname = "scene.bombsquad_arrange_character"
	bl_label = "Arrange Bombsquad Character"
	bl_options = {'REGISTER', 'UNDO'}

	style: bpy.props.EnumProperty(
		items=(
			('NONE', 'None', "Clear all transformations."),
			('DEFAULT', 'Default', "Arrange the character parts to resemble `neoSpaz` style"),
		),
		default='DEFAULT',
		name="Style",
	)

	@classmethod
	def poll(cls, context):
		return len(context.selected_objects) > 0

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		selected_objects = context.selected_objects

		for obj in selected_objects:
			character_part = utils.get_character_part_name(obj.name.split('.')[0])
			if character_part is None:
				continue
			part_metadata = utils.character_part_metadata[character_part]
			if self.style == 'NONE':
				obj.location = (0, 0, 0)
				obj.rotation_euler = (0, 0, 0)
			elif self.style == 'DEFAULT':
				obj.location = part_metadata['location']
				obj.rotation_euler = part_metadata['rotation']

		return {'FINISHED'}


class COLLECTION_OT_bombsquad_create_character_exporter(bpy.types.Operator):
	"""Create a collection exporter for the active collection"""
	bl_idname = "collection.bombsquad_create_character_exporter"
	bl_label = "Create Character Exporter"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	@classmethod
	def poll(cls, context):
		return context.view_layer.active_layer_collection.collection != context.scene.collection

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		collection = context.view_layer.active_layer_collection.collection
		
		bpy.ops.collection.exporter_add(name='IO_FH_bombsquad_bob')
		exporter = collection.exporters[-1]

		exporter.export_properties.apply_object_transformations = False
		exporter.export_properties.apply_modifiers = True

		print(f"{self.__class__.__name__}: [INFO] Created collection exporter for collection `{collection.name}`.")

		return {'FINISHED'}


classes = (
	SCENE_OT_bombsquad_arrange_character,
	COLLECTION_OT_bombsquad_create_character_exporter,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()


def unregister():
	_unregister()


if __name__ == "__main__":
	register()
