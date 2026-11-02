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
		segments = [s for a in settings.attachments for s in a.segments]
		if isinstance(block, bpy.types.Mesh):
			used = (any(r.mesh == block for r in settings.parts) or any(s.mesh_block == block for s in segments)
				or any(o.data == block for o in collection.all_objects))
		else:
			used = any(r.image == block for r in settings.textures) or any(block in (s.texture_block, s.mask_block) for s in segments)
		if used:
			found.append(collection)
	return found


def make_unique_mesh(collection, row):
	"""Give a Parts row its own copy of its mesh."""
	name = f'{collection.name.split(".")[0]}_left_{row.part}' if row.side == 'L' else f'{collection.name.split(".")[0]}_{row.part}'
	copy = part_scene.copy_mesh(row.mesh, name)
	row.mesh = copy
	copy.ballistica_asset.path = part_scene._free_path(collection, row)
	return copy


def make_unique_image(collection, item):
	"""Give a Textures row its own copy of its image (unsaved paint included)."""
	copy = copy_image(item.image, f'{collection.name.split(".")[0]}_{texture_scene.SUFFIXES[item.field]}')
	item.image = copy
	copy.ballistica_texture.path = texture_scene._free_path(collection, item)
	return copy


def make_unique_segment(segment, key):
	"""Give a segment its own copy of its mesh, texture or mask ('mesh', 'texture', 'mask_texture')."""
	from . import attach_scene
	from .props import SEGMENT_BLOCKS

	collection, index, j = attach_scene._locate(segment)
	block = getattr(segment, SEGMENT_BLOCKS[key])
	path = attach_scene.default_path(collection, index, j, key)
	name = path.rsplit('/', 1)[-1]
	if key == 'mesh':
		copy = part_scene.copy_mesh(block, name)
		copy.ballistica_asset.path = attach_scene._free(path, copy)
	else:
		copy = copy_image(block, name)
		copy.ballistica_texture.path = attach_scene._free(path, copy)
	setattr(segment, SEGMENT_BLOCKS[key], copy)  # mirrors the path and rebuilds
	return copy


def copy_image(image, name):
	"""A new image with `image`'s pixels (unsaved paint included) and settings."""
	width, height = image.size
	copy = bpy.data.images.new(name, width, height, alpha=True)
	copy.colorspace_settings.name = image.colorspace_settings.name  # before the pixels: it regenerates
	if image.has_data or image.filepath:
		pixels = [0.0] * (width * height * 4)
		image.pixels.foreach_get(pixels)
		copy.pixels.foreach_set(pixels)
	copy.file_format = 'PNG'
	for name in ('role', 'quality', 'wrap_h', 'wrap_v', 'alpha'):
		copy.ballistica_texture[name] = image.ballistica_texture.get(name, 0)
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
		for attachment in settings.attachments:
			for segment in attachment.segments:
				for block in (segment.mesh_block, segment.texture_block, segment.mask_block):
					path = block.ballistica_asset.path if isinstance(block, bpy.types.Mesh) else block.ballistica_texture.path if block else ''
					if path:
						paths.setdefault(path, set()).add(block)
	problems = []
	for path, blocks in sorted(paths.items()):
		if len(blocks) > 1:
			names = ', '.join(sorted(b.name for b in blocks))
			problems.append(f"{path} is the export path of {len(blocks)} different meshes or images ({names}); "
				"they'd overwrite each other. Change one's export path, or pick the same one")
	return problems
