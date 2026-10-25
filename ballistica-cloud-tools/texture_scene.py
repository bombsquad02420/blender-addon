"""Body textures: the Textures list and the material that follows it.

Two fixed rows, the character's color texture and color mask, each
holding a Blender image. Picking an image shows it on the body material
(made if the character has none); clearing one unlinks it, so the
Colorize group's defaults show (plain white, untinted) instead of a broken
texture. The .bchar's texture fields are written from the rows on export.
"""

import bpy

from . import scene, workspace

ROWS = ('color_texture', 'color_mask_texture')
LABELS = {'color_texture': "Color", 'color_mask_texture': "Color Mask"}
SUFFIXES = {'color_texture': 'color', 'color_mask_texture': 'color_mask', 'icon_texture': 'icon', 'icon_mask_texture': 'icon_color_mask'}
# Icon field -> the settings picker holding its image.
ICON_BLOCKS = {'icon_texture': 'icon_block', 'icon_mask_texture': 'icon_mask_block'}
MASKS = ('color_mask_texture', 'icon_mask_texture')
# Row -> the Colorize group input its image feeds, and its texture node's name.
SOCKETS = {'color_texture': 'Color', 'color_mask_texture': 'Color Mask'}
NODE_NAMES = {'color_texture': 'bct_color', 'color_mask_texture': 'bct_color_mask'}
NEW_SIZE = 512

_quiet = False


def is_mask(row):
	return row.field == 'color_mask_texture'


def has_rows(settings):
	return [r.field for r in settings.textures] == list(ROWS)


def row(settings, field):
	return next((r for r in settings.textures if r.field == field), None)


def fill_rows(collection):
	"""Rows from the body material's images (or the texture fields)."""
	global _quiet
	from .repair import body_material

	settings = collection.ballistica_character
	material = body_material(collection)
	_quiet = True
	try:
		if not has_rows(settings):
			settings.textures.clear()
			for field in ROWS:
				settings.textures.add().field = field
		for item in settings.textures:
			node = _texture_node(material, item.field) if material is not None else None
			image = node.image if node is not None else None
			if image is None and getattr(settings, item.field):
				image = scene._image(settings.workspace_root, getattr(settings, item.field), data=is_mask(item))
			item.image = image
	finally:
		_quiet = False
	for item in settings.textures:
		show(collection, item.field, item.image)  # unlink missing ones


def _group_node(material):
	return next((n for n in material.node_tree.nodes if n.type == 'GROUP' and 'Color Mask' in n.inputs), None) if material.node_tree else None


def _texture_node(material, field):
	"""The image node feeding `field`'s socket (named by scene.build_material)."""
	return material.node_tree.nodes.get(NODE_NAMES[field]) if material.node_tree else None


def show(collection, field, image):
	"""Show `image` (or nothing) as the body material's `field` texture."""
	from .repair import body_material

	material = body_material(collection)
	if material is None:
		material = _make_material(collection)
	set_image(material, field, image)


def set_image(material, field, image):
	"""Show `image` (or nothing: the Colorize defaults) as a material's `field` texture."""
	group = _group_node(material)
	node = _texture_node(material, field)
	if group is None or node is None:
		return
	node.image = image
	socket = group.inputs[SOCKETS[field]]
	links = material.node_tree.links
	if image is None:
		for link in list(socket.links):
			links.remove(link)
	elif not socket.links:
		links.new(node.outputs['Color'], socket)


def _make_material(collection):
	"""A body material for a character that has none; given to its parts."""
	settings = collection.ballistica_character
	material = scene.build_material(collection.name, settings.workspace_root, '', '', collection)
	settings.body_material = material
	for obj in collection.all_objects:
		if obj.type == 'MESH' and obj.ballistica_part.role in scene.PART_GROUPS:
			scene.assign_material(obj, material)
	for item in settings.textures:
		show(collection, item.field, item.image)
	return material


def on_row_changed(item):
	"""props hook: a Textures row's image changed."""
	if _quiet:
		return
	collection = item.id_data
	if not isinstance(collection, bpy.types.Collection) or not collection.ballistica_character.is_character:
		return
	image = item.image
	if image is not None and is_mask(item) and image.ballistica_texture.role not in workspace.DATA_ROLES:
		image.ballistica_texture.role = 'data'  # shows it as Non-Color too
	show(collection, item.field, image)


def new_image(collection, field):
	"""A blank image for a row: white color, or a black (untinted) mask."""
	name = f'{collection.name.split(".")[0]}_{SUFFIXES[field]}'
	mask = field in MASKS
	image = bpy.data.images.new(name, NEW_SIZE, NEW_SIZE, alpha=True)
	if mask:
		image.colorspace_settings.name = 'Non-Color'  # before painting: it regenerates the image
		image.ballistica_texture['role'] = workspace.TEXTURE_SETTINGS['texture_role'][0].index('data')
	image.generated_color = (0.0, 0.0, 0.0, 1.0) if mask else (1.0, 1.0, 1.0, 1.0)
	image.file_format = 'PNG'
	from .repair import rename

	rename(image)  # a clash got Blender's ".001": make it a file name
	return image


