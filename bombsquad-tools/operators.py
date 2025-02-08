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


class COLLECTION_OT_bombsquad_create_bob_exporter(bpy.types.Operator):
	"""Create a collection exporter for the active collection"""
	bl_idname = "collection.bombsquad_create_bob_exporter"
	bl_label = "Create .bob Exporter"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	@classmethod
	def poll(cls, context):
		return context.view_layer.active_layer_collection.collection != context.scene.collection

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		collection = context.view_layer.active_layer_collection.collection
		
		bpy.ops.collection.exporter_add(name='IO_FH_bombsquad_bob')
		exporter = collection.exporters[-1]

		print(f"{self.__class__.__name__}: [INFO] Created collection exporter for collection `{collection.name}`.")

		return {'FINISHED'}


class COLLECTION_OT_bombsquad_create_cob_exporter(bpy.types.Operator):
	"""Create a collection exporter for the active collection"""
	bl_idname = "collection.bombsquad_create_cob_exporter"
	bl_label = "Create .cob Exporter"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	@classmethod
	def poll(cls, context):
		return context.view_layer.active_layer_collection.collection != context.scene.collection

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		collection = context.view_layer.active_layer_collection.collection
		
		bpy.ops.collection.exporter_add(name='IO_FH_bombsquad_cob')
		exporter = collection.exporters[-1]

		print(f"{self.__class__.__name__}: [INFO] Created collection exporter for collection `{collection.name}`.")

		return {'FINISHED'}


class OBJECT_OT_add_bombsquad_map_location(bpy.types.Operator):
	"""Add a well known BombSquad map location to the scene"""
	bl_idname = "object.add_bombsquad_map_location"
	bl_label = "Add BombSquad map location"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	location_type: bpy.props.EnumProperty(
		items=utils.known_location_type_items,
		name="Location Type",
	)

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")
		
		location = utils.location_metadata[self.location_type]
		empty = None

		if location['draw'] == 'POINT':
			empty = utils.add_point(
				context,
				name=self.location_type + '.000',
				center=location['default_center'],
			)
		elif location['draw'] == 'PLANE':
			empty = utils.add_plane(
				context,
				name=self.location_type + '.000',
				center=location['default_center'],
				size=location['default_size'],
			)
		elif location['draw'] == 'CUBE':
			empty = utils.add_cube(
				context,
				name=self.location_type + '.000',
				center=location['default_center'],
				size=location['default_size'],
			)
		
		bpy.ops.object.select_all(action='DESELECT')
		empty.select_set(True)

		return {'FINISHED'}


class OBJECT_OT_add_bombsquad_map_location_custom(bpy.types.Operator):
	"""Add a custom BombSquad map location to the scene"""
	bl_idname = "object.add_bombsquad_map_location_custom"
	bl_label = "Add custom BombSquad map location"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	location_type: bpy.props.EnumProperty(
		items=utils.custom_location_type_items,
		name="Location Type",
	)
	location_name: bpy.props.StringProperty(
		name="Location Name",
		default="custom"
	)

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")
		
		empty = None

		if self.location_type == 'POINT':
			empty = utils.add_point(
				context,
				name=self.location_name + '.000',
			)
		elif self.location_type == 'PLANE':
			empty = utils.add_plane(
				context,
				name=self.location_name + '.000',
			)
		elif self.location_type == 'CUBE':
			empty = utils.add_cube(
				context,
				name=self.location_name + '.000',
			)
		
		bpy.ops.object.select_all(action='DESELECT')
		empty.select_set(True)

		return {'FINISHED'}


classes = (
	SCENE_OT_bombsquad_arrange_character,
	COLLECTION_OT_bombsquad_create_character_exporter,
	COLLECTION_OT_bombsquad_create_bob_exporter,
	COLLECTION_OT_bombsquad_create_cob_exporter,
	OBJECT_OT_add_bombsquad_map_location,
	OBJECT_OT_add_bombsquad_map_location_custom,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()


def unregister():
	_unregister()


if __name__ == "__main__":
	register()
