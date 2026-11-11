"""One-off: extract the game's eye meshes and textures into assets/source/.

	blender -b path/to/bs_eye.blend --python assets/extract_eye_assets.py

bs_eye.blend holds eyeBall, eyeBallIris and eyeLid as imported from an
old BombSquad build's .bob files (by the bombsquad-tools addon, so in
Blender axes), with eyeColor.dds / eyeColorTintMask.dds loaded from that
build's ba_data/textures. This writes them as OBJ (game axes, unit size,
as the engine draws them before kSpazRigEyeMeshScale) and PNG, which
build_assets.py turns into the bundled asset .blend.
"""

import importlib.util
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'source')

spec = importlib.util.spec_from_file_location('ballistica_cloud_tools', os.path.join(ADDON, '__init__.py'), submodule_search_locations=[ADDON])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from ballistica_cloud_tools import objfile, scene  # noqa: E402

MESHES = {'eyeBall': 'eye_ball', 'eyeBallIris': 'eye_ball_iris', 'eyeLid': 'eye_lid'}
IMAGES = {'eyeColor.dds': ('eye_color', False), 'eyeColorTintMask.dds': ('eye_color_tint_mask', True)}

os.makedirs(OUT, exist_ok=True)
for source, name in MESHES.items():
	obj = bpy.data.objects[source]
	assert obj.matrix_world.is_identity, f'{source} has a transform; apply it first'
	objfile.write(os.path.join(OUT, f'{name}.obj'), scene.obj_from_mesh(obj.data))
	print('wrote', name)
for source, (name, data) in IMAGES.items():
	image = bpy.data.images[source]
	image.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
	out = bpy.data.images.new(name, *image.size, alpha=True)
	out.colorspace_settings.name = image.colorspace_settings.name
	out.pixels = image.pixels[:]
	out.filepath_raw = os.path.join(OUT, f'{name}.png')
	out.file_format = 'PNG'
	out.save()
	print('wrote', name, tuple(image.size))
