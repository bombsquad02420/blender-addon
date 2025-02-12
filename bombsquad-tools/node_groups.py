import bpy


BOMBSQUAD_SHADER_NAME = "BombSquad Shader"
BOMBSQUAD_COLORIZE_SHADER_NAME = "BombSquad Colorize Shader"


# Generated using extension node_to_python
def create_bombsquad_shader_node_group():
	bombsquad_shader = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = BOMBSQUAD_SHADER_NAME)

	bombsquad_shader.color_tag = 'NONE'
	bombsquad_shader.description = ""
	bombsquad_shader.default_group_node_width = 140

	#bombsquad_shader interface
	#Socket Shader
	shader_socket = bombsquad_shader.interface.new_socket(name = "Shader", in_out='OUTPUT', socket_type = 'NodeSocketShader')
	shader_socket.attribute_domain = 'POINT'

	#Socket Texture
	texture_socket = bombsquad_shader.interface.new_socket(name = "Texture", in_out='INPUT', socket_type = 'NodeSocketColor')
	texture_socket.default_value = (0.0, 0.0, 0.0, 1.0)
	texture_socket.attribute_domain = 'POINT'

	#Socket Alpha
	alpha_socket = bombsquad_shader.interface.new_socket(name = "Alpha", in_out='INPUT', socket_type = 'NodeSocketFloat')
	alpha_socket.default_value = 1.0
	alpha_socket.min_value = 0.0
	alpha_socket.max_value = 1.0
	alpha_socket.subtype = 'FACTOR'
	alpha_socket.attribute_domain = 'POINT'

	#initialize bombsquad_shader nodes
	#node Group Output
	group_output = bombsquad_shader.nodes.new("NodeGroupOutput")
	group_output.name = "Group Output"
	group_output.is_active_output = True

	#node Group Input
	group_input = bombsquad_shader.nodes.new("NodeGroupInput")
	group_input.name = "Group Input"

	#node Mix Shader
	mix_shader = bombsquad_shader.nodes.new("ShaderNodeMixShader")
	mix_shader.name = "Mix Shader"

	#node Transparent BSDF
	transparent_bsdf = bombsquad_shader.nodes.new("ShaderNodeBsdfTransparent")
	transparent_bsdf.name = "Transparent BSDF"
	#Color
	transparent_bsdf.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)

	#Set locations
	group_output.location = (380.0, 0.0)
	group_input.location = (-320.0, 0.0)
	mix_shader.location = (140.0, -20.0)
	transparent_bsdf.location = (-80.0, 40.0)

	#Set dimensions
	group_output.width, group_output.height = 140.0, 100.0
	group_input.width, group_input.height = 140.0, 100.0
	mix_shader.width, mix_shader.height = 140.0, 100.0
	transparent_bsdf.width, transparent_bsdf.height = 140.0, 100.0

	#initialize bombsquad_shader links
	#transparent_bsdf.BSDF -> mix_shader.Shader
	bombsquad_shader.links.new(transparent_bsdf.outputs[0], mix_shader.inputs[1])
	#group_input.Alpha -> mix_shader.Fac
	bombsquad_shader.links.new(group_input.outputs[1], mix_shader.inputs[0])
	#group_input.Texture -> mix_shader.Shader
	bombsquad_shader.links.new(group_input.outputs[0], mix_shader.inputs[2])
	#mix_shader.Shader -> group_output.Shader
	bombsquad_shader.links.new(mix_shader.outputs[0], group_output.inputs[0])
	
	return bombsquad_shader

def find_or_create_bombsquad_shader_node_group():
	if BOMBSQUAD_SHADER_NAME not in bpy.data.node_groups:
		bombsquad_shader = create_bombsquad_shader_node_group()
		return bombsquad_shader
	
	return bpy.data.node_groups[BOMBSQUAD_SHADER_NAME]


