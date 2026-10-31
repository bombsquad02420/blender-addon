"""Edit the attachment templates and the starter body by hand, in a .blend.

	blender -b --factory-startup --python assets/attachment_blend.py -- make
	(open assets/source/attachment_templates.blend, edit, save)
	blender -b --factory-startup --python assets/attachment_blend.py -- save
	blender -b --factory-startup --python assets/attachment_blend.py -- body

`make` writes assets/source/attachment_templates.blend: one object per
template segment (named like its OBJ: hat, antenna_0, ...), each in a
collection named after its template, placed where it goes on the starter
body. They share one material with the template atlas
(assets/attachments/attachments_color.png).

The starter body (New Character's blocky one) is in the Starter Body
collection: one object per part (head, torso, ...), with the starter color
texture (assets/template/color.png). Edit and paint it like the
attachments. `body` puts a fresh Starter Body into an existing .blend,
leaving the attachments alone (replacing an old gray Reference Body).

`save` writes the objects' meshes back to assets/attachments/<name>.obj
and the body's to assets/template/<part>.obj (an object is found by its
name, else by its mesh's name; a body part by its part tag) as they look:
if an object was moved, turned or scaled away from its place, that change
goes into the mesh (and the object is put back). The atlas the objects use
to assets/attachments/attachments_color.png, and the body's texture to
assets/template/color.png (copied as is, or saved if painted), pointing
the .blend at them. If there's no atlas mask yet, a black one (no tints)
of the same size is written.
What you see is what's saved, so don't move objects aside just to look
at them, and don't apply or clear their transforms (Ctrl+A, Alt+G/R/S),
which takes them off their place. Modifiers are applied.
"""

import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)
BLEND = os.path.join(HERE, 'source', 'attachment_templates.blend')
spec = importlib.util.spec_from_file_location('ballistica_cloud_tools', os.path.join(ADDON, '__init__.py'), submodule_search_locations=[ADDON])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from ballistica_cloud_tools import attach_templates, objfile, scene, template  # noqa: E402

BODY = 'Starter Body'
PART_KEY = 'bct_starter_part'  # a body object's part (head, torso, ...)


def segment_names():
	"""Object name -> (template, segment index, OBJ path)."""
	names = {}
	for item in attach_templates.TEMPLATES:
		count = item.segment_count
		for index in range(count):
			path = attach_templates.obj_path(item.key, index, count)
			names[os.path.splitext(os.path.basename(path))[0]] = (item, index, path)
	return names


def _reference():
	"""A blank character (the starter body) with every template attached."""
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)  # New Character puts it there
	workspace = tempfile.mkdtemp()
	with open(os.path.join(workspace, 'workspace.json'), 'w') as outfile:
		json.dump({'path': {}, 'type': 'assets_v1'}, outfile)
	bpy.ops.ballistica.new_character(directory=workspace, name='reference', start_from='BLANK')
	character = bpy.data.collections['reference']
	bpy.context.scene.ballistica_active_character = character
	for item in attach_templates.TEMPLATES:
		bpy.ops.ballistica.attachment_add(template=item.key)
	bpy.context.view_layer.update()
	return character


def _parts(character):
	return [o for o in character.all_objects if o.type == 'MESH' and o.ballistica_part.role in scene.PART_GROUPS]


def _remove(character):
	"""Remove the reference character and what only it used."""
	for collection in [character, *character.children_recursive]:
		for obj in list(collection.objects):
			bpy.data.objects.remove(obj)
	for collection in [*character.children_recursive, character]:
		bpy.data.collections.remove(collection)
	for block in list(bpy.data.materials):
		if block.users == 0:
			bpy.data.materials.remove(block)
	bpy.ops.outliner.orphans_purge(do_recursive=True)


