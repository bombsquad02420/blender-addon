import bpy

print("hello from blender")

print([obj.name for obj in bpy.context.scene.collection.all_objects])
bpy.ops.object.delete()
print([obj.name for obj in bpy.context.scene.collection.all_objects])

print("done")