# ---- export paths and fields ----

def default_path(collection, field):
	return f'textures/{collection.name.split(".")[0]}_{SUFFIXES[field]}'


def fields(collection):
	"""{texture field: logical path} as export will write them."""
	settings = collection.ballistica_character
	out = {}
	for item in settings.textures:
		if item.image is None:
			out[item.field] = ''
		else:
			out[item.field] = item.image.ballistica_texture.path or _free_path(collection, item)
	return out


def _free_path(collection, item):
	base = default_path(collection, item.field)
	taken = {i.ballistica_texture.path for i in bpy.data.images if i != item.image}
	path, n = base, 2
	while path in taken:
		path, n = f'{base}_{n}', n + 1
	return path


def assign_paths(collection):
	settings = collection.ballistica_character
	for item in settings.textures:
		if item.image is not None and not item.image.ballistica_texture.path:
			item.image.ballistica_texture.path = _free_path(collection, item)
	for name, value in fields(collection).items():
		setattr(settings, name, value)


# ---- the icon and icon mask (Identity) ----

class _Slot:
	"""An icon field and its image, shaped like a Textures row for _free_path."""

	def __init__(self, field, image):
		self.field, self.image = field, image


def mirror_icons(collection):
	"""Write the icon pickers' export paths into the icon fields.

	An image without an export path gets the default one. An empty picker
	keeps the field as loaded (a file that wasn't found stays referenced).
	"""
	settings = collection.ballistica_character
	for field, attr in ICON_BLOCKS.items():
		image = getattr(settings, attr)
		if image is None:
			continue
		if not image.ballistica_texture.path:
			image.ballistica_texture.path = _free_path(collection, _Slot(field, image))
		if field in MASKS and image.ballistica_texture.role not in workspace.DATA_ROLES:
			image.ballistica_texture.role = 'data'
		setattr(settings, field, image.ballistica_texture.path)


def fill_icons(collection):
	"""The icon pickers from the icon fields (after building a character)."""
	settings = collection.ballistica_character
	settings['_loading'] = True
	try:
		for field, attr in ICON_BLOCKS.items():
			if getattr(settings, attr) is None and getattr(settings, field):
				setattr(settings, attr, scene._image(settings.workspace_root, getattr(settings, field), data=field in MASKS))
	finally:
		del settings['_loading']


def on_icon_changed(settings, field):
	"""props hook: an icon picker changed."""
	collection = settings.id_data
	if not isinstance(collection, bpy.types.Collection) or not settings.is_character:
		return
	if getattr(settings, ICON_BLOCKS[field]) is None:
		setattr(settings, field, '')  # cleared
	else:
		mirror_icons(collection)


# ---- every image the character exports (the Textures panel) ----

def exported_images(collection):
	"""[(image, label)] the character's .bchar points at, in panel order.

	Body textures, icons, then each attachment segment's own images. An
	image used in several places is listed once, its uses joined.
	"""
	settings = collection.ballistica_character
	uses = {}
	for item in settings.textures:
		if item.image is not None:
			uses.setdefault(item.image, []).append(f"Body {LABELS[item.field]}")
	for field, attr in ICON_BLOCKS.items():
		image = getattr(settings, attr)
		if image is not None:
			uses.setdefault(image, []).append("Icon Mask" if field in MASKS else "Icon")
	for index, attachment in enumerate(settings.attachments):
		name = f"{attachment.target.replace('_', ' ').title()} attachment {index + 1}"
		for segment in attachment.segments:
			for image, what in ((segment.texture_block, "Texture"), (segment.mask_block, "Mask")):
				if image is not None:
					uses.setdefault(image, []).append(f"{name} {what}")
	return [(image, ", ".join(dict.fromkeys(labels))) for image, labels in uses.items()]


def is_mask_image(collection, image):
	"""Whether an image is used as a color mask (its channels are tints)."""
	settings = collection.ballistica_character
	masks = [r.image for r in settings.textures if r.field == 'color_mask_texture'] + [settings.icon_mask_block]
	masks += [s.mask_block for a in settings.attachments for s in a.segments]
	return image in masks


def paint_target(collection, image):
	"""What to paint `image` on: an attachment's mesh object, 'BODY', or None (icons)."""
	from . import attach_scene

	settings = collection.ballistica_character
	for index, attachment in enumerate(settings.attachments):
		for j, segment in enumerate(attachment.segments):
			if image in (segment.texture_block, segment.mask_block):
				return next((o for o in attach_scene.edited_meshes(collection)
					if o.get(attach_scene.INDEX_KEY) == index and o.get(attach_scene.SEGMENT_KEY) == j), None)
	if any(r.image == image for r in settings.textures):
		return 'BODY'
	return None


from . import props as _props  # noqa: E402

_props.ATTACHMENT_REBUILD_HOOKS['texture'] = on_row_changed
_props.ATTACHMENT_REBUILD_HOOKS['icon'] = on_icon_changed