def _add_body(character):
	"""The Starter Body collection: the starter parts where the reference has them."""
	body = bpy.data.collections.new(BODY)
	bpy.context.scene.collection.children.link(body)
	color = bpy.data.images.load(template.texture_path('color'))
	color.filepath = bpy.path.relpath(color.filepath, start=os.path.dirname(BLEND))
	material = _material('starter_body', color)
	for obj in _parts(character):
		part = obj.ballistica_part.role
		mesh = scene.mesh_from_obj(template.obj_path(part), part)
		mesh.materials.append(material)
		copy = bpy.data.objects.new(part, mesh)
		copy[PART_KEY] = part
		copy.matrix_world = obj.matrix_world.copy()
		body.objects.link(copy)


def make():
	package.register()
	from ballistica_cloud_tools import attach_scene

	for obj in list(bpy.data.objects):
		bpy.data.objects.remove(obj)
	character = _reference()
	_add_body(character)

	settings = character.ballistica_character
	names = segment_names()
	atlas = bpy.data.images.load(attach_templates.texture_path(False))
	atlas.filepath = bpy.path.relpath(atlas.filepath, start=os.path.dirname(BLEND))
	material = _material('attachment', atlas)
	for index, (attachment, item) in enumerate(zip(settings.attachments, attach_templates.TEMPLATES)):
		group = bpy.data.collections.new(item.label)
		bpy.context.scene.collection.children.link(group)
		for obj in attach_scene.edited_meshes(character):
			if obj.get(attach_scene.INDEX_KEY) != index:
				continue
			j = obj.get(attach_scene.SEGMENT_KEY, 0)
			name = os.path.splitext(os.path.basename(attach_templates.obj_path(item.key, j, item.segment_count)))[0]
			mesh = scene.mesh_from_obj(names[name][2], name)
			copy = bpy.data.objects.new(name, mesh)
			copy.matrix_world = obj.matrix_world.copy()
			mesh.materials.append(material)
			group.objects.link(copy)

	package.unregister()
	default = bpy.data.collections.get('Collection')
	if default is not None:
		bpy.data.collections.remove(default)
	_remove(character)
	os.makedirs(os.path.dirname(BLEND), exist_ok=True)
	bpy.ops.wm.save_as_mainfile(filepath=BLEND, relative_remap=False)
	print('wrote', BLEND)


def body():
	"""Put a fresh Starter Body into the existing .blend."""
	bpy.ops.wm.open_mainfile(filepath=BLEND)
	for name in (BODY, 'Reference Body'):
		old = bpy.data.collections.get(name)
		if old is not None:
			for obj in list(old.objects):
				bpy.data.objects.remove(obj)
			bpy.data.collections.remove(old)
	package.register()
	character = _reference()
	_add_body(character)
	package.unregister()
	_remove(character)
	bpy.ops.wm.save_mainfile()
	print('added', BODY, 'to', BLEND)


def _material(key, image):
	material = bpy.data.materials.new(key)
	material.use_nodes = True
	nodes = material.node_tree.nodes
	shader = nodes.get('Principled BSDF')
	texture = nodes.new('ShaderNodeTexImage')
	texture.image = image
	texture.location = (-350, 250)
	material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
	return material


def placements():
	"""Where `make` puts things (world matrices), from a fresh reference:
	{segment object name: matrix}, {body part: matrix}."""
	package.register()
	from ballistica_cloud_tools import attach_scene

	character = _reference()
	found = {}
	for index, item in enumerate(attach_templates.TEMPLATES):
		for obj in attach_scene.edited_meshes(character):
			if obj.get(attach_scene.INDEX_KEY) == index:
				path = attach_templates.obj_path(item.key, obj.get(attach_scene.SEGMENT_KEY, 0), item.segment_count)
				found[os.path.splitext(os.path.basename(path))[0]] = obj.matrix_world.copy()
	parts = {o.ballistica_part.role: o.matrix_world.copy() for o in _parts(character)}
	package.unregister()
	return found, parts


