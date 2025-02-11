import bpy

# Generated using extension node_to_python
def create_bombsquad_shader_node_group():
	bombsquad_shader = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "bombsquad_shader")

	bombsquad_shader.color_tag = 'NONE'
	bombsquad_shader.description = ""
	bombsquad_shader.default_group_node_width = 140

	#bombsquad_shader interface
	#Socket Shader
	shader_socket = bombsquad_shader.interface.new_socket(name = "Shader", in_out='OUTPUT', socket_type = 'NodeSocketShader')
	shader_socket.attribute_domain = 'POINT'

	#Socket Fac
	fac_socket = bombsquad_shader.interface.new_socket(name = "Fac", in_out='INPUT', socket_type = 'NodeSocketFloat')
	fac_socket.subtype = 'FACTOR'
	fac_socket.attribute_domain = 'POINT'

	#Socket Shader
	shader_socket_1 = bombsquad_shader.interface.new_socket(name = "Shader", in_out='INPUT', socket_type = 'NodeSocketShader')
	shader_socket_1.attribute_domain = 'POINT'

	#initialize bombsquad_shader nodes
	#node Group Output
	group_output = bombsquad_shader.nodes.new("NodeGroupOutput")
	group_output.name = "Group Output"
	group_output.is_active_output = True

	#node Group Input
	group_input = bombsquad_shader.nodes.new("NodeGroupInput")
	group_input.name = "Group Input"

	#node Transparent BSDF
	transparent_bsdf = bombsquad_shader.nodes.new("ShaderNodeBsdfTransparent")
	transparent_bsdf.name = "Transparent BSDF"
	#Color
	transparent_bsdf.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)

	#node Mix Shader
	mix_shader = bombsquad_shader.nodes.new("ShaderNodeMixShader")
	mix_shader.name = "Mix Shader"

	#Set locations
	group_output.location = (320.0, 0.0)
	group_input.location = (-330.0, 0.0)
	transparent_bsdf.location = (-120.0, 60.0)
	mix_shader.location = (100.0, 0.0)

	#Set dimensions
	group_output.width, group_output.height = 140.0, 100.0
	group_input.width, group_input.height = 140.0, 100.0
	transparent_bsdf.width, transparent_bsdf.height = 140.0, 100.0
	mix_shader.width, mix_shader.height = 140.0, 100.0

	#initialize bombsquad_shader links
	#transparent_bsdf.BSDF -> mix_shader.Shader
	bombsquad_shader.links.new(transparent_bsdf.outputs[0], mix_shader.inputs[1])
	#group_input.Fac -> mix_shader.Fac
	bombsquad_shader.links.new(group_input.outputs[0], mix_shader.inputs[0])
	#group_input.Shader -> mix_shader.Shader
	bombsquad_shader.links.new(group_input.outputs[1], mix_shader.inputs[2])
	#mix_shader.Shader -> group_output.Shader
	bombsquad_shader.links.new(mix_shader.outputs[0], group_output.inputs[0])
	
	return bombsquad_shader

def find_or_create_bombsquad_shader_node_group():
	if 'bombsquad_shader' not in bpy.data.node_groups:
		bombsquad_shader = create_bombsquad_shader_node_group()
		return bombsquad_shader
	
	return bpy.data.node_groups['bombsquad_shader']


