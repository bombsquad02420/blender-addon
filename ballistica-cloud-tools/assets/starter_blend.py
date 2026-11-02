"""Edit the starter body (New Character's blocky one) by hand, in a .blend.

	blender -b --factory-startup --python assets/starter_blend.py -- make
	(open assets/source/starter_body.blend, edit, save)
	blender -b --factory-startup --python assets/starter_blend.py -- save

`make` writes assets/source/starter_body.blend: one object per body part
(head, torso, ...), placed as on a new character, with the starter color
and color mask textures (assets/template/color.png, color_mask.png) packed
in, shown through the Ballistica Colorize group like a character (the
group's Highlight inputs preview the tints). After painting a texture, save it
into the .blend (Image Editor: Image > Save, Alt+S) before saving the
.blend: a painted packed image isn't kept otherwise.

`save` writes the parts' meshes back to assets/template/<part>.obj (an
object is found by its part tag, else by its name) as they look: if a part
was moved, turned or scaled away from its place, that change goes into the
mesh (and the object is put back). The two textures go to
assets/template/color.png and color_mask.png. The icons stay as they are. Modifiers are applied.

`make template` (build_template.py) regenerates these files from
template.py, overwriting what's saved here.
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
BLEND = os.path.join(HERE, 'source', 'starter_body.blend')
spec = importlib.util.spec_from_file_location('ballistica_cloud_tools', os.path.join(ADDON, '__init__.py'), submodule_search_locations=[ADDON])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from ballistica_cloud_tools import nodegroup, objfile, scene, template  # noqa: E402

PART_KEY = 'bct_starter_part'  # an object's part (head, torso, ...)
# Texture node name -> the template texture it holds.
TEXTURES = {'bct_color': 'color', 'bct_color_mask': 'color_mask'}


def placements():
	"""Part -> where it sits on a new character (world matrix)."""
	package.register()
	bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)  # New Character puts it there
	workspace = tempfile.mkdtemp()
	with open(os.path.join(workspace, 'workspace.json'), 'w') as outfile:
		json.dump({'path': {}, 'type': 'assets_v1'}, outfile)
	bpy.ops.ballistica.new_character(directory=workspace, name='reference', start_from='BLANK')
	character = bpy.data.collections['reference']
	bpy.context.view_layer.update()
	found = {
		o.ballistica_part.role: o.matrix_world.copy() for o in character.all_objects
		if o.type == 'MESH' and o.ballistica_part.role in scene.PART_GROUPS}
	package.unregister()
	return found


def make():
	places = placements()
	bpy.ops.wm.read_factory_settings(use_empty=True)
	material = _material()
	for part in template.CUBOIDS:
		mesh = scene.mesh_from_obj(template.obj_path(part), part)
		mesh.materials.append(material)
		obj = bpy.data.objects.new(part, mesh)
		obj[PART_KEY] = part
		obj.matrix_world = places[part]
		bpy.context.scene.collection.objects.link(obj)
	os.makedirs(os.path.dirname(BLEND), exist_ok=True)
	bpy.ops.wm.save_as_mainfile(filepath=BLEND, relative_remap=False)
	print('wrote', BLEND)


def _material():
	"""The body material: both textures, packed, through the Colorize group."""
	material = bpy.data.materials.new('starter_body')
	nodes, links = material.node_tree.nodes, material.node_tree.links
	nodes.clear()
	out = nodes.new('ShaderNodeOutputMaterial')
	out.location = (300, 0)
	group = nodes.new('ShaderNodeGroup')
	group.node_tree = nodegroup.get()
	group.width = 200
	links.new(group.outputs['Color'], out.inputs['Surface'])
	for index, (node_name, texture) in enumerate(TEXTURES.items()):
		image = bpy.data.images.load(template.texture_path(texture))
		image.name = texture
		if texture == 'color_mask':
			image.colorspace_settings.name = 'Non-Color'
		image.pack()
		node = nodes.new('ShaderNodeTexImage')
		node.name = node_name
		node.image = image
		node.interpolation = 'Closest'  # blocky pixels
		node.location = (-350, 150 - 300 * index)
		links.new(node.outputs['Color'], group.inputs['Color Mask' if texture == 'color_mask' else 'Color'])
	return material


def save():
	places = placements()
	bpy.ops.wm.open_mainfile(filepath=BLEND)
	# Saved in Edit Mode, a mesh's latest edits aren't in its data yet: leave it.
	editing = [o for o in bpy.data.objects if o.mode == 'EDIT']
	if editing:
		bpy.context.view_layer.objects.active = editing[0]
		bpy.ops.object.mode_set(mode='OBJECT')
	tagged = {o[PART_KEY]: o for o in bpy.data.objects if o.type == 'MESH' and PART_KEY in o}
	depsgraph = bpy.context.evaluated_depsgraph_get()
	written, used = [], []
	for part in template.CUBOIDS:
		obj = tagged.get(part) or bpy.data.objects.get(part)
		if obj is None or obj.type != 'MESH':
			print('missing', part)
			continue
		used.append(obj)
		# Away from its place: put that difference into the mesh, and the
		# object back, so the mesh looks in the game as it does here.
		delta = places[part].inverted() @ obj.matrix_world
		if not _is_identity(delta):
			moved, turned, scaled = delta.decompose()
			print(f'{part}: baked a move of {moved.length:.3f} and a turn of '
				f'{math.degrees(turned.angle):.1f} degrees into its mesh')
			obj.data.transform(delta)
			obj.matrix_world = places[part]
			bpy.context.view_layer.update()  # so the evaluated mesh has the change
			depsgraph = bpy.context.evaluated_depsgraph_get()
		mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
		try:
			objfile.write(template.obj_path(part), scene.obj_from_mesh(mesh))
		finally:
			bpy.data.meshes.remove(mesh)
		written.append(f'{part}.obj')
	print('wrote', len(written), 'meshes:', ', '.join(written))
	_save_textures(used)
	bpy.ops.wm.save_mainfile()


def _is_identity(matrix, tolerance=1e-5):
	from mathutils import Matrix

	return all(abs(a - b) <= tolerance for row, ident in zip(matrix, Matrix.Identity(4)) for a, b in zip(row, ident))


def _save_textures(objects):
	"""Write the parts' color and color mask textures to assets/template/."""
	nodes = {
		node.name: node for obj in objects for slot in obj.material_slots if slot.material and slot.material.node_tree
		for node in slot.material.node_tree.nodes if node.type == 'TEX_IMAGE' and node.image is not None}
	for node_name, texture in TEXTURES.items():
		node = nodes.get(node_name)
		if node is None:
			print(f'no {node_name} texture node: {texture}.png left as is')
			continue
		image = node.image
		target = template.texture_path(texture)
		# A copy, so the image in the .blend stays packed.
		copy = image.copy()
		try:
			copy.filepath_raw = target
			copy.file_format = 'PNG'
			copy.save()
		finally:
			bpy.data.images.remove(copy)
		print(f'wrote {texture}.png', tuple(image.size))


mode = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'make'
{'make': make, 'save': save}[mode]()
