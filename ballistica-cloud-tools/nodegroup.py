"""The "Ballistica Colorize" shader node group, bundled as an asset.

Reproduces the engine's colorize shader (base/graphics/gl/program/
program_object_gl.h):

	color = tex * mix(1, highlight1, mask.r)
	            * mix(1, highlight2, mask.g)
	            * mix(1, highlight3, mask.b)

In `.bchar` terms Highlight 1 is `color`, Highlight 2 is `highlight` and
Highlight 3 is `highlight2`.

The group ships in assets/ballistica_assets.blend (built by
assets/build_assets.py) and is appended from there; `create()` is what that
build script runs, never the addon at runtime.
"""

import os

import bpy

GROUP_NAME = "Ballistica Colorize"
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


def create():
	"""Build the node group in the current file and return it."""
	group = bpy.data.node_groups.new(GROUP_NAME, 'ShaderNodeTree')
	group.description = "BombSquad character colorize, as the game draws it"
	iface = group.interface
	sockets = {}
	for name, description in INPUTS:
		socket = iface.new_socket(name=name, in_out='INPUT', socket_type='NodeSocketColor')
		socket.default_value = DEFAULTS[name]
		socket.description = description
		sockets[name] = socket
	iface.new_socket(name='BSDF', in_out='OUTPUT', socket_type='NodeSocketShader')
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

	bsdf = nodes.new('ShaderNodeBsdfPrincipled')
	bsdf.location = (250, 150)
	bsdf.inputs['Roughness'].default_value = 0.6
	links.new(color, bsdf.inputs['Base Color'])
	links.new(bsdf.outputs['BSDF'], group_out.inputs['BSDF'])
	links.new(color, group_out.inputs['Color'])
	return group


class MissingAssetError(RuntimeError):
	"""The bundled asset file is missing or doesn't contain the node group."""


def get():
	"""The node group, appended from the bundled .blend if needed.

	Raises MissingAssetError rather than building a substitute: a missing
	or unreadable assets file is a broken build (run `make cloud-assets`).
	"""
	group = bpy.data.node_groups.get(GROUP_NAME)
	if group is not None and group.library is None:
		return group
	if not os.path.isfile(ASSETS_BLEND):
		raise MissingAssetError(f"Bundled asset file not found: {ASSETS_BLEND}. Rebuild the addon (make cloud-build).")
	with bpy.data.libraries.load(ASSETS_BLEND, link=False, assets_only=True) as (src, dst):
		if GROUP_NAME not in src.node_groups:
			raise MissingAssetError(f'"{GROUP_NAME}" not found in {ASSETS_BLEND}. Rebuild the addon (make cloud-build).')
		dst.node_groups = [GROUP_NAME]
	return bpy.data.node_groups[GROUP_NAME]


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
