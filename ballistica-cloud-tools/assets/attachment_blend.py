"""Edit the attachment templates by hand, in a .blend.

	blender -b --factory-startup --python assets/attachment_blend.py -- make
	(open assets/source/attachment_templates.blend, edit, save)
	blender -b --factory-startup --python assets/attachment_blend.py -- save

`make` writes assets/source/attachment_templates.blend: one object per
template segment (named like its OBJ: hat, antenna_0, ...), each in a
collection named after its template, placed where it goes on a reference
starter body (unselectable). Each uses its template's color PNG straight
from assets/attachments/, so painting it and saving the image (Image >
Save) updates the shipped file.

`save` writes the objects' meshes back to assets/attachments/<name>.obj.
Only the mesh data counts, in the object's own space: move, turn or scale
the objects freely to look at them, but edit the shape in Edit Mode, and
don't apply transforms (Ctrl+A), which would bake the placement in.
Modifiers are applied.
"""

import importlib.util
import json
import os
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
from ballistica_cloud_tools import attach_templates, objfile, scene  # noqa: E402


def segment_names():
	"""Object name -> (template, segment index, OBJ path)."""
	names = {}
	for item in attach_templates.TEMPLATES:
		count = len(item.segments)
		for index in range(count):
			path = attach_templates.obj_path(item.key, index, count)
			names[os.path.splitext(os.path.basename(path))[0]] = (item, index, path)
	return names


def make():
	package.register()
	from ballistica_cloud_tools import attach_scene

	for obj in list(bpy.data.objects):
		bpy.data.objects.remove(obj)
	workspace = tempfile.mkdtemp()
	with open(os.path.join(workspace, 'workspace.json'), 'w') as outfile:
		json.dump({'path': {}, 'type': 'assets_v1'}, outfile)
	bpy.ops.ballistica.new_character(directory=workspace, name='reference', start_from='BLANK')
	character = bpy.data.collections['reference']
	bpy.context.scene.ballistica_active_character = character
	for item in attach_templates.TEMPLATES:
		bpy.ops.ballistica.attachment_add(template=item.key)
	bpy.context.view_layer.update()

	reference = bpy.data.collections.new('Reference Body')
	bpy.context.scene.collection.children.link(reference)
	gray = bpy.data.materials.new('reference_body')
	gray.diffuse_color = (0.6, 0.6, 0.6, 1.0)
	for obj in [o for o in character.all_objects if o.type == 'MESH' and o.ballistica_part.role in scene.PART_GROUPS]:
		body_mesh = obj.data.copy()
		body_mesh.materials.clear()
		body_mesh.materials.append(gray)
		copy = bpy.data.objects.new(f'reference {obj.name}', body_mesh)
		copy.matrix_world = obj.matrix_world.copy()
		copy.hide_select = True
		copy.display_type = 'SOLID'
		reference.objects.link(copy)

	settings = character.ballistica_character
	names = segment_names()
	for index, (attachment, item) in enumerate(zip(settings.attachments, attach_templates.TEMPLATES)):
		group = bpy.data.collections.new(item.label)
		bpy.context.scene.collection.children.link(group)
		image = bpy.data.images.load(attach_templates.texture_path(item.key, False))
		image.filepath = bpy.path.relpath(image.filepath, start=os.path.dirname(BLEND))
		material = _material(item.key, image)
		for obj in attach_scene.edited_meshes(character):
			if obj.get(attach_scene.INDEX_KEY) != index:
				continue
			j = obj.get(attach_scene.SEGMENT_KEY, 0)
			name = os.path.splitext(os.path.basename(attach_templates.obj_path(item.key, j, len(item.segments))))[0]
			mesh = scene.mesh_from_obj(names[name][2], name)
			copy = bpy.data.objects.new(name, mesh)
			copy.matrix_world = obj.matrix_world.copy()
			mesh.materials.append(material)
			group.objects.link(copy)

	package.unregister()
	default = bpy.data.collections.get('Collection')
	if default is not None:
		bpy.data.collections.remove(default)
	for collection in [character, *character.children_recursive]:
		for obj in list(collection.objects):
			bpy.data.objects.remove(obj)
	for collection in [*character.children_recursive, character]:
		bpy.data.collections.remove(collection)
	for block in list(bpy.data.materials):
		if block.users == 0:
			bpy.data.materials.remove(block)
	bpy.ops.outliner.orphans_purge(do_recursive=True)
	os.makedirs(os.path.dirname(BLEND), exist_ok=True)
	bpy.ops.wm.save_as_mainfile(filepath=BLEND, relative_remap=False)
	print('wrote', BLEND)


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


def save():
	bpy.ops.wm.open_mainfile(filepath=BLEND)
	names = segment_names()
	depsgraph = bpy.context.evaluated_depsgraph_get()
	written = []
	for name, (_, _, path) in names.items():
		obj = bpy.data.objects.get(name)
		if obj is None or obj.type != 'MESH':
			print('missing', name)
			continue
		mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
		try:
			objfile.write(path, scene.obj_from_mesh(mesh))
		finally:
			bpy.data.meshes.remove(mesh)
		written.append(os.path.basename(path))
	print('wrote', len(written), 'meshes:', ', '.join(written))


mode = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'make'
{'make': make, 'save': save}[mode]()
