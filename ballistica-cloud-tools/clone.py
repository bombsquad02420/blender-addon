"""Planning a new character copied from an existing one (pure Python).

The copy gets its own meshes and textures under its new name, so editing
it never changes the original: every mesh and texture reference is
mapped to a new logical path. Settings, sounds and label string keys are
kept as they are (sounds and strings aren't edited in Blender). Two
fields that used the same file keep sharing one new file.
"""

import copy

from . import bchar, rig

TEXTURE_SUFFIXES = (
	('color_texture', 'color'),
	('color_mask_texture', 'color_mask'),
	('icon_texture', 'icon'),
	('icon_mask_texture', 'icon_color_mask'),
)


def plan(source, name):
	"""(new Character, {old mesh: new mesh}, {old texture: new texture}).

	`source` is a bchar.Character; nothing in it is modified.
	"""
	raw = copy.deepcopy(source.raw)
	character = bchar.Character(raw)
	data = character.data
	meshes, textures = {}, {}

	def remap(table, old, new):
		if not old:
			return old
		if old not in table:
			table[old] = new
		return table[old]

	data['name'] = f'strings/characters/{name}'
	for field, suffix in TEXTURE_SUFFIXES:
		if data.get(field):
			data[field] = remap(textures, data[field], f'textures/{name}_{suffix}')
	for part, field, _ in rig.PARTS:
		if data.get(field):
			data[field] = remap(meshes, data[field], f'meshes/{name}_{part}')
		left = f'left_{part}_mesh'
		if data.get(left):
			data[left] = remap(meshes, data[left], f'meshes/{name}_left_{part}')
	for i, attachment in enumerate(data.get('attachments', [])):
		segments = attachment.get('segments', [])
		for j, segment in enumerate(segments):
			base = f'{name}_attachment{i}' + (f'_{j}' if len(segments) > 1 else '')
			if segment.get('mesh'):
				segment['mesh'] = remap(meshes, segment['mesh'], f'meshes/{base}')
			if segment.get('texture'):
				segment['texture'] = remap(textures, segment['texture'], f'textures/{base}')
			if segment.get('mask_texture'):
				segment['mask_texture'] = remap(textures, segment['mask_texture'], f'textures/{base}_mask')
	return character, meshes, textures


def mask_textures(character):
	"""New texture paths that are masks (non-color data)."""
	data = character.data
	masks = {data.get('color_mask_texture'), data.get('icon_mask_texture')}
	for attachment in data.get('attachments', []):
		for segment in attachment.get('segments', []):
			masks.add(segment.get('mask_texture'))
	return {m for m in masks if m}
