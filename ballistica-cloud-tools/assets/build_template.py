"""Rebuild assets/template/ (the New Character starter body) and
assets/attachments/ (the attachment templates, attach_templates.py).

	make template   (in ballistica-cloud-tools)
	# or: blender -b --factory-startup --python assets/build_template.py

Writes one OBJ per body part (game axes, as a workspace stores them) and
the color / color mask / icon / icon mask PNGs, all from template.py. The
files are committed and shipped; New Character copies them into the new
character, so they can also be edited by hand instead of regenerated.
"""

import importlib.util
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location('ballistica_cloud_tools', os.path.join(ADDON, '__init__.py'), submodule_search_locations=[ADDON])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from ballistica_cloud_tools import attach_templates, objfile, template  # noqa: E402

OUT = os.path.join(HERE, 'template')
os.makedirs(OUT, exist_ok=True)
for part in template.CUBOIDS:
	objfile.write(os.path.join(OUT, f'{part}.obj'), template.cuboid(part))
color, mask = template.textures(template.TEXTURE_SIZE)
icon, icon_mask = template.icon(template.ICON_SIZE)
for name, pixels, size in (
	('color', color, template.TEXTURE_SIZE), ('color_mask', mask, template.TEXTURE_SIZE),
	('icon', icon, template.ICON_SIZE), ('icon_mask', icon_mask, template.ICON_SIZE),
):
	image = bpy.data.images.new(name, size, size, alpha=True)
	if 'mask' in name:
		image.colorspace_settings.name = 'Non-Color'
	image.pixels.foreach_set(pixels)
	image.filepath_raw = os.path.join(OUT, f'{name}.png')
	image.file_format = 'PNG'
	image.save()
print('wrote', OUT)

# Attachment templates: one OBJ per segment, and a small color and mask.
os.makedirs(attach_templates.TEMPLATE_DIR, exist_ok=True)
for item in attach_templates.TEMPLATES:
	for index, make in enumerate(item.segments):
		objfile.write(attach_templates.obj_path(item.key, index, len(item.segments)), make())
	color, mask = item.textures()
	for is_mask, pixels in ((False, color), (True, mask)):
		size = attach_templates.TEXTURE_SIZE
		image = bpy.data.images.new(f'{item.key}_{is_mask}', size, size, alpha=True)
		if is_mask:
			image.colorspace_settings.name = 'Non-Color'
		image.pixels.foreach_set(pixels)
		image.filepath_raw = attach_templates.texture_path(item.key, is_mask)
		image.file_format = 'PNG'
		image.save()
print('wrote', attach_templates.TEMPLATE_DIR)