# Generated using extension node_to_python
def create_bombsquad_colorize_shader_node_group():
	bombsquad_colorize_shader = bpy.data.node_groups.new(type = 'ShaderNodeTree', name = "bombsquad_colorize_shader")

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

	#node Mix.001
	mix_001 = bombsquad_colorize_shader.nodes.new("ShaderNodeMix")
	mix_001.name = "Mix.001"
	mix_001.blend_type = 'MULTIPLY'
	mix_001.clamp_factor = True
	mix_001.clamp_result = False
	mix_001.data_type = 'RGBA'
	mix_001.factor_mode = 'UNIFORM'

	#node Mix.002
	mix_002 = bombsquad_colorize_shader.nodes.new("ShaderNodeMix")
	mix_002.name = "Mix.002"
	mix_002.blend_type = 'MULTIPLY'
	mix_002.clamp_factor = True
	mix_002.clamp_result = False
	mix_002.data_type = 'RGBA'
	mix_002.factor_mode = 'UNIFORM'

	#Set locations
	group_output.location = (80.0, -160.0)
	group_input.location = (-880.0, -80.0)
	separate_xyz.location = (-640.0, -280.0)
	mix_001.location = (-360.0, 40.0)
	mix_002.location = (-120.0, -140.0)

	#Set dimensions
	group_output.width, group_output.height = 140.0, 100.0
	group_input.width, group_input.height = 140.0, 100.0
	separate_xyz.width, separate_xyz.height = 140.0, 100.0
	mix_001.width, mix_001.height = 140.0, 100.0
	mix_002.width, mix_002.height = 140.0, 100.0

	#initialize bombsquad_colorize_shader links
	#group_input.Highlight Color -> mix_002.B
	bombsquad_colorize_shader.links.new(group_input.outputs[3], mix_002.inputs[7])
	#group_input.Tint Color -> mix_001.B
	bombsquad_colorize_shader.links.new(group_input.outputs[2], mix_001.inputs[7])
	#separate_xyz.X -> mix_001.Factor
	bombsquad_colorize_shader.links.new(separate_xyz.outputs[0], mix_001.inputs[0])
	#group_input.Texture -> mix_001.A
	bombsquad_colorize_shader.links.new(group_input.outputs[0], mix_001.inputs[6])
	#mix_001.Result -> mix_002.A
	bombsquad_colorize_shader.links.new(mix_001.outputs[2], mix_002.inputs[6])
	#separate_xyz.Y -> mix_002.Factor
	bombsquad_colorize_shader.links.new(separate_xyz.outputs[1], mix_002.inputs[0])
	#mix_002.Result -> group_output.BSDF
	bombsquad_colorize_shader.links.new(mix_002.outputs[2], group_output.inputs[0])
	#group_input.Color Mask -> separate_xyz.Vector
	bombsquad_colorize_shader.links.new(group_input.outputs[1], separate_xyz.inputs[0])
	
	return bombsquad_colorize_shader

def find_or_create_bombsquad_colorize_shader_node_group():
	if 'bombsquad_colorize_shader' not in bpy.data.node_groups:
		bombsquad_colorize_shader = create_bombsquad_colorize_shader_node_group()
		return bombsquad_colorize_shader
	
	return bpy.data.node_groups['bombsquad_colorize_shader']


# Generated using extension node_to_python
def create_bombsquad_character_material(name, color_image_src, color_mask_image_src, uv_map_name):
	mat = bpy.data.materials.new(name=name)
	mat.use_nodes = True
	bombsquad_colorize_shader = find_or_create_bombsquad_colorize_shader_node_group()

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
	color_mask_image.name = "Color Mask Image"
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

	#node Group
	group = bombsquad_character_material.nodes.new("ShaderNodeGroup")
	group.name = "Group"
	group.node_tree = bombsquad_colorize_shader
	#Socket_3
	group.inputs[2].default_value = (1.0, 0.01, 0.37, 1.0)
	#Socket_4
	group.inputs[3].default_value = (0.63, 0.01, 1.0, 1.0)

	#Set locations
	material_output.location = (-60.0, 320.0)
	color_image.location = (-920.0, 400.0)
	color_mask_image.location = (-920.0, 100.0)
	uv_map.location = (-1260.0, 40.0)
	group.location = (-420.0, 320.0)

	#Set dimensions
	material_output.width, material_output.height = 140.0, 100.0
	color_image.width, color_image.height = 280.0, 100.0
	color_mask_image.width, color_mask_image.height = 280.0, 100.0
	uv_map.width, uv_map.height = 140.0, 100.0
	group.width, group.height = 240.0, 100.0

	#initialize bombsquad_character_material links
	#uv_map.UV -> color_image.Vector
	bombsquad_character_material.links.new(uv_map.outputs[0], color_image.inputs[0])
	#uv_map.UV -> color_mask_image.Vector
	bombsquad_character_material.links.new(uv_map.outputs[0], color_mask_image.inputs[0])
	#group.BSDF -> material_output.Surface
	bombsquad_character_material.links.new(group.outputs[0], material_output.inputs[0])
	#color_image.Color -> group.Texture
	bombsquad_character_material.links.new(color_image.outputs[0], group.inputs[0])
	#color_mask_image.Color -> group.Color Mask
	bombsquad_character_material.links.new(color_mask_image.outputs[0], group.inputs[1])

	return mat


# bombsquad_character_material = create_bombsquad_character_material_node_group(
# 	name="char mat",
# 	color_image_src = None,
# 	color_mask_image_src = None,
# 	uv_map_name = "Float2",
# )

