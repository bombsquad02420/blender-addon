import os
import bpy

from . import utils, node_groups


class SCENE_OT_bombsquad_arrange_character(bpy.types.Operator):
	"""Arrange selected character parts"""
	bl_idname = "scene.bombsquad_arrange_character"
	bl_label = "Arrange Bombsquad Character"
	bl_options = {'REGISTER', 'UNDO'}

	style: bpy.props.EnumProperty(
		items=(
			('NONE', 'None', "Clear all transformations."),
			('DEFAULT', 'Default', "Arrange the character parts to resemble neoSpaz style"),
			('WIDE', 'Wide', "Arrange the character parts to resemble frosty, mel, and other wider styles"),
			('EXPLODED', 'Exploded', "Space out the character parts so that they are easier to texture paint and uv map"),
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
			elif self.style == 'WIDE':
				obj.location = part_metadata['location_wide'] if 'location_wide' in part_metadata else part_metadata['location']
				obj.rotation_euler = part_metadata['rotation_wide'] if 'rotation_wide' in part_metadata else part_metadata['rotation']
			elif self.style == 'EXPLODED':
				obj.location = part_metadata['location_exploded']
				obj.rotation_euler = (0, 0, 0)

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


class SCENE_OT_bombsquad_export_textures(bpy.types.Operator):
	"""Export all textures marked as BombSquad Texture"""
	bl_idname = "scene.bombsquad_export_textures"
	bl_label = "Export BombSquad Textures"
	bl_options = {'REGISTER'}

	export_directory: bpy.props.StringProperty(
		name="Export Directory",
		subtype='DIR_PATH',
	)

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")

		exported = 0
		images = bpy.data.images
		for image in images:
			if not image.bombsquad.export_enabled:
				continue
			if not image.has_data:
				self.report({'WARNING'}, f"Image `{image.name}` has no data. Skipping export.")
				print(f"{self.__class__.__name__}: [WARN] Image `{image.name}` has no data.")
				continue
			filename = bpy.path.display_name_to_filepath(image.name) + '.png'
			filepath = os.path.join(self.export_directory, filename)
			print(f"{self.__class__.__name__}: [INFO] Exporting image `{image.name}` to {filepath}.")
			image.save(filepath=filepath)
			exported += 1

		print(f"{self.__class__.__name__}: [INFO] Exported {exported} images.")
		self.report({'INFO'}, f"Exported {exported} images.")

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
		cursor_location = context.scene.cursor.location
		empty = None

		if location['draw'] == 'POINT':
			empty = utils.add_point(
				context,
				name=self.location_type + '.000',
				center=cursor_location,
			)
		elif location['draw'] == 'PLANE':
			empty = utils.add_plane(
				context,
				name=self.location_type + '.000',
				center=cursor_location,
				size=location['default_size'],
			)
		elif location['draw'] == 'CUBE':
			empty = utils.add_cube(
				context,
				name=self.location_type + '.000',
				center=cursor_location,
				size=location['default_size'],
			)
		
		bpy.ops.object.select_all(action='DESELECT')
		empty.select_set(True)
		context.view_layer.objects.active = empty

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
		
		cursor_location = context.scene.cursor.location
		empty = None

		if self.location_type == 'POINT':
			empty = utils.add_point(
				context,
				name=self.location_name + '.000',
				center=cursor_location,
			)
		elif self.location_type == 'PLANE':
			empty = utils.add_plane(
				context,
				name=self.location_name + '.000',
				center=cursor_location,
			)
		elif self.location_type == 'CUBE':
			empty = utils.add_cube(
				context,
				name=self.location_name + '.000',
				center=cursor_location,
			)
		
		bpy.ops.object.select_all(action='DESELECT')
		empty.select_set(True)
		context.view_layer.objects.active = empty

		return {'FINISHED'}


class MATERIAL_OT_add_bombsquad_shader(bpy.types.Operator):
	"""Add a simple BombSquad shader material that supports transparency"""
	bl_idname = "material.add_bombsquad_shader"
	bl_label = "Add BombSquad Shader"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	material_name: bpy.props.StringProperty(
		name="Material Name",
		default="BombSquad Material"
	)
	image: bpy.props.StringProperty(
		name="Image",
	)
	uv_map: bpy.props.StringProperty(
		name="UV Map",
	)

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")
		
		active_object = context.active_object

		image_src = None
		if self.image and self.image in bpy.data.images:
			image_src = bpy.data.images[self.image]

		uv_map_name = self.uv_map
		if uv_map_name == "" and active_object.data.uv_layers:
			uv_map_name = active_object.data.uv_layers[0].name

		material = node_groups.create_bombsquad_material(
			name=self.material_name,
			image_src=image_src,
			uv_map_name=uv_map_name,
		)
		active_object.data.materials.append(material)

		return {'FINISHED'}


class MATERIAL_OT_add_bombsquad_colorize_shader(bpy.types.Operator):
	"""Add a BombSquad shader material that supports color mask"""
	bl_idname = "material.add_bombsquad_colorize_shader"
	bl_label = "Add BombSquad Colorize Shader"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	material_name: bpy.props.StringProperty(
		name="Material Name",
		default="BombSquad Colorize Material"
	)
	image: bpy.props.StringProperty(
		name="Image",
	)
	color_mask: bpy.props.StringProperty(
		name="Color Mask",
	)
	uv_map: bpy.props.StringProperty(
		name="UV Map",
	)

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def execute(self, context):
		print(f"{self.__class__.__name__}: [INFO] Executing with options {self.as_keywords()}")
				
		active_object = context.active_object

		image_src = None
		if self.image and self.image in bpy.data.images:
			image_src = bpy.data.images[self.image]

		color_mask_src = None
		if self.color_mask and self.color_mask in bpy.data.images:
			color_mask_src = bpy.data.images[self.color_mask]

		uv_map_name = self.uv_map
		if uv_map_name == "" and active_object.data.uv_layers:
			uv_map_name = active_object.data.uv_layers[0].name

		material = node_groups.create_bombsquad_character_material(
			name=self.material_name,
			color_image_src=image_src,
			color_mask_image_src=color_mask_src,
			uv_map_name=uv_map_name,
		)
		active_object.data.materials.append(material)

		return {'FINISHED'}


classes = (
	SCENE_OT_bombsquad_arrange_character,
	COLLECTION_OT_bombsquad_create_character_exporter,
	COLLECTION_OT_bombsquad_create_bob_exporter,
	COLLECTION_OT_bombsquad_create_cob_exporter,
	SCENE_OT_bombsquad_export_textures,
	OBJECT_OT_add_bombsquad_map_location,
	OBJECT_OT_add_bombsquad_map_location_custom,
	MATERIAL_OT_add_bombsquad_shader,
	MATERIAL_OT_add_bombsquad_colorize_shader,
)


_register, _unregister = bpy.utils.register_classes_factory(classes)


def register():
	_register()


def unregister():
	_unregister()


if __name__ == "__main__":
	register()
