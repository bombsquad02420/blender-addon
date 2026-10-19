"""Bundled assets: the "Ballistica Colorize" and "Ballistica Eye" shader
groups, and the game's eye meshes and textures.

Colorize:

Reproduces the engine's colorize shader (base/graphics/gl/program/
program_object_gl.h):

	color = tex * mix(1, highlight1, mask.r)
	            * mix(1, highlight2, mask.g)
	            * mix(1, highlight3, mask.b)

In `.bchar` terms Highlight 1 is `color`, Highlight 2 is `highlight` and
Highlight 3 is `highlight2`.

Eye (DrawEyeBalls / SetupEyeLidShading in spaz_node.cc):

	color = tex * mix(1, iris, mask) * base

with the eyeColor texture and tint mask; the eyeball uses iris = eye_color
and base = eyeball_color, the eyelid no mask and base = eyelid_color.

Everything ships in assets/ballistica_assets.blend (built by
assets/build_assets.py) and is appended from there; the create functions
are what that build script runs, never the addon at runtime.
"""

import os

import bpy

GROUP_NAME = "Ballistica Colorize"
EYE_GROUP_NAME = "Ballistica Eye"
# Data the build bakes into the asset file (see build_assets.py).
EYE_MESHES = ('eye_ball', 'eye_lid')
EYE_IMAGES = ('eye_color', 'eye_color_tint_mask')
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
ASSETS_BLEND = os.path.join(ASSETS_DIR, 'ballistica_assets.blend')
LIBRARY_NAME = "Ballistica Cloud Tools"

INPUTS = (
	('Color', "The color texture"),
	('Color Mask', "The color mask texture (non-color data)"),
	('Highlight 1', "Tints the mask's red channel (.bchar color)"),
	('Highlight 2', "Tints the mask's green channel (.bchar highlight)"),
	('Highlight 3', "Tints the mask's blue channel (.bchar highlight2)"),
)
DEFAULTS = {
	'Color': (1.0, 1.0, 1.0, 1.0),
	'Color Mask': (0.0, 0.0, 0.0, 1.0),
	'Highlight 1': (0.5, 0.5, 0.5, 1.0),
	'Highlight 2': (0.5, 0.5, 0.5, 1.0),
	'Highlight 3': (1.0, 1.0, 1.0, 1.0),
}


EYE_INPUTS = (
	('Color', "The eye color texture"),
	('Tint Mask', "Where Iris Color applies (non-color data)"),
	('Iris Color', "Tints the masked area (.bchar eye_color)"),
	('Base Color', "Multiplies everything (.bchar eyeball_color or eyelid_color)"),
)


def create_eye():
	"""Build the eye node group in the current file and return it."""
	group = bpy.data.node_groups.new(EYE_GROUP_NAME, 'ShaderNodeTree')
	group.description = "BombSquad eyeball / eyelid shading, as the game draws it"
	iface = group.interface
	for name, description in EYE_INPUTS:
		socket = iface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocketColor')
		socket.default_value = (0.0, 0.0, 0.0, 1.0) if name == 'Tint Mask' else (1.0, 1.0, 1.0, 1.0)
		socket.description = description
	iface.new_socket(name='Color', in_out='OUTPUT', socket_type='NodeSocketColor')
	nodes, links = group.nodes, group.links
	group_in = nodes.new('NodeGroupInput')
	group_in.location = (-600, 0)
	group_out = nodes.new('NodeGroupOutput')
	group_out.location = (300, 0)
	split = nodes.new('ShaderNodeSeparateColor')
	split.location = (-400, -200)
	links.new(group_in.outputs['Tint Mask'], split.inputs['Color'])
	tint = nodes.new('ShaderNodeMix')
	tint.data_type, tint.blend_type, tint.location = 'RGBA', 'MULTIPLY', (-150, 50)
	links.new(split.outputs['Red'], _socket(tint.inputs, 'Factor_Float'))
	links.new(group_in.outputs['Color'], _socket(tint.inputs, 'A_Color'))
	links.new(group_in.outputs['Iris Color'], _socket(tint.inputs, 'B_Color'))
	base = nodes.new('ShaderNodeMix')
	base.data_type, base.blend_type, base.location = 'RGBA', 'MULTIPLY', (80, 50)
	_socket(base.inputs, 'Factor_Float').default_value = 1.0
	links.new(_socket(tint.outputs, 'Result_Color'), _socket(base.inputs, 'A_Color'))
	links.new(group_in.outputs['Base Color'], _socket(base.inputs, 'B_Color'))
	links.new(_socket(base.outputs, 'Result_Color'), group_out.inputs['Color'])
	return group


