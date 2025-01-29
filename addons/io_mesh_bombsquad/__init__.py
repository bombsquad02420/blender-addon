import os
import json
import bpy
import bmesh
import bpy_extras
import math
from mathutils import Vector

from contextlib import contextmanager
from collections import defaultdict

from . import bob
from . import cob


# region BOB


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


# region COB


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


# region LevelDefs


class IMPORT_SCENE_OT_bombsquad_leveldefs(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    """Load Bombsquad Level Defs"""
    bl_idname = "import_scene.bombsquad_leveldefs"
    bl_label = "Import Bombsquad Level Definitions"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}
    
    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
    )

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filter_glob',))
        filepath = os.fsencode(keywords["filepath"])
        data = None
        with open(filepath, "r") as file:
            data = json.load(file)

        if data is None or "locations" not in data:
            return {'CANCELLED'}

        collection_name = bpy.path.display_name_from_filepath(filepath)
        scene = bpy.context.scene
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)
        bpy.context.view_layer.update()

        # This matrix is different from the one used in bob and cob formats
        matrix = bpy_extras.io_utils.axis_conversion(from_forward='Z', from_up='-Y').to_3x3()

        for location_type, locations in data["locations"].items():
            for location in locations:
                if "center" in location and "size" in location:
                    center = Vector(location["center"][0:3]) @ matrix
                    size = Vector(location["size"][0:3]).xzy
                    self.add_region(
                        context,
                        center=center,
                        size=size,
                        collection=collection.name,
                        location_type=location_type,
                    )
                elif "center" in location:
                    center = Vector(location["center"][0:3]) @ matrix
                    self.add_point(
                        context,
                        center=center,
                        collection=collection.name,
                        location_type=location_type,
                    )

        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.update()
        return {'FINISHED'}

    def add_point(self, context,
            center, collection, location_type):
        bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', radius=0.25, location=center, scale=(1, 1, 1))
        empty = context.active_object
        empty.show_name = True
        # blender will autoincrement this counter if the name already exists
        empty.name = location_type + ".000"
        bpy.data.collections[collection].objects.link(empty)
        context.collection.objects.unlink(empty)
        return empty

    def add_region(self, context,
            center, size, collection, location_type):
        radius = 1.0
        if location_type in ['area_of_interest_bounds', 'map_bounds']:
            # these were known as boxes in previuos versions
            # for boxes, the size represents the overall dimension
            # otherwise, size is the distance of the lower and upper limit from the center
            # this is why we halve the internal size for "boxes"
            # so that the numbers you see in blender ui match those in the level definitions json file
            # see: get_def_bound_box and get_start_position in ballistica source code
            radius = 0.5
        bpy.ops.object.empty_add(type='CUBE', align='WORLD', radius=radius, location=center, scale=(1, 1, 1))
        empty = context.active_object
        if location_type in ['ffa_spawn', 'spawn', 'spawn_by_flag']:
            # bombsquad ignores the vertical size for spawn points,
            # so we can set it to some small number to make it easier to read in the 3d view
            # see: get_start_position in ballistica source code
            size.z = 0.05
        empty.scale = size
        empty.show_name = True
        # blender will autoincrement tis counter if the name already exists
        empty.name = location_type + ".000"
        bpy.data.collections[collection].objects.link(empty)
        context.collection.objects.unlink(empty)
        return empty


class EXPORT_SCENE_OT_bombsquad_leveldefs(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    """Save Bombsquad Level Defs"""
    bl_idname = "export_scene.bombsquad_leveldefs"
    bl_label = "Export Bombsquad Level Definitions"
    bl_options = {'REGISTER', 'PRESET'}

    filename_ext = ".json"
    check_extension = True
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
    )

    @classmethod
    def poll(cls, context):
        return context.collection is not None and len(context.collection.objects) > 0

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filter_glob',))
        filepath = os.fsencode(keywords["filepath"])

        collection = context.collection
        objects = sorted(collection.objects.values(), key=lambda obj: obj.name)

        if len(objects)==0:
            return {'CANCELLED'}

        # This matrix is different from the one used in bob and cob formats
        matrix = bpy_extras.io_utils.axis_conversion(to_forward='Z', to_up='-Y').to_3x3()

        data_locations = {}
        for obj in objects:
            if obj.type == "EMPTY" and obj.empty_display_type  == "CUBE":
                location_type = obj.name.split('.')[0]
                if location_type in ['area_of_interest_bounds', 'map_bounds']:
                    assert obj.empty_display_size == 0.5
                else:
                    assert obj.empty_display_size == 1.0
                center = obj.matrix_world.to_translation() @ matrix
                size = obj.matrix_world.to_scale().xzy
                if location_type not in data_locations:
                    data_locations[location_type] = []
                data_locations[location_type].append({
                    "center": [round(n, 2) for n in center],
                    "size": [round(n, 2) for n in size],
                })
            elif obj.type == "EMPTY" and obj.empty_display_type  == "PLAIN_AXES":
                location_type = obj.name.split('.')[0]
                center = obj.matrix_world.to_translation() @ matrix
                if location_type not in data_locations:
                    data_locations[location_type] = []
                data_locations[location_type].append({
                    "center": [round(n, 2) for n in center],
                })

        data = {}
        # TODO: add check_existing flag
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                data = json.load(file)

        data["locations"] = data_locations

        with open(filepath, "w") as file:
            json.dump(data, file, indent=2, sort_keys=True)

        return {'FINISHED'}


# Enables importing files by draggin and dropping into the blender UI
# Enables export via collection exporter
class IO_FH_bombsquad_leveldefs(bpy.types.FileHandler):
    bl_idname = "IO_FH_bombsquad_leveldefs"
    bl_label = "BombSquad Level Definitions"
    bl_import_operator = "import_mesh.bombsquad_leveldefs"
    bl_export_operator = "export_mesh.bombsquad_leveldefs"
    bl_file_extensions = ".json"

    @classmethod
    def poll_drop(cls, context):
        # drop sohuld only be allowed in 3d view and outliner
        return bpy_extras.io_utils.poll_file_object_drop(context)


def menu_func_import_leveldefs(self, context):
    self.layout.operator(IMPORT_SCENE_OT_bombsquad_leveldefs.bl_idname, text="Bombsquad Level Definitions (.json)")


def menu_func_export_leveldefs(self, context):
    self.layout.operator(EXPORT_SCENE_OT_bombsquad_leveldefs.bl_idname, text="Bombsquad Level Definitions (.json)")


# region Addon Lifecycle


classes = (
    IMPORT_MESH_OT_bombsquad_bob,
    EXPORT_MESH_OT_bombsquad_bob,
    IO_FH_bombsquad_bob,
    IMPORT_MESH_OT_bombsquad_cob,
    EXPORT_MESH_OT_bombsquad_cob,
    IO_FH_bombsquad_cob,
    IMPORT_SCENE_OT_bombsquad_leveldefs,
    EXPORT_SCENE_OT_bombsquad_leveldefs,
    IO_FH_bombsquad_leveldefs,
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
