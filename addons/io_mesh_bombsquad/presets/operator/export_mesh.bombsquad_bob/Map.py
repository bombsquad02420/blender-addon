import bpy

def set_operator_properties(op):
	op.apply_object_transformations = True

set_operator_properties(bpy.context.active_operator)