def create():
	"""Build the colorize node group in the current file and return it."""
	group = bpy.data.node_groups.new(GROUP_NAME, 'ShaderNodeTree')
	group.description = "BombSquad character colorize, as the game draws it"
	iface = group.interface
	sockets = {}
	for name, description in INPUTS:
		socket = iface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocketColor')
		socket.default_value = DEFAULTS[name]
		socket.description = description
		sockets[name] = socket
	iface.new_socket(name='Color', in_out='OUTPUT', socket_type='NodeSocketColor')

	nodes, links = group.nodes, group.links
	group_in = nodes.new('NodeGroupInput')
	group_in.location = (-800, 0)
	group_out = nodes.new('NodeGroupOutput')
	group_out.location = (500, 0)
	split = nodes.new('ShaderNodeSeparateColor')
	split.location = (-550, -250)
	links.new(group_in.outputs['Color Mask'], split.inputs['Color'])

	color = group_in.outputs['Color']
	for i, (channel, highlight) in enumerate((('Red', 'Highlight 1'), ('Green', 'Highlight 2'), ('Blue', 'Highlight 3'))):
		mix = nodes.new('ShaderNodeMix')
		mix.data_type = 'RGBA'
		mix.blend_type = 'MULTIPLY'
		mix.location = (-300 + 200 * i, 100)
		links.new(split.outputs[channel], _socket(mix.inputs, 'Factor_Float'))
		links.new(color, _socket(mix.inputs, 'A_Color'))
		links.new(group_in.outputs[highlight], _socket(mix.inputs, 'B_Color'))
		color = _socket(mix.outputs, 'Result_Color')

	links.new(color, group_out.inputs['Color'])
	return group


class MissingAssetError(RuntimeError):
	"""The bundled asset file is missing or doesn't contain the node group."""


def get(name=GROUP_NAME):
	"""A bundled node group, appended from the asset .blend if needed.

	Raises MissingAssetError rather than building a substitute: a missing
	or unreadable assets file is a broken build (run `make build` in ballistica-cloud-tools).
	"""
	group = bpy.data.node_groups.get(name)
	if group is not None and group.library is None:
		return group
	_append('node_groups', [name])
	return bpy.data.node_groups[name]


def get_data(kind, names):
	"""Bundled meshes or images (`kind` 'meshes' / 'images'), appended once."""
	collection = getattr(bpy.data, kind)
	missing = [n for n in names if collection.get(n) is None or collection[n].library is not None]
	if missing:
		_append(kind, missing)
	return [collection[n] for n in names]


def _append(kind, names):
	if not os.path.isfile(ASSETS_BLEND):
		raise MissingAssetError(f"Bundled asset file not found: {ASSETS_BLEND}. Rebuild the addon (make build in ballistica-cloud-tools).")
	with bpy.data.libraries.load(ASSETS_BLEND, link=False) as (src, dst):
		absent = [n for n in names if n not in getattr(src, kind)]
		if absent:
			raise MissingAssetError(f"{', '.join(absent)} not found in {ASSETS_BLEND}. Rebuild the addon (make build in ballistica-cloud-tools).")
		setattr(dst, kind, list(names))


def _socket(sockets, identifier):
	for socket in sockets:
		if socket.identifier == identifier:
			return socket
	raise KeyError(identifier)


def register_library():
	"""Add the addon's assets folder as an asset library (if not there)."""
	libraries = bpy.context.preferences.filepaths.asset_libraries
	path = os.path.normpath(ASSETS_DIR)
	for library in libraries:
		if os.path.normpath(bpy.path.abspath(library.path)) == path:
			return
	library = libraries.new(name=LIBRARY_NAME, directory=path)
	library.import_method = 'APPEND'


def unregister_library():
	libraries = bpy.context.preferences.filepaths.asset_libraries
	path = os.path.normpath(ASSETS_DIR)
	for library in list(libraries):
		if os.path.normpath(bpy.path.abspath(library.path)) == path:
			libraries.remove(library)
