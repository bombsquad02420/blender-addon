"""Reading and writing `.bchar` character definitions.

The cloud's schema is newer than what the addon models (the engine already
reads fields like per-part looks and team coloring strengths), so a
Character keeps the whole JSON it was loaded from and only changes the
fields the addon sets. Everything else round-trips untouched.
"""

import copy

from . import jsonfile, rig


class Character:
	def __init__(self, raw=None):
		if raw is None:
			raw = {'data': {'type': rig.CHARACTER_TYPE}}
		if not isinstance(raw.get('data'), dict):
			raise ValueError('Not a character definition: missing "data" object.')
		self.raw = raw

	@classmethod
	def load(cls, path):
		return cls(jsonfile.read(path))

	def save(self, path):
		"""Write to `path`; return True if the file changed."""
		return jsonfile.write(path, self.raw)

	def copy(self):
		return Character(copy.deepcopy(self.raw))

	@property
	def data(self):
		return self.raw['data']

	@property
	def type(self):
		return self.data.get('type', rig.CHARACTER_TYPE)

	def get(self, field, default=None):
		"""A field's value, else its standard-Spaz default, else `default`."""
		if field in self.data:
			return self.data[field]
		return rig.DEFAULTS.get(field, default)

	def set(self, field, value):
		"""Set a field the way the web UI would.

		An empty value (None, '' or an empty list) removes the field. A value
		equal to the default is only written if the field was already there,
		so importing and exporting an untouched character changes nothing.
		"""
		if value is None or value == '' or value == []:
			self.data.pop(field, None)
			return
		value = _plain(value)
		if field not in self.data and field in rig.DEFAULTS and _same(value, rig.DEFAULTS[field]):
			return
		self.data[field] = value

	def mesh_refs(self):
		"""(part, logical path or None) for every body part, right side."""
		return [(part, self.data.get(field)) for part, field, _ in rig.PARTS]

	def left_mesh_ref(self, part):
		return self.data.get(f'left_{part}_mesh')

	@property
	def attachments(self):
		return self.data.get('attachments', [])

	def referenced_assets(self):
		"""(field, kind, logical path) for every asset reference."""
		refs = []
		for field in ('icon_texture', 'icon_mask_texture', 'color_texture', 'color_mask_texture'):
			if self.data.get(field):
				refs.append((field, 'texture', self.data[field]))
		for part, field, _ in rig.PARTS:
			for key in (field, f'left_{part}_mesh'):
				if self.data.get(key):
					refs.append((key, 'mesh', self.data[key]))
		for field in rig.SOUND_FIELDS:
			for sound in self.data.get(field, []):
				refs.append((field, 'sound', sound))
		for i, attachment in enumerate(self.attachments):
			for j, segment in enumerate(attachment.get('segments', [])):
				where = f'attachments[{i}].segments[{j}]'
				if segment.get('mesh'):
					refs.append((f'{where}.mesh', 'mesh', segment['mesh']))
				for key in ('texture', 'mask_texture'):
					if segment.get(key):
						refs.append((f'{where}.{key}', 'texture', segment[key]))
		return refs


def _plain(value):
	"""JSON-friendly copy: tuples and Blender vectors become lists."""
	if isinstance(value, (str, bool, int)) or value is None:
		return value
	if isinstance(value, float):
		return _round(value)
	if isinstance(value, dict):
		return {k: _plain(v) for k, v in value.items()}
	return [_plain(v) for v in value]


def _round(value):
	# Blender stores floats as float32; keep files readable (0.3, not
	# 0.30000001192092896) without losing meaningful precision.
	rounded = round(value, 6)
	return 0.0 if rounded == 0 else rounded


def _same(a, b):
	if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
		return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
	if isinstance(a, float) or isinstance(b, float):
		return abs(a - b) < 1e-6
	return a == b