def save():
	expected, places = placements()
	bpy.ops.wm.open_mainfile(filepath=BLEND)
	# Saved in Edit Mode, a mesh's latest edits aren't in its data yet: leave it.
	editing = [o for o in bpy.data.objects if o.mode == 'EDIT']
	if editing:
		bpy.context.view_layer.objects.active = editing[0]
		bpy.ops.object.mode_set(mode='OBJECT')
	names = segment_names()
	by_mesh = {o.data.name: o for o in bpy.data.objects if o.type == 'MESH'}
	segments = [bpy.data.objects.get(n) or by_mesh.get(n) for n in names]
	targets = [(name, obj, expected[name], path) for (name, (_, _, path)), obj in zip(names.items(), segments)]
	parts = {o[PART_KEY]: o for o in bpy.data.objects if o.type == 'MESH' and PART_KEY in o}
	if parts:
		targets += [(part, parts.get(part), places[part], template.obj_path(part)) for part in template.CUBOIDS]
	else:
		print(f'no {BODY} here (the body command adds one): the starter body is left as is')
	depsgraph = bpy.context.evaluated_depsgraph_get()
	written = []
	for name, obj, place, path in targets:
		if obj is None or obj.type != 'MESH':
			print('missing', name)
			continue
		# Away from its place: put that difference into the mesh, and the
		# object back, so the mesh looks in the game as it does here.
		delta = place.inverted() @ obj.matrix_world
		if not _is_identity(delta):
			moved, turned, scaled = delta.decompose()
			print(f'{name}: baked a move of {moved.length:.3f} and a turn of '
				f'{math.degrees(turned.angle):.1f} degrees into its mesh')
			obj.data.transform(delta)
			obj.matrix_world = place
			bpy.context.view_layer.update()  # so the evaluated mesh has the change
			depsgraph = bpy.context.evaluated_depsgraph_get()
		mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
		try:
			objfile.write(path, scene.obj_from_mesh(mesh))
		finally:
			bpy.data.meshes.remove(mesh)
		written.append(os.path.basename(path))
	print('wrote', len(written), 'meshes:', ', '.join(written))
	_save_atlas(segments)
	if parts:
		_save_image(parts.values(), template.texture_path('color'), 'starter body color')
	bpy.ops.wm.save_mainfile()


def _is_identity(matrix, tolerance=1e-5):
	from mathutils import Matrix

	return all(abs(a - b) <= tolerance for row, ident in zip(matrix, Matrix.Identity(4)) for a, b in zip(row, ident))


def _save_image(objects, target, name):
	"""Ship the one image `objects` use to `target` (copied, or saved if painted)."""
	images = {
		node.image for obj in objects if obj is not None for slot in obj.material_slots if slot.material and slot.material.node_tree
		for node in slot.material.node_tree.nodes if node.type == 'TEX_IMAGE' and node.image is not None}
	if len(images) != 1:
		print(f'expected one {name} image, found', sorted(i.name for i in images))
		return None
	image = images.pop()
	source = bpy.path.abspath(image.filepath)
	if image.is_dirty or not os.path.isfile(source):
		image.save(filepath=target)
	elif os.path.abspath(source) != os.path.abspath(target):
		shutil.copyfile(source, target)
	image.filepath = bpy.path.relpath(target, start=os.path.dirname(BLEND))
	image.name = name
	print('wrote', os.path.basename(target), tuple(image.size))
	return image


def _save_atlas(objects):
	"""Ship the atlas the template objects use, and a mask if there's none."""
	atlas = _save_image(objects, attach_templates.texture_path(False), attach_templates.ATLAS)
	if atlas is None:
		return
	mask_path = attach_templates.texture_path(True)
	if not os.path.isfile(mask_path):
		width, height = atlas.size
		mask = bpy.data.images.new(attach_templates.ATLAS_MASK, width, height, alpha=True)
		mask.colorspace_settings.name = 'Non-Color'
		mask.pixels.foreach_set([0.0, 0.0, 0.0, 1.0] * (width * height))
		mask.filepath_raw = mask_path
		mask.file_format = 'PNG'
		mask.save()
		print('wrote', os.path.basename(mask_path))


mode = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'make'
{'make': make, 'save': save, 'body': body}[mode]()
