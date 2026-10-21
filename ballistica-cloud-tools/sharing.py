"""Meshes and images shared between characters.

A part's mesh or a body texture can be used by several characters (the
classic characters share meshes, and the pickers can pick anything).
Editing a shared one changes every character using it, so the panel says
how many use it and offers Make Unique: a copy with its own export path.
Two different meshes (or images) given the same export path would
overwrite each other's file, which Check reports.
"""

import bpy

from . import part_scene, texture_scene


def characters():
	return [c for c in bpy.data.collections if c.ballistica_character.is_character]


def users(block):
	"""Characters whose parts, textures or attachment objects use `block`."""
	found = []
	for collection in characters():
		settings = collection.ballistica_character
		if isinstance(block, bpy.types.Mesh):
			used = any(r.mesh == block for r in settings.parts) or any(o.data == block for o in collection.all_objects)
		else:
			used = any(r.image == block for r in settings.textures)
		if used:
			found.append(collection)
	return found


def make_unique_mesh(collection, row):
	"""Give a Parts row its own copy of its mesh."""
	name = f'{collection.name}_left_{row.part}' if row.side == 'L' else f'{collection.name}_{row.part}'
	copy = part_scene.copy_mesh(row.mesh, name)
	row.mesh = copy
	copy.ballistica_asset.path = part_scene._free_path(collection, row)
	return copy


def make_unique_image(collection, item):
	"""Give a Textures row its own copy of its image (unsaved paint included)."""
	image = item.image
	width, height = image.size
	copy = bpy.data.images.new(f'{collection.name}_{texture_scene.SUFFIXES[item.field]}', width, height, alpha=True)
	copy.colorspace_settings.name = image.colorspace_settings.name  # before the pixels: it regenerates
	if image.has_data or image.filepath:
		pixels = [0.0] * (width * height * 4)
		image.pixels.foreach_get(pixels)
		copy.pixels.foreach_set(pixels)
	copy.file_format = 'PNG'
	for name in ('role', 'quality', 'wrap_h', 'wrap_v', 'alpha'):
		copy.ballistica_texture[name] = image.ballistica_texture.get(name, 0)
	item.image = copy
	copy.ballistica_texture.path = texture_scene._free_path(collection, item)
	return copy


def duplicate_paths(collection):
	"""Problems: one export path given to different meshes or images.

	Looks at every character in the same workspace, since they write into
	the same folder.
	"""
	root = collection.ballistica_character.workspace_root
	paths = {}
	for other in characters():
		settings = other.ballistica_character
		if settings.workspace_root != root:
			continue
		for row in settings.parts:
			if row.enabled and row.mesh is not None and row.mesh.ballistica_asset.path:
				paths.setdefault(row.mesh.ballistica_asset.path, set()).add(row.mesh)
		for item in settings.textures:
			if item.image is not None and item.image.ballistica_texture.path:
				paths.setdefault(item.image.ballistica_texture.path, set()).add(item.image)
	problems = []
	for path, blocks in sorted(paths.items()):
		if len(blocks) > 1:
			names = ', '.join(sorted(b.name for b in blocks))
			problems.append(f"{path} is the export path of {len(blocks)} different meshes or images ({names}); "
				"they'd overwrite each other. Change one's export path, or pick the same one")
	return problems
