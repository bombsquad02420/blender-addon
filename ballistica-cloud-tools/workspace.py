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


def mark_data_textures(root, texture_files):
	"""Mark textures as non-color data (masks) in workspace.json.

	Only adds `texture_role: data` to entries that lack a role; every other
	key is left as it is. Returns True if workspace.json changed.
	"""
	path = os.path.join(root, WORKSPACE_FILE)
	data = jsonfile.read(path)
	entries = data.setdefault('path', {})
	changed = False
	for texture in texture_files:
		key = os.path.relpath(texture, root).replace(os.sep, '/')
		entry = entries.setdefault(key, {'type': 'tex_v1'})
		if 'texture_role' not in entry:
			entry['texture_role'] = 'data'
			changed = True
	if changed:
		jsonfile.write(path, data)
	return changed


def texture_role(root, texture_file):
	"""The texture's `texture_role` from workspace.json, or None."""
	path = os.path.join(root, WORKSPACE_FILE)
	key = os.path.relpath(texture_file, root).replace(os.sep, '/')
	return jsonfile.read(path).get('path', {}).get(key, {}).get('texture_role')