# Generated using extension node_to_python
def create_bombsquad_colorize_shader_node_group():
	bombsquad_colorize_shader = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = BOMBSQUAD_COLORIZE_SHADER_NAME)

	bombsquad_colorize_shader.color_tag = 'NONE'
	bombsquad_colorize_shader.description = ""
	bombsquad_colorize_shader.default_group_node_width = 140

	#bombsquad_colorize_shader interface
	#Socket BSDF
	bsdf_socket = bombsquad_colorize_shader.interface.new_socket(name = "BSDF", in_out='OUTPUT', socket_type = 'NodeSocketShader')
	bsdf_socket.attribute_domain = 'POINT'

	#Socket Texture
	texture_socket = bombsquad_colorize_shader.interface.new_socket(name = "Texture", in_out='INPUT', socket_type = 'NodeSocketColor')
	texture_socket.default_value = (0.5, 0.5, 0.5, 1.0)
	texture_socket.attribute_domain = 'POINT'

	#Socket Color Mask
	color_mask_socket = bombsquad_colorize_shader.interface.new_socket(name = "Color Mask", in_out='INPUT', socket_type = 'NodeSocketColor')
	color_mask_socket.default_value = (0.0, 0.0, 0.0, 1.0)
	color_mask_socket.attribute_domain = 'POINT'

	#Socket Tint Color
	tint_color_socket = bombsquad_colorize_shader.interface.new_socket(name = "Tint Color", in_out='INPUT', socket_type = 'NodeSocketColor')
	tint_color_socket.default_value = (1.0, 0.01, 0.37, 1.0)
	tint_color_socket.attribute_domain = 'POINT'

	#Socket Highlight Color
	highlight_color_socket = bombsquad_colorize_shader.interface.new_socket(name = "Highlight Color", in_out='INPUT', socket_type = 'NodeSocketColor')
	highlight_color_socket.default_value = (0.31, 0.01, 1.0, 1.0)
	highlight_color_socket.attribute_domain = 'POINT'

	#initialize bombsquad_colorize_shader nodes
	#node Group Output
	group_output = bombsquad_colorize_shader.nodes.new("NodeGroupOutput")
	group_output.name = "Group Output"
	group_output.is_active_output = True

	#node Group Input
	group_input = bombsquad_colorize_shader.nodes.new("NodeGroupInput")
	group_input.name = "Group Input"

	#node Separate XYZ
	separate_xyz = bombsquad_colorize_shader.nodes.new("ShaderNodeSeparateXYZ")
	separate_xyz.name = "Separate XYZ"

	#node Multiply Red
	multiply_red = bombsquad_colorize_shader.nodes.new("ShaderNodeMix")
	multiply_red.name = "Multiply Red"
	multiply_red.blend_type = 'MULTIPLY'
	multiply_red.clamp_factor = True
	multiply_red.clamp_result = False
	multiply_red.data_type = 'RGBA'
	multiply_red.factor_mode = 'UNIFORM'

	#node Multiply Green
	multiply_green = bombsquad_colorize_shader.nodes.new("ShaderNodeMix")
	multiply_green.name = "Multiply Green"
	multiply_green.blend_type = 'MULTIPLY'
	multiply_green.clamp_factor = True
	multiply_green.clamp_result = False
	multiply_green.data_type = 'RGBA'
	multiply_green.factor_mode = 'UNIFORM'

	#Set locations
	group_output.location = (80.0, -160.0)
	group_input.location = (-880.0, -80.0)
	separate_xyz.location = (-640.0, -280.0)
	multiply_red.location = (-360.0, 40.0)
	multiply_green.location = (-120.0, -140.0)

	#Set dimensions
	group_output.width, group_output.height = 140.0, 100.0
	group_input.width, group_input.height = 140.0, 100.0
	separate_xyz.width, separate_xyz.height = 140.0, 100.0
	multiply_red.width, multiply_red.height = 140.0, 100.0
	multiply_green.width, multiply_green.height = 140.0, 100.0

	#initialize bombsquad_colorize_shader links
	#group_input.Highlight Color -> multiply_green.B
	bombsquad_colorize_shader.links.new(group_input.outputs[3], multiply_green.inputs[7])
	#group_input.Tint Color -> multiply_red.B
	bombsquad_colorize_shader.links.new(group_input.outputs[2], multiply_red.inputs[7])
	#separate_xyz.X -> multiply_red.Factor
	bombsquad_colorize_shader.links.new(separate_xyz.outputs[0], multiply_red.inputs[0])
	#group_input.Texture -> multiply_red.A
	bombsquad_colorize_shader.links.new(group_input.outputs[0], multiply_red.inputs[6])
	#multiply_red.Result -> multiply_green.A
	bombsquad_colorize_shader.links.new(multiply_red.outputs[2], multiply_green.inputs[6])
	#separate_xyz.Y -> multiply_green.Factor
	bombsquad_colorize_shader.links.new(separate_xyz.outputs[1], multiply_green.inputs[0])
	#multiply_green.Result -> group_output.BSDF
	bombsquad_colorize_shader.links.new(multiply_green.outputs[2], group_output.inputs[0])
	#group_input.Color Mask -> separate_xyz.Vector
	bombsquad_colorize_shader.links.new(group_input.outputs[1], separate_xyz.inputs[0])
	return bombsquad_colorize_shader

