import bpy

def set_operator_properties(op):
	op.group_into_collection = True
	op.setup_collection_exporter = True
	op.arrange_character_meshes = False

set_operator_properties(bpy.context.active_operator)
