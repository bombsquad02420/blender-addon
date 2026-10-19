"""Rebuild assets/ballistica_assets.blend (the bundled asset library).

	make assets   (in ballistica-cloud-tools)
	# or: blender -b --factory-startup --python assets/build_assets.py

Creates the "Ballistica Colorize" and "Ballistica Eye" node groups (marked
as assets in the "Ballistica" catalog), the eye meshes from source/*.obj
and the packed eye textures from source/*.png, and saves the file next to
this script.

Eye meshes get the engine's fixed transforms baked in (DrawEyeBalls /
DrawEyeLids in spaz_node.cc): scale kSpazRigEyeMeshScale, and the
eyeball (ball + iris, one mesh) pitched kSpazRigEyeballPitch so it looks
slightly down.
"""

import importlib.util
import os
import uuid

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_ID = 'b9c1e3a4-6f2d-4f5e-9a7b-3c2d1e0f4a5b'  # fixed so catalog assignments stay stable
CATALOG_FILE = """# This is an Asset Catalog Definition file for Blender.
#
# Empty lines and lines starting with `#` will be ignored.
# The first non-ignored line should be the version indicator.
# Other lines are of the format "UUID:catalog/path/for/assets:simple catalog name"

VERSION 1

{id}:Ballistica:Ballistica
"""

import math  # noqa: E402
import sys  # noqa: E402

import bmesh  # noqa: E402
from mathutils import Matrix  # noqa: E402

ADDON = os.path.dirname(HERE)
SOURCE = os.path.join(HERE, 'source')
spec = importlib.util.spec_from_file_location('ballistica_cloud_tools', os.path.join(ADDON, '__init__.py'), submodule_search_locations=[ADDON])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from ballistica_cloud_tools import nodegroup, rig, scene  # noqa: E402

assert str(uuid.UUID(CATALOG_ID)) == CATALOG_ID

# Start from an empty file (the factory scene has a cube, camera, light...).
for collection in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.node_groups,
		bpy.data.cameras, bpy.data.lights, bpy.data.images):
	for item in list(collection):
		collection.remove(item)
for create in (nodegroup.create, nodegroup.create_eye):
	group = create()
	group.asset_mark()
	group.asset_data.catalog_id = CATALOG_ID
	group.asset_data.description = group.description
	group.asset_data.author = "Ballistica Cloud Tools"
	group.asset_data.tags.new("BombSquad")
	group.asset_data.tags.new("Character")
	group.use_fake_user = True


def mesh(name, sources, transform):
	"""Join OBJ sources into one Blender mesh with `transform` applied."""
	bm = bmesh.new()
	for source in sources:
		part = scene.mesh_from_obj(os.path.join(SOURCE, f'{source}.obj'), source)
		bm.from_mesh(part)
		bpy.data.meshes.remove(part)
	bm.transform(transform)
	out = bpy.data.meshes.new(name)
	bm.to_mesh(out)
	bm.free()
	out.materials.append(None)  # one slot; objects assign their own material
	out.use_fake_user = True
	return out


eye_scale = Matrix.Scale(rig.EYE_MESH_SCALE, 4)
# Pitch about +X; positive turns the iris (+Z) down, which is what the rig
# describes for kSpazRigEyeballPitch (-10, "looks slightly down").
pitch = Matrix.Rotation(math.radians(abs(rig.EYEBALL_PITCH)), 4, 'X')
mesh('eye_ball', ('eye_ball', 'eye_ball_iris'), pitch @ eye_scale)
mesh('eye_lid', ('eye_lid',), eye_scale)
for name in nodegroup.EYE_IMAGES:
	image = bpy.data.images.load(os.path.join(SOURCE, f'{name}.png'))
	image.name = name
	if 'mask' in name:
		image.colorspace_settings.name = 'Non-Color'
	image.pack()
	image.use_fake_user = True

with open(os.path.join(HERE, 'blender_assets.cats.txt'), 'w', newline='\n') as outfile:
	outfile.write(CATALOG_FILE.format(id=CATALOG_ID))
bpy.ops.wm.save_as_mainfile(filepath=nodegroup.ASSETS_BLEND, compress=True, copy=True)
print('built', nodegroup.ASSETS_BLEND)
