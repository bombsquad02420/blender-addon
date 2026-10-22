"""Rebuild assets/ballistica_assets.blend (the bundled asset library).

	make assets   (in ballistica-cloud-tools)
	# or: blender -b --factory-startup --python assets/build_assets.py

Creates the "Ballistica Colorize" and "Ballistica Eye" node groups (marked
as assets in the "Ballistica" catalog), the eye meshes from source/*.obj
the packed eye textures from source/*.png and the reflection environments
(source/cubemaps, resampled to equirectangular), and saves the file next to
this script.

Eye meshes get the engine's fixed transforms baked in (DrawEyeBalls /
DrawEyeLids in spaz_node.cc): scale kSpazRigEyeMeshScale, and the
eyeball (ball + iris, one mesh with a material slot each) pitched kSpazRigEyeballPitch so it looks
slightly down.
"""

import importlib.util
import os
import uuid

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_ID = 'b9c1e3a4-6f2d-4f5e-9a7b-3c2d1e0f4a5b'  # fixed so catalog assignments stay stable
BRUSH_CATALOG_ID = '4e2a7c1d-8b3f-4a6e-9d5c-2f1b0e7a3c68'  # the mask brushes' own tab in the brush shelf
CATALOG_FILE = """# This is an Asset Catalog Definition file for Blender.
#
# Empty lines and lines starting with `#` will be ignored.
# The first non-ignored line should be the version indicator.
# Other lines are of the format "UUID:catalog/path/for/assets:simple catalog name"

VERSION 1

{id}:Ballistica:Ballistica
{brushes}:Ballistica/Mask Brushes:Ballistica-Mask Brushes
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
from ballistica_cloud_tools import nodegroup, paint, rig, scene  # noqa: E402

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
	"""Join OBJ sources into one Blender mesh with `transform` applied.

	Each source gets its own material slot (faces keep the source's index).
	"""
	bm = bmesh.new()
	for index, source in enumerate(sources):
		part = scene.mesh_from_obj(os.path.join(SOURCE, f'{source}.obj'), source)
		for poly in part.polygons:
			poly.material_index = index
		bm.from_mesh(part)
		bpy.data.meshes.remove(part)
	bm.transform(transform)
	out = bpy.data.meshes.new(name)
	bm.to_mesh(out)
	bm.free()
	for _ in sources:
		out.materials.append(None)  # objects assign their own materials
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



def equirect_from_cubemap(name, width=1024):
	"""Packed equirectangular image from source/cubemaps/<name>_{px..nz}.png.

	Blender's Environment Texture only takes equirectangular images, so the
	game's cubemaps are resampled: each output pixel's direction (Cycles'
	equirectangular mapping, Blender axes) is turned into game axes and
	looked up with OpenGL's cube-face rules, as the engine's samplerCube
	does with its reflection vector.
	"""
	import numpy as np

	faces = {}
	for face in ('px', 'nx', 'py', 'ny', 'pz', 'nz'):
		image = bpy.data.images.load(os.path.join(SOURCE, 'cubemaps', f'{name}_{face}.png'))
		w, h = image.size
		pixels = np.empty(w * h * 4, dtype=np.float32)
		image.pixels.foreach_get(pixels)
		faces[face] = pixels.reshape(h, w, 4)[::-1]  # Blender stores bottom row first; make row 0 the top
		bpy.data.images.remove(image)
	size = faces['px'].shape[0]

	height = width // 2
	u = (np.arange(width) + 0.5) / width
	v = (np.arange(height) + 0.5) / height
	u, v = np.meshgrid(u, v)
	# Cycles: u = -atan2(y, x) / 2pi + 0.5, v = atan2(z, hypot(x, y)) / pi + 0.5
	phi = (0.5 - u) * 2 * np.pi
	theta = (v - 0.5) * np.pi
	bx, by, bz = np.cos(theta) * np.cos(phi), np.cos(theta) * np.sin(phi), np.sin(theta)
	# Blender (x, y, z) -> game (x, z, -y)
	rx, ry, rz = bx, bz, -by

	out = np.zeros((height, width, 4), dtype=np.float32)
	ax, ay, az = np.abs(rx), np.abs(ry), np.abs(rz)
	# OpenGL cube map selection: (face, mask, major, sc, tc)
	choices = (
		('px', (ax >= ay) & (ax >= az) & (rx > 0), ax, -rz, -ry),
		('nx', (ax >= ay) & (ax >= az) & (rx <= 0), ax, rz, -ry),
		('py', (ay > ax) & (ay >= az) & (ry > 0), ay, rx, rz),
		('ny', (ay > ax) & (ay >= az) & (ry <= 0), ay, rx, -rz),
		('pz', (az > ax) & (az > ay) & (rz > 0), az, rx, -ry),
		('nz', (az > ax) & (az > ay) & (rz <= 0), az, -rx, -ry),
	)
	for face, mask, major, sc, tc in choices:
		s_ = (sc[mask] / major[mask] + 1) / 2
		t_ = (tc[mask] / major[mask] + 1) / 2
		col = np.clip((s_ * size).astype(int), 0, size - 1)
		row = np.clip((t_ * size).astype(int), 0, size - 1)  # t = 0 is the top row
		out[mask] = faces[face][row, col]
	out[..., 3] = 1.0

	image = bpy.data.images.new(name, width, height)
	image.pixels.foreach_set(out.ravel())  # row 0 is v = 0, the bottom, as Blender stores it
	image.pack()
	image.use_fake_user = True
	return image


for name in nodegroup.REFLECTION_IMAGES:
	equirect_from_cubemap(name)

RGB = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
# Every thumbnail: three equal red, green and blue blobs around the middle
# (top left, top right, bottom), then the brush's own bigger blob in the
# middle, overlapping all three, doing what the brush does to them.
BLOB_RADIUS = 0.32
BLOB_CENTRES = tuple((0.44 * math.cos(math.radians(a)), 0.44 * math.sin(math.radians(a))) for a in (150, 30, 270))
STROKE_RADIUS = 0.62  # almost around the three blobs


def _cover(distance, edge):
	"""How much of a pixel `distance` inside a shape's edge is covered (0 edge: hard)."""
	if edge == 0:
		return 1.0 if distance > 0 else 0.0
	return min(max(distance / edge, 0.0), 1.0)


def _brush_preview(brush, color, kind, size=128):
	"""What the brush does to a mask: its blob over red, green and blue ones.

	add:   adds its tint (red over green makes yellow)
	erase: takes its tint away (all of them for Erase All)
	only:  covers them with its tint, with a hard edge
	"""
	pixels = []
	for y in range(size):
		for x in range(size):
			dx, dy = (x + 0.5) / size * 2 - 1, (y + 0.5) / size * 2 - 1
			rgb, alpha = [0.0, 0.0, 0.0], 0.0
			for (cx, cy), tint in zip(BLOB_CENTRES, RGB):
				cover = _cover(BLOB_RADIUS - math.hypot(dx - cx, dy - cy), 0.05)
				rgb = [min(a + b * cover, 1.0) for a, b in zip(rgb, tint)]
				alpha = max(alpha, cover)
			stroke = _cover(STROKE_RADIUS - math.hypot(dx, dy), 0 if kind == 'only' else 0.08)
			if kind == 'add':
				rgb = [min(a + b * stroke, 1.0) for a, b in zip(rgb, color)]
			elif kind == 'erase':
				rgb = [max(a - b * stroke, 0.0) for a, b in zip(rgb, color)]
				if not any(rgb):
					alpha = 0.0  # erased to nothing: the background shows through
				ring = _cover(0.025 - abs(STROKE_RADIUS - math.hypot(dx, dy)), 0.015)
				if ring:  # the brush's outline
					rgb = [a * (1 - ring) + 0.85 * ring for a in rgb]
					alpha = max(alpha, ring)
				pixels += [*rgb, alpha]
				continue
			elif stroke:
				rgb = list(color)
			alpha = max(alpha, stroke)
			pixels += [*rgb, alpha]
	preview = brush.preview_ensure()
	preview.image_size = (size, size)
	preview.image_pixels_float.foreach_set(pixels)


# The colour mask brushes (paint.BRUSHES), in their own catalog.
for brush in list(bpy.data.brushes):
	bpy.data.brushes.remove(brush)
for label, blend, color, hard, description in paint.BRUSHES.values():
	brush = bpy.data.brushes.new(paint.PREFIX + label, mode='TEXTURE_PAINT')
	brush.blend = blend
	brush.color = color
	if hard:
		brush.curve_distance_falloff_preset = 'CONSTANT'  # a hard edge
	brush.asset_mark()
	brush.asset_data.catalog_id = BRUSH_CATALOG_ID
	brush.asset_data.description = description
	brush.asset_data.author = "Ballistica Cloud Tools"
	brush.use_fake_user = True
	_brush_preview(brush, color, 'erase' if blend == 'SUB' else 'only' if hard else 'add')

with open(os.path.join(HERE, 'blender_assets.cats.txt'), 'w', newline='\n') as outfile:
	outfile.write(CATALOG_FILE.format(id=CATALOG_ID, brushes=BRUSH_CATALOG_ID))
bpy.ops.wm.save_as_mainfile(filepath=nodegroup.ASSETS_BLEND, compress=True, copy=True)
print('built', nodegroup.ASSETS_BLEND)