def find_or_create_bombsquad_colorize_shader_node_group():
	if BOMBSQUAD_COLORIZE_SHADER_NAME not in bpy.data.node_groups:
		bombsquad_colorize_shader = create_bombsquad_colorize_shader_node_group()
		return bombsquad_colorize_shader
	
	return bpy.data.node_groups[BOMBSQUAD_COLORIZE_SHADER_NAME]


# Generated using extension node_to_python
def create_bombsquad_material(name, image_src, uv_map_name):
	mat = bpy.data.materials.new(name=name)
	mat.use_nodes = True

	bombsquad_material = mat.node_tree

	#start with a clean node tree
	for node in bombsquad_material.nodes:
		bombsquad_material.nodes.remove(node)
	bombsquad_material.color_tag = 'NONE'
	bombsquad_material.description = ""
	bombsquad_material.default_group_node_width = 140
	
	#bombsquad_material interface

	#initialize bombsquad_material nodes
	#node Material Output
	material_output = bombsquad_material.nodes.new("ShaderNodeOutputMaterial")
	material_output.name = "Material Output"
	material_output.is_active_output = True
	material_output.target = 'ALL'
	#Displacement
	material_output.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Thickness
	material_output.inputs[3].default_value = 0.0

	#node Image Texture
	image_texture = bombsquad_material.nodes.new("ShaderNodeTexImage")
	image_texture.name = "Image Texture"
	image_texture.extension = 'CLIP'
	image_texture.image = image_src
	image_texture.image_user.frame_current = 0
	image_texture.image_user.frame_duration = 100
	image_texture.image_user.frame_offset = 0
	image_texture.image_user.frame_start = 1
	image_texture.image_user.tile = 0
	image_texture.image_user.use_auto_refresh = False
	image_texture.image_user.use_cyclic = False
	image_texture.interpolation = 'Linear'
	image_texture.projection = 'FLAT'
	image_texture.projection_blend = 0.0

	#node UV Map
	uv_map = bombsquad_material.nodes.new("ShaderNodeUVMap")
	uv_map.name = "UV Map"
	uv_map.from_instancer = False
	uv_map.uv_map = uv_map_name

	#node BombSquad Shader Node Group
	bombsquad_shader_node_group = bombsquad_material.nodes.new("ShaderNodeGroup")
	bombsquad_shader_node_group.name = "BombSquad Shader Node Group"
	bombsquad_shader_node_group.node_tree = find_or_create_bombsquad_shader_node_group()

	#Set locations
	material_output.location = (320.0, 280.0)
	image_texture.location = (-220.0, 280.0)
	uv_map.location = (-440.0, 200.0)
	bombsquad_shader_node_group.location = (100.0, 280.0)

	#Set dimensions
	material_output.width, material_output.height = 140.0, 100.0
	image_texture.width, image_texture.height = 240.0, 100.0
	uv_map.width, uv_map.height = 150.0, 100.0
	bombsquad_shader_node_group.width, bombsquad_shader_node_group.height = 140.0, 100.0

	#initialize bombsquad_material links
	#bombsquad_shader_node_group.Shader -> material_output.Surface
	bombsquad_material.links.new(bombsquad_shader_node_group.outputs[0], material_output.inputs[0])
	#image_texture.Alpha -> bombsquad_shader_node_group.Alpha
	bombsquad_material.links.new(image_texture.outputs[1], bombsquad_shader_node_group.inputs[1])
	#image_texture.Color -> bombsquad_shader_node_group.Texture
	bombsquad_material.links.new(image_texture.outputs[0], bombsquad_shader_node_group.inputs[0])
	#uv_map.UV -> image_texture.Vector
	bombsquad_material.links.new(uv_map.outputs[0], image_texture.inputs[0])
	
	return mat


