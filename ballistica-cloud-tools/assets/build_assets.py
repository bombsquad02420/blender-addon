"""Rebuild assets/ballistica_assets.blend (the bundled asset library).

	make cloud-assets
	# or: blender -b --factory-startup --python assets/build_assets.py

Creates the "Ballistica Colorize" node group, marks it as an asset in the
"Ballistica" catalog, and saves the file next to this script.
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

spec = importlib.util.spec_from_file_location('nodegroup', os.path.join(os.path.dirname(HERE), 'nodegroup.py'))
nodegroup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nodegroup)

assert str(uuid.UUID(CATALOG_ID)) == CATALOG_ID

for group in list(bpy.data.node_groups):
	bpy.data.node_groups.remove(group)
group = nodegroup.create()
group.asset_mark()
group.asset_data.catalog_id = CATALOG_ID
group.asset_data.description = group.description
group.asset_data.author = "Ballistica Cloud Tools"
group.asset_data.tags.new("BombSquad")
group.asset_data.tags.new("Character")
group.use_fake_user = True

with open(os.path.join(HERE, 'blender_assets.cats.txt'), 'w', newline='\n') as outfile:
	outfile.write(CATALOG_FILE.format(id=CATALOG_ID))
bpy.ops.wm.save_as_mainfile(filepath=nodegroup.ASSETS_BLEND, compress=True, copy=True)
print('built', nodegroup.ASSETS_BLEND)
