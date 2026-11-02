"""Edit the starter body (New Character's blocky one) by hand, in a .blend.

	blender -b --factory-startup --python assets/starter_blend.py -- make
	(open assets/source/starter_body.blend, edit, save)
	blender -b --factory-startup --python assets/starter_blend.py -- save

`make` writes assets/source/starter_body.blend: one object per body part
(head, torso, ...), placed as on a new character, with the starter color
texture (assets/template/color.png).

`save` writes the parts' meshes back to assets/template/<part>.obj (an
object is found by its part tag, else by its name) as they look: if a part
was moved, turned or scaled away from its place, that change goes into the
mesh (and the object is put back). The texture the parts use goes to
assets/template/color.png (copied as is, or saved if painted). The color
mask and icons stay as they are. Modifiers are applied.

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
from ballistica_cloud_tools import objfile, scene, template  # noqa: E402

PART_KEY = 'bct_starter_part'  # an object's part (head, torso, ...)


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
	color = bpy.data.images.load(template.texture_path('color'))
	color.filepath = bpy.path.relpath(color.filepath, start=os.path.dirname(BLEND))
	material = bpy.data.materials.new('starter_body')
	material.use_nodes = True
	nodes = material.node_tree.nodes
	texture = nodes.new('ShaderNodeTexImage')
	texture.image = color
	texture.interpolation = 'Closest'  # blocky pixels, as in the game's starter
	texture.location = (-350, 250)
	material.node_tree.links.new(texture.outputs['Color'], nodes['Principled BSDF'].inputs['Base Color'])
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
	_save_color(used)
	bpy.ops.wm.save_mainfile()


def _is_identity(matrix, tolerance=1e-5):
	from mathutils import Matrix

	return all(abs(a - b) <= tolerance for row, ident in zip(matrix, Matrix.Identity(4)) for a, b in zip(row, ident))


def _save_color(objects):
	"""Ship the one image the parts use as assets/template/color.png."""
	images = {
		node.image for obj in objects for slot in obj.material_slots if slot.material and slot.material.node_tree
		for node in slot.material.node_tree.nodes if node.type == 'TEX_IMAGE' and node.image is not None}
	if len(images) != 1:
		print('expected one color image, found', sorted(i.name for i in images), '(color.png left as is)')
		return
	image = images.pop()
	target = template.texture_path('color')
	source = bpy.path.abspath(image.filepath)
	if image.is_dirty or not os.path.isfile(source):
		image.save(filepath=target)
	elif os.path.abspath(source) != os.path.abspath(target):
		shutil.copyfile(source, target)
	image.filepath = bpy.path.relpath(target, start=os.path.dirname(BLEND))
	print('wrote color.png', tuple(image.size))


mode = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'make'
{'make': make, 'save': save}[mode]()
