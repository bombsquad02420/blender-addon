import bpy
op = bpy.context.active_operator

op.group_into_collection = True
op.setup_collection_exporter = True
op.arrange_character_meshes = False
