"""A local Ballistica asset workspace folder.

Assets are named by *logical path*: the path from the workspace root
without its extension (`meshes/agent_head.obj` is `meshes/agent_head`).
The `strings/` folder is never read: string fields are plain keys.
"""

import os

from . import jsonfile

WORKSPACE_FILE = 'workspace.json'

EXTENSIONS = {
	'mesh': ('.obj',),
	'texture': ('.png',),
	'sound': ('.wav', '.ogg'),
	'character': ('.bchar',),
}

IGNORED_DIRS = ('strings',)


def find_root(path):
	"""The workspace folder containing `path`, or None."""
	path = os.path.abspath(path)
	if os.path.isfile(path):
		path = os.path.dirname(path)
	while True:
		if os.path.isfile(os.path.join(path, WORKSPACE_FILE)):
			return path
		parent = os.path.dirname(path)
		if parent == path:
			return None
		path = parent


def logical_path(root, file_path):
	rel = os.path.relpath(os.path.abspath(file_path), root)
	return os.path.splitext(rel)[0].replace(os.sep, '/')


def file_path(root, logical, kind):
	"""The file for a logical path of `kind`, or None if it doesn't exist."""
	for ext in EXTENSIONS[kind]:
		candidate = os.path.join(root, *logical.split('/')) + ext
		if os.path.isfile(candidate):
			return candidate
	return None


def new_file_path(root, logical, kind):
	"""Where a new asset of `kind` at `logical` should be written."""
	return os.path.join(root, *logical.split('/')) + EXTENSIONS[kind][0]


def list_assets(root, kind):
	"""Sorted logical paths of every asset of `kind` in the workspace."""
	exts = EXTENSIONS[kind]
	found = []
	for base, dirs, files in os.walk(root):
		rel_base = os.path.relpath(base, root)
		if rel_base == '.':
			dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
		else:
			dirs[:] = [d for d in dirs if not d.startswith('.')]
		for name in files:
			if name.endswith(exts) and not name.startswith('.'):
				found.append(logical_path(root, os.path.join(base, name)))
	return sorted(set(found))


# Per-texture build settings in workspace.json (assets_v1 `tex_v1` path
# entries; ballistica bacommon/workspace/assetsv1.py): key -> (values,
# default). Only non-default values are stored.
TEXTURE_SETTINGS = {
	'texture_role': (('default', 'source_premultiplied', 'straight_alpha', 'data', 'premultiplied_data'), 'default'),
	'texture_quality': (('default', 'low', 'high', 'custom'), 'default'),
	'texture_wrapping_h': (('clamp', 'repeat'), 'clamp'),
	'texture_wrapping_v': (('clamp', 'repeat'), 'clamp'),
	'texture_alpha': (('auto', 'yes', 'no'), 'auto'),
}
# Roles for masks: their channels are data, not color.
DATA_ROLES = ('data', 'premultiplied_data')


def _texture_key(root, texture_file):
	return os.path.relpath(texture_file, root).replace(os.sep, '/')


def texture_settings(root, texture_file):
	"""{key: value} for every TEXTURE_SETTINGS key (defaults where unset).

	Values the addon doesn't know (a newer schema) are returned as found.
	"""
	path = os.path.join(root, WORKSPACE_FILE)
	entry = jsonfile.read(path).get('path', {}).get(_texture_key(root, texture_file), {}) if os.path.isfile(path) else {}
	return {key: entry.get(key, default) for key, (_, default) in TEXTURE_SETTINGS.items()}


def set_texture_settings(root, settings_by_file):
	"""Write textures' settings into workspace.json.

	`settings_by_file` maps a texture file to {key: value} for the keys to
	write: a default value removes the key, anything else sets it. Every
	other key is left as it is; an entry left with nothing but its type is
	removed (only textures with non-default settings are listed). Returns
	True if workspace.json changed.
	"""
	path = os.path.join(root, WORKSPACE_FILE)
	data = jsonfile.read(path)
	entries = data.setdefault('path', {})
	for texture_file, settings in settings_by_file.items():
		key = _texture_key(root, texture_file)
		entry = entries.get(key)
		for name, value in settings.items():
			if value == TEXTURE_SETTINGS[name][1]:
				if entry is not None:
					entry.pop(name, None)
			else:
				if entry is None:
					entry = entries[key] = {'type': 'tex_v1'}
				entry[name] = value
		if entry is not None and entry == {'type': 'tex_v1'}:
			del entries[key]
	return jsonfile.write(path, data)
