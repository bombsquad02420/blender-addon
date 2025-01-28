import os
import bpy
import bmesh
import bpy_extras
import math
from mathutils import Vector

from contextlib import contextmanager
from collections import defaultdict

from . import bob
from . import cob

bl_info = {
    "name": "Import/Export BombSquad models",
    "description": "Import and export BombSquad models in the .bob and .cob formats",
    "author": "Mrmaxmeier, aryan02420",
    "version": (3, 0),
    "blender": (4, 2, 0),
    "location": "File > Import-Export",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export"
}

@contextmanager
def to_bmesh(mesh, save=False):
    try:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        yield bm
    finally:
        if save:
            bm.to_mesh(mesh)
        bm.free()
        del bm


class IMPORT_MESH_OT_bombsquad_bob(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    """Load a Bombsquad Mesh file"""
    bl_idname = "import_mesh.bombsquad_bob"
    bl_label = "Import Bombsquad Mesh"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".bob"
    filter_glob: bpy.props.StringProperty(
        default="*.bob",
        options={'HIDDEN'},
    )

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filter_glob',))
        mesh = self.import_bob(context, **keywords)
        if not mesh:
            return {'CANCELLED'}

        scene = bpy.context.scene
        obj = bpy.data.objects.new(mesh.name, mesh)
        scene.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.context.view_layer.update()
        return {'FINISHED'}
    
    def import_bob(self, context, filepath):
        filepath = os.fsencode(filepath)
        with open(filepath, 'rb') as file:
            bob_data = bob.deserialize(file)
            bob_name = bpy.path.display_name_from_filepath(filepath)
            mesh = bpy.data.meshes.new(name=bob_name)
            return bob.to_mesh(mesh=mesh, bob_data=bob_data)


class EXPORT_MESH_OT_bombsquad_bob(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    """Save a Bombsquad Mesh file"""
    bl_idname = "export_mesh.bombsquad_bob"
    bl_label = "Export Bombsquad Mesh"
    bl_options = {'REGISTER', 'PRESET'}

    filter_glob: bpy.props.StringProperty(
        default="*.bob",
        options={'HIDDEN'},
    )
    check_extension = True
    filename_ext = ".bob"

    apply_object_transformations: bpy.props.BoolProperty(
        name="Apply Object Transformations",
        description="",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        keywords = self.as_keywords(ignore=(
            'check_existing',
            'filter_glob',
        ))
        return self.export_bob(context, **keywords)

    def export_bob(self, context, filepath,
            apply_object_transformations):
        scene = context.scene
        obj = bpy.context.active_object
        mesh = obj.to_mesh()
        
        if apply_object_transformations:
            mesh.transform(obj.matrix_world)

        filepath = os.fsencode(filepath)

        with open(filepath, 'wb') as file:
            bob_data = bob.from_mesh(mesh)
            bob.serialize(bob_data, file)

        return {'FINISHED'}


# Enables importing files by draggin and dropping into the blender UI
# Enables export via collection exporter
class IO_FH_bombsquad_bob(bpy.types.FileHandler):
    bl_idname = "IO_FH_bombsquad_bob"
    bl_label = "BombSquad Mesh"
    bl_import_operator = "import_mesh.bombsquad_bob"
    bl_export_operator = "export_mesh.bombsquad_bob"
    bl_file_extensions = ".bob"

    @classmethod
    def poll_drop(cls, context):
        # drop sohuld only be allowed in 3d view and outliner
        return bpy_extras.io_utils.poll_file_object_drop(context)


def menu_func_import_bob(self, context):
    self.layout.operator(IMPORT_MESH_OT_bombsquad_bob.bl_idname, text="Bombsquad Mesh (.bob)")


def menu_func_export_bob(self, context):
    self.layout.operator(EXPORT_MESH_OT_bombsquad_bob.bl_idname, text="Bombsquad Mesh (.bob)")


class IMPORT_MESH_OT_bombsquad_cob(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    """Load a Bombsquad Collision Mesh"""
    bl_idname = "import_mesh.bombsquad_cob"
    bl_label = "Import Bombsquad Collision Mesh"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".cob"
    filter_glob: bpy.props.StringProperty(
        default="*.cob",
        options={'HIDDEN'},
    )

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filter_glob',))
        mesh = self.import_cob(context, **keywords)
        if not mesh:
            return {'CANCELLED'}

        scene = bpy.context.scene
        obj = bpy.data.objects.new(mesh.name, mesh)
        scene.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.context.view_layer.update()
        return {'FINISHED'}

    def import_cob(self, context, filepath):
        filepath = os.fsencode(filepath)
        with open(filepath, 'rb') as file:
            cob_data = cob.deserialize(file)
            print(cob_data)
            cob_name = bpy.path.display_name_from_filepath(filepath)
            mesh = bpy.data.meshes.new(name=cob_name)
            return cob.to_mesh(mesh=mesh, cob_data=cob_data)


class EXPORT_MESH_OT_bombsquad_cob(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    """Save a Bombsquad Collision Mesh file"""
    bl_idname = "export_mesh.bombsquad_cob"
    bl_label = "Export Bombsquad Collision Mesh"
    bl_options = {'REGISTER', 'PRESET'}

    filter_glob: bpy.props.StringProperty(
        default="*.cob",
        options={'HIDDEN'},
    )
    check_extension = True
    filename_ext = ".cob"

    apply_object_transformations: bpy.props.BoolProperty(
        name="Apply Object Transformations",
        description="",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        keywords = self.as_keywords(ignore=(
            'check_existing',
            'filter_glob',
        ))
        return self.export_cob(context, **keywords)

    def export_cob(self, context, filepath,
            apply_object_transformations):
        scene = context.scene
        obj = bpy.context.active_object
        mesh = obj.to_mesh()

        if apply_object_transformations:
            mesh.transform(obj.matrix_world)

        filepath = os.fsencode(filepath)

        with open(filepath, 'wb') as file:
            cob_data = cob.from_mesh(mesh)
            cob.serialize(cob_data, file)

        return {'FINISHED'}


# Enables importing files by draggin and dropping into the blender UI
# Enables export via collection exporter
class IO_FH_bombsquad_cob(bpy.types.FileHandler):
    bl_idname = "IO_FH_bombsquad_cob"
    bl_label = "BombSquad Collision Mesh"
    bl_import_operator = "import_mesh.bombsquad_cob"
    bl_export_operator = "export_mesh.bombsquad_cob"
    bl_file_extensions = ".cob"

    @classmethod
    def poll_drop(cls, context):
        # drop sohuld only be allowed in 3d view and outliner
        return bpy_extras.io_utils.poll_file_object_drop(context)


def menu_func_import_cob(self, context):
    self.layout.operator(IMPORT_MESH_OT_bombsquad_cob.bl_idname, text="Bombsquad Collision Mesh (.cob)")


def menu_func_export_cob(self, context):
    self.layout.operator(EXPORT_MESH_OT_bombsquad_cob.bl_idname, text="Bombsquad Collision Mesh (.cob)")


def flpV(vector):
    vector = vector.copy()
    vector.y = -vector.y
    return vector.xzy


class IMPORT_SCENE_OT_bombsquad_leveldefs(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    """Load Bombsquad Level Defs"""
    bl_idname = "import_scene.bombsquad_leveldefs"
    bl_label = "Import Bombsquad Level Definitions"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
    )

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filter_glob',))
        print("executing", keywords["filepath"])
        data = {}
        with open(os.fsencode(keywords["filepath"]), "r") as file:
            exec(file.read(), data)
        del data["__builtins__"]
        if "points" not in data or "boxes" not in data:
            return {'CANCELLED'}

        scene = bpy.context.scene
        points = bpy.data.collections.new("points")
        bpy.context.scene.collection.children.link(points)
        boxes = bpy.data.collections.new("boxes")
        scene.collection.children.link(boxes)
        scene.cursor.location = (0,0,0)
        bpy.context.view_layer.update()

        def makeBox(middle, scale, collection):
            bpy.ops.mesh.primitive_cube_add(location=middle)
            cube = bpy.context.active_object
            cube.scale = scale
            cube.show_name = True
            cube.show_wire = True
            cube.display_type = 'WIRE'
            cube.name = key
            bpy.data.collections[collection].objects.link(cube)
            bpy.context.collection.objects.unlink(cube)
            return cube

        for key, pos in data["points"].items():
            if len(pos) == 6:
                middle, size = Vector(pos[:3]), Vector(pos[3:])
                if "spawn" in key.lower():
                    size.y = 0.05
                cube = makeBox((middle.x,-middle.z,middle.y), size, 'points')
                bpy.ops.object.select_all(action='DESELECT')
                cube.select_set(True)
                bpy.context.view_layer.objects.active = cube
                scene.tool_settings.transform_pivot_point = 'CURSOR'
                bpy.ops.transform.rotate(value=-math.pi/2, orient_axis='X', orient_type='GLOBAL')

            else:
                empty = bpy.data.objects.new(key, None)
                middle = Vector(pos[:3])
                empty.location = (middle.x,-middle.z,middle.y)
                empty.empty_display_size = 0.45
                points.objects.link(empty)
                empty.show_name = True
                bpy.ops.object.select_all(action='DESELECT')
                empty.select_set(True)
                bpy.context.view_layer.objects.active = empty
                scene.tool_settings.transform_pivot_point = 'CURSOR'
                bpy.ops.transform.rotate(value=-math.pi/2, orient_axis='X', orient_type='GLOBAL')

        for key, pos in data["boxes"].items():
            middle, size = Vector(pos[:3]), flpV(Vector(pos[6:9]))
            cube = makeBox((middle.x,-middle.z,middle.y), size/2, 'boxes')

        bpy.context.view_layer.update()
        return {'FINISHED'}


class EXPORT_SCENE_OT_bombsquad_leveldefs(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    """Export Bombsquad Level Defs"""
    bl_idname = "export_scene.bombsquad_leveldefs"
    bl_label = "Export Bombsquad Level Definitions"
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
    )

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filter_glob',))
        filepath = keywords["filepath"]
        print("writing level defs", filepath)

        if len(bpy.data.collections["points"].objects)==0 or len(bpy.data.collections["boxes"].objects)==0:
            return {'CANCELLED'}

        def v_to_str(v, flip=True, isScale=False):
            if flip:
                v = flpV(v)
            if isScale:
                v = Vector([abs(n) for n in v])
            return repr(tuple([round(n, 5) for n in tuple(v)]))

        with open(os.fsencode(filepath), "w+") as file:
            file.write("# This file generated from '{}'\n".format(os.path.basename(bpy.data.filepath)))
            file.write("points, boxes = {}, {}\n")

            for point in bpy.data.collections["points"].objects:
                pos = point.matrix_world.to_translation()
                if point.type == 'MESH':  # spawn point with random variance
                    scale = point.scale
                    file.write("points['{}'] = {}".format(point.name, v_to_str(pos)))
                    file.write(" + {}\n".format(v_to_str(scale, False, isScale=True)))
                else:
                    file.write("points['{}'] = {}\n".format(point.name, v_to_str(pos)))

            for box in bpy.data.collections["boxes"].objects:
                pos = box.matrix_world.to_translation()
                scale = box.scale*2
                file.write("boxes['{}'] = {}".format(box.name, v_to_str(pos)))
                file.write(" + (0, 0, 0) + {}\n".format(v_to_str(scale, isScale=True)))

        return {'FINISHED'}


def menu_func_import_leveldefs(self, context):
    self.layout.operator(IMPORT_SCENE_OT_bombsquad_leveldefs.bl_idname, text="Bombsquad Level Definitions (.json)")


def menu_func_export_leveldefs(self, context):
    self.layout.operator(EXPORT_SCENE_OT_bombsquad_leveldefs.bl_idname, text="Bombsquad Level Definitions (.json)")


classes = (
    IMPORT_MESH_OT_bombsquad_bob,
    EXPORT_MESH_OT_bombsquad_bob,
    IO_FH_bombsquad_bob,
    IMPORT_MESH_OT_bombsquad_cob,
    EXPORT_MESH_OT_bombsquad_cob,
    IO_FH_bombsquad_cob,
    IMPORT_SCENE_OT_bombsquad_leveldefs,
    EXPORT_SCENE_OT_bombsquad_leveldefs,
)

import_funcs = (
    menu_func_import_bob,
    menu_func_import_cob,
    menu_func_import_leveldefs,
)

export_funcs = (
    menu_func_export_bob,
    menu_func_export_cob,
    menu_func_export_leveldefs,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    for import_func in import_funcs:
        bpy.types.TOPBAR_MT_file_import.append(import_func)
    for export_func in export_funcs:
        bpy.types.TOPBAR_MT_file_export.append(export_func)


def unregister():
    from bpy.utils import unregister_class
    for export_func in reversed(export_funcs):
        bpy.types.TOPBAR_MT_file_export.remove(export_func)
    for import_func in reversed(import_funcs):
        bpy.types.TOPBAR_MT_file_import.remove(import_func)
    for cls in reversed(classes):
        unregister_class(cls)

if __name__ == "__main__":
    register()