# Generated using extension node_to_python
def create_bombsquad_character_material(name, color_image_src, color_mask_image_src, uv_map_name):
	mat = bpy.data.materials.new(name=name)
	mat.use_nodes = True

	bombsquad_character_material = mat.node_tree
	
	#start with a clean node tree
	for node in bombsquad_character_material.nodes:
		bombsquad_character_material.nodes.remove(node)
	bombsquad_character_material.color_tag = 'NONE'
	bombsquad_character_material.description = ""
	bombsquad_character_material.default_group_node_width = 140

	#bombsquad_character_material interface

	#initialize bombsquad_character_material nodes
	#node Material Output
	material_output = bombsquad_character_material.nodes.new("ShaderNodeOutputMaterial")
	material_output.name = "Material Output"
	material_output.is_active_output = True
	material_output.target = 'ALL'
	#Displacement
	material_output.inputs[2].default_value = (0.0, 0.0, 0.0)
	#Thickness
	material_output.inputs[3].default_value = 0.0

	#node Color Image
	color_image = bombsquad_character_material.nodes.new("ShaderNodeTexImage")
	color_image.name = "Color Image"
	color_image.extension = 'CLIP'
	color_image.image = color_image_src
	color_image.image_user.frame_current = 0
	color_image.image_user.frame_duration = 100
	color_image.image_user.frame_offset = 0
	color_image.image_user.frame_start = 1
	color_image.image_user.tile = 0
	color_image.image_user.use_auto_refresh = False
	color_image.image_user.use_cyclic = False
	color_image.interpolation = 'Linear'
	color_image.projection = 'FLAT'
	color_image.projection_blend = 0.0

	#node Color Mask Image 
	color_mask_image = bombsquad_character_material.nodes.new("ShaderNodeTexImage")
	color_mask_image.name = "Color Mask Image "
	color_mask_image.extension = 'CLIP'
	color_mask_image.image = color_mask_image_src
	color_mask_image.image_user.frame_current = 0
	color_mask_image.image_user.frame_duration = 100
	color_mask_image.image_user.frame_offset = 0
	color_mask_image.image_user.frame_start = 1
	color_mask_image.image_user.tile = 0
	color_mask_image.image_user.use_auto_refresh = False
	color_mask_image.image_user.use_cyclic = False
	color_mask_image.interpolation = 'Linear'
	color_mask_image.projection = 'FLAT'
	color_mask_image.projection_blend = 0.0

	#node UV Map
	uv_map = bombsquad_character_material.nodes.new("ShaderNodeUVMap")
	uv_map.name = "UV Map"
	uv_map.from_instancer = False
	uv_map.uv_map = uv_map_name

	#node BombSquad Colorize Shader
	bombsquad_colorize_shader_node_group = bombsquad_character_material.nodes.new("ShaderNodeGroup")
	bombsquad_colorize_shader_node_group.name = "BombSquad Colorize Shader Node Group"
	bombsquad_colorize_shader_node_group.node_tree = find_or_create_bombsquad_colorize_shader_node_group()

	#Set locations
	material_output.location = (-60.000003814697266, 320.0)
	color_image.location = (-860.0000610351562, 400.0)
	color_mask_image.location = (-860.0000610351562, 100.0)
	uv_map.location = (-1160.0, 80.0)
	bombsquad_colorize_shader_node_group.location = (-420.0000305175781, 320.0)

	#Set dimensions
	material_output.width, material_output.height = 140.0, 100.0
	color_image.width, color_image.height = 283.39801025390625, 100.0
	color_mask_image.width, color_mask_image.height = 283.6218566894531, 100.0
	uv_map.width, uv_map.height = 150.0, 100.0
	bombsquad_colorize_shader_node_group.width, bombsquad_colorize_shader_node_group.height = 262.0115966796875, 100.0

	#initialize bombsquad_character_material links
	#uv_map.UV -> color_image.Vector
	bombsquad_character_material.links.new(uv_map.outputs[0], color_image.inputs[0])
	#uv_map.UV -> color_mask_image.Vector
	bombsquad_character_material.links.new(uv_map.outputs[0], color_mask_image.inputs[0])
	#bombsquad_colorize_shader_node_group.BSDF -> material_output.Surface
	bombsquad_character_material.links.new(bombsquad_colorize_shader_node_group.outputs[0], material_output.inputs[0])
	#color_image.Color -> bombsquad_colorize_shader_node_group.Texture
	bombsquad_character_material.links.new(color_image.outputs[0], bombsquad_colorize_shader_node_group.inputs[0])
	#color_mask_image.Color -> bombsquad_colorize_shader_node_group.Color Mask
	bombsquad_character_material.links.new(color_mask_image.outputs[0], bombsquad_colorize_shader_node_group.inputs[1])
	
	return mat

