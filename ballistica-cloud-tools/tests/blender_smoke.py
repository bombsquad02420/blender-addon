"""End-to-end check inside Blender (not run by unittest discovery).

	blender -b --factory-startup --python tests/blender_smoke.py -- <ClassicCharacterAssets>

Copies the workspace to a temp folder, imports characters, and checks that
exporting an untouched character writes nothing and that an edit writes
only the edited mesh.
"""

import hashlib
import importlib.util
import os
import shutil
import sys
import tempfile

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = sys.argv[sys.argv.index('--') + 1]

spec = importlib.util.spec_from_file_location('ballistica_cloud_tools', os.path.join(ADDON, '__init__.py'), submodule_search_locations=[ADDON])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
package.register()

import bpy  # noqa: E402
from ballistica_cloud_tools import objfile, operators, rig  # noqa: E402


def make_active(obj):
	"""Make `obj` active, as a click would in the UI.

	The UI's message bus notifies the addon when the active object changes;
	background mode has no UI, so call that handler directly.
	"""
	from ballistica_cloud_tools import attach_scene

	bpy.context.view_layer.objects.active = obj
	attach_scene.on_active_object_changed()

ws = os.path.join(tempfile.mkdtemp(), 'ws')
shutil.copytree(SAMPLE, ws, ignore=shutil.ignore_patterns('.git'))

# The checks below are written against classic Zoe's three hair
# attachments; the sample may have been edited since (in place, by
# exporting), so reset them in this temporary copy.
CLASSIC_ZOE_ATTACHMENTS = [
	{'damping': 0.7, 'kind': 'antenna', 'radius': 0.375,
		'segments': [{'mesh': 'meshes/hair_tuft1', 'transform': {'translate': [0.02, 0.16, 0.05]}}],
		'stiffness': 0.2, 'target': 'head',
		'transform': {'rotate': [48.427, 28.318, 12.945], 'translate': [-0.173, 0.124, 0.153]}},
	{'damping': 0.7, 'kind': 'antenna',
		'segments': [{'mesh': 'meshes/hair_tuft2', 'transform': {'rotate': [0.0, -24.995, 0.0], 'translate': [-0.01, 0.03, 0.06]}}],
		'stiffness': 0.3, 'target': 'head',
		'transform': {'rotate': [-59.035, 23.207, -13.262], 'translate': [0.196, 0.098, 0.118]}},
	{'damping': 0.8, 'kind': 'antenna_2', 'length': 0.8, 'radius': 0.625,
		'segments': [
			{'mesh': 'meshes/hair_tuft3', 'transform': {'rotate': [-180.0, 0.0, 0.0]}},
			{'mesh': 'meshes/hair_tuft4', 'transform': {'rotate': [-180.0, 0.0, 0.0], 'translate': [0.0, 0.0, 0.04]}}],
		'stiffness': 0.67, 'stiffness_change': -0.26, 'target': 'head',
		'transform': {'rotate': [-180.0, 63.025, 0.0], 'translate': [0.0, 0.28, -0.224]}},
]


def _reset_zoe():
	import json

	path = os.path.join(ws, 'characters', 'zoe.bchar')
	with open(path) as infile:
		raw = json.load(infile)
	raw['data']['attachments'] = CLASSIC_ZOE_ATTACHMENTS
	with open(path, 'w') as outfile:
		outfile.write(json.dumps(raw, indent=2, sort_keys=True) + '\n')


_reset_zoe()


def snapshot():
	out = {}
	for base, _, files in os.walk(ws):
		for name in files:
			path = os.path.join(base, name)
			with open(path, 'rb') as infile:
				out[os.path.relpath(path, ws)] = hashlib.sha1(infile.read()).hexdigest()
	return out


def expected_attachment_meshes(name):
	"""Attachment mesh objects a character should get: one per segment, two
	for a `both` attachment on a limb or wing. From the file, so the test
	follows the sample workspace if it was edited."""
	import json
	from ballistica_cloud_tools import attachments as rules

	with open(os.path.join(ws, 'characters', f'{name}.bchar')) as infile:
		data = json.load(infile)['data']
	total = 0
	for a in data.get('attachments', []):
		sides = 2 if a.get('target') in rules.LIMB_TARGETS and a.get('side', 'both') == 'both' else 1
		total += sides * len(a.get('segments', []))
	return total


before = snapshot()
for name in ('agent_johnson', 'zoe', 'pixel'):
	attachments = expected_attachment_meshes(name)
	assert bpy.ops.ballistica.import_character(filepath=os.path.join(ws, 'characters', f'{name}.bchar')) == {'FINISHED'}
	collection = bpy.data.collections[name]
	found = [o for o in collection.all_objects if o.ballistica_part.role == 'attachment']
	assert all(o.users_collection[0].name == f'{name} Attachments' for o in found)
	assert len(found) == attachments, (name, [o.name for o in found])
	assert operators.check(collection) == [], operators.check(collection)

# Meshes and images carry their export path; images their texture settings.
agent_head = next(o for o in bpy.data.collections['agent_johnson'].all_objects if o.ballistica_part.role == 'head')
assert agent_head.data.ballistica_asset.path == 'meshes/agent_head'
assert agent_head.data.ballistica_asset.export_uv == agent_head.data.uv_layers[0].name
mask_image = next(i for i in bpy.data.images if i.ballistica_texture.path == 'textures/agent_color_mask')
assert mask_image.ballistica_texture.role == 'data' and mask_image.colorspace_settings.name == 'Non-Color'
color_image = next(i for i in bpy.data.images if i.ballistica_texture.path == 'textures/agent_color')
assert color_image.ballistica_texture.role == 'default' and color_image.ballistica_texture.wrap_h == 'clamp'

# The UV map export writes is the render-active one (picked in the panel).
uv_test = bpy.data.meshes.new('uv_test')
uv_test.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
first, second = uv_test.uv_layers.new(name='paint'), uv_test.uv_layers.new(name='atlas')
for loop, uv in enumerate(((0.1, 0.1), (0.2, 0.1), (0.1, 0.2))):
	first.data[loop].uv, second.data[loop].uv = uv, (0.9, 0.9)
assert uv_test.ballistica_asset.export_uv == 'paint'
uv_test.ballistica_asset.export_uv = 'atlas'
assert second.active_render and uv_test.uv_layers.active == first  # editing stays on 'paint'
from ballistica_cloud_tools import scene  # noqa: E402
assert {tuple(round(c, 3) for c in uv) for uv in scene.obj_from_mesh(uv_test).uvs} == {(0.9, 0.9)}
bpy.data.meshes.remove(uv_test)

# Colorize: the bundled asset group, driven by the collection's tints.
from ballistica_cloud_tools import nodegroup  # noqa: E402

libraries = [lib.name for lib in bpy.context.preferences.filepaths.asset_libraries]
assert nodegroup.LIBRARY_NAME in libraries, libraries
group = bpy.data.node_groups[nodegroup.GROUP_NAME]
assert group.asset_data is not None, 'node group should stay marked as an asset'
assert [s.name for s in group.interface.items_tree if s.in_out == 'INPUT'] == [n for n, _ in nodegroup.INPUTS] + ['Reflection', 'Reflection Scale']

# Reflections: body and eyes look up the bundled environments; the body's
# strength follows the panel's reflection_scale.
body_mat = bpy.data.materials['agent_johnson']
body_group = next(n for n in body_mat.node_tree.nodes if n.type == 'GROUP')
env = body_group.inputs['Reflection'].links[0].from_node
assert env.type == 'TEX_ENVIRONMENT' and env.image.name == nodegroup.REFLECTION_CHAR, env
assert env.inputs['Vector'].links[0].from_socket.name == 'Reflection'
assert abs(body_group.inputs['Reflection Scale'].default_value - 0.2) < 1e-6  # agent_johnson.bchar
bpy.data.collections['agent_johnson'].ballistica_character.reflection_scale = 0.7
bpy.context.view_layer.update()
assert abs(body_group.inputs['Reflection Scale'].default_value - 0.7) < 1e-6
bpy.data.collections['agent_johnson'].ballistica_character.reflection_scale = 0.2
bpy.context.view_layer.update()
eye_mats = {m.name: m for m in bpy.data.materials if m.name.startswith(('zoe_eye', 'zoe_iris'))}
for name, image, strength in (('zoe_eye', nodegroup.REFLECTION_SHARPEST, 3.0), ('zoe_iris', nodegroup.REFLECTION_SHARPEST, 2.0), ('zoe_eyelid', nodegroup.REFLECTION_CHAR, 0.05)):
	g = next(n for n in eye_mats[name].node_tree.nodes if n.type == 'GROUP')
	assert g.inputs['Reflection'].links[0].from_node.image.name == image, name
	assert abs(g.inputs['Reflection Scale'].default_value - strength) < 1e-6, name
assert [s.name for s in group.interface.items_tree if s.in_out == 'OUTPUT'] == ['Color']
output = next(n for n in bpy.data.materials['agent_johnson'].node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
assert output.inputs['Surface'].links[0].from_socket.name == 'Color'
agent = bpy.data.collections['agent_johnson']
material = bpy.data.materials['agent_johnson']
node = next(n for n in material.node_tree.nodes if n.type == 'GROUP')
agent.ballistica_character.highlight = (0.25, 0.5, 0.75)
bpy.context.view_layer.update()
value = tuple(round(v, 4) for v in node.inputs['Highlight 2'].default_value[:3])
assert value == (0.25, 0.5, 0.75), value
agent.ballistica_character.highlight = (1.0, 0.5, 0.3)  # back to the file's value

assert [o.name for o in bpy.data.collections['agent_johnson Head'].objects] == ['head']
assert sorted(o.name for o in bpy.data.collections['agent_johnson Legs'].objects) == sorted(f'{p}.{s}' for p in ('upper_leg', 'lower_leg', 'toes') for s in 'RL')
from ballistica_cloud_tools.scene import _layer_collections  # noqa: E402
hidden = {c.name for c in agent.children if next(_layer_collections(bpy.context.view_layer.layer_collection, c)).hide_viewport}
assert hidden == {'agent_johnson Rig', 'agent_johnson Eyes', 'agent_johnson Guides'}, hidden
assert [c.name for c in agent.children] == [f'agent_johnson {g}' for g in ('Rig', 'Head', 'Body', 'Arms', 'Legs', 'Attachments', 'Eyes', 'Guides')]
head = next(o for o in agent.all_objects if o.name == 'head')
make_active(head)
assert bpy.ops.ballistica.export_character() == {'FINISHED'}
changed = sorted(k for k, v in snapshot().items() if before.get(k) != v)
assert changed == [], changed

head.data.vertices[0].co.x += 0.01
bpy.ops.ballistica.export_character()
changed = sorted(k for k, v in snapshot().items() if before.get(k) != v)
assert changed == ['meshes/agent_head.obj'], changed
original = objfile.read(os.path.join(SAMPLE, 'meshes', 'agent_head.obj'))
written = objfile.read(os.path.join(ws, 'meshes', 'agent_head.obj'))
assert len(original.faces) == len(written.faces)

# Modifiers are applied on export, and changing one counts as a change.
head_file = os.path.join(ws, 'meshes', 'agent_head.obj')
subsurf = head.modifiers.new('Subdivision', 'SUBSURF')
subsurf.levels = 1
bpy.ops.ballistica.export_character()
assert len(objfile.read(head_file).faces) > len(original.faces) * 3, 'subdivided head should be exported'
with open(head_file, 'rb') as infile:
	subdivided = infile.read()
bpy.ops.ballistica.export_character()  # unchanged: not rewritten
with open(head_file, 'rb') as infile:
	assert infile.read() == subdivided
head.modifiers.remove(subsurf)
bpy.ops.ballistica.export_character()
assert len(objfile.read(head_file).faces) == len(original.faces), 'removing the modifier should export the base mesh'
# Moving the object never changes the export.
head.location.x += 1.0
before_move = snapshot()
bpy.ops.ballistica.export_character()
assert snapshot() == before_move
head.location.x -= 1.0

# Bones: chains are connected; panel offsets drive the offset bones.
from mathutils import Vector  # noqa: E402
from ballistica_cloud_tools import scene  # noqa: E402

arm = next(o for o in bpy.data.collections['agent_johnson Rig'].objects if o.type == 'ARMATURE')
bones = arm.data.bones
assert bones['forearm.R'].use_connect and bones['toes.L'].use_connect and bones['head'].use_connect
assert bones['heel.R'].use_connect and bones['toes.R'].parent.name == 'heel.R' and bones['heel.R'].parent.name == 'lower_leg.R'
assert all(arm.pose.bones['heel.L'].lock_rotation)
assert bones['upper_arm.R'].parent.name == 'shoulder_offset.R'
assert bones['eye_offset.L'].parent.name == 'head'
settings = agent.ballistica_character


def game_head(bone):
	"""A pose bone's head in game space (armature space, game axes)."""
	return scene.TO_GAME @ arm.pose.bones[bone].head


settings.shoulder_offset = (0.0, 0.0, 0.0)
settings.eye_offset = (0.0, 0.0, 0.0)
bpy.context.view_layer.update()
base = {b: game_head(b) for b in ('upper_arm.R', 'upper_arm.L', 'eye_offset.L', 'eye_offset.R')}
scale = agent.ballistica_character.eye_scale
settings.shoulder_offset = (0.03, -0.02, 0.01)
settings.eye_offset = (0.07, -0.03, 0.2)
bpy.context.view_layer.update()


def moved(bone):
	return tuple(round(c, 4) for c in game_head(bone) - base[bone])


assert moved('upper_arm.R') == (0.03, -0.02, 0.01), moved('upper_arm.R')
assert moved('upper_arm.L') == (-0.03, -0.02, 0.01), moved('upper_arm.L')
# The +X eye is the right one (as the engine draws it); offsets scale with eye_scale.
expected = tuple(round(c * scale, 4) for c in (0.07, -0.03, 0.2))
assert moved('eye_offset.R') == expected, (moved('eye_offset.R'), expected)
assert moved('eye_offset.L') == (-expected[0], expected[1], expected[2]), moved('eye_offset.L')
# The eye stand-in sits at head centre + eye_offset (Zoe has visible eyes).
zoe = bpy.data.collections['zoe']
zoe.ballistica_character.eye_offset = (0.07, -0.03, 0.2)
bpy.context.view_layer.update()
zoe_arm = next(o for o in zoe.all_objects if o.type == 'ARMATURE')
eye_obj = next(o for o in bpy.data.collections['zoe Eyes'].objects if o.name.startswith('eye.R'))
head_centre = scene.TO_GAME @ (zoe_arm.matrix_world @ zoe_arm.pose.bones['head'].tail)
offset = tuple(round(c, 4) for c in (scene.TO_GAME @ eye_obj.matrix_world.translation) - head_centre)
zscale = zoe.ballistica_character.eye_scale
assert offset == tuple(round(c * zscale, 4) for c in (0.07, -0.03, 0.2)), (offset, zscale)
# The eye handle: on the +X eye; Position and Size are what people mean.
from ballistica_cloud_tools import eye_scene  # noqa: E402

zhandle = eye_scene.handle(zoe)
bpy.context.view_layer.update()
assert (zhandle.matrix_world.translation - eye_obj.matrix_world.translation).length < 1e-5
assert abs(zhandle.scale.x - zscale) < 1e-6
zset = zoe.ballistica_character
where = tuple(zset.eye_position)
zset.eye_size = zscale * 1.2  # bigger eyes stay put
assert all(abs(a - b) < 1e-5 for a, b in zip(zset.eye_position, where)), (tuple(zset.eye_position), where)
assert all(abs(a - b / (zscale * 1.2)) < 1e-5 for a, b in zip(zset.eye_offset, where))
assert abs(zhandle.scale.x - zscale * 1.2) < 1e-6  # the handle follows the panel
zhandle.location.z += 0.02  # dragged up in the viewport (Blender +Z is game +Y)
bpy.context.view_layer.update()
assert abs(zset.eye_position[1] - (where[1] + 0.02)) < 1e-5, (tuple(zset.eye_position), where)
zhandle.rotation_euler.y = -__import__('math').radians(12.0)  # turned: the eyelids tilt
bpy.context.view_layer.update()
assert abs(zset.eyelid_angle - 12.0) < 1e-3, zset.eyelid_angle
zhandle.rotation_euler.y = -__import__('math').radians(80.0)  # past the game's range
bpy.context.view_layer.update()
assert abs(zset.eyelid_angle - 30.0) < 1e-3 and abs(zhandle.rotation_euler.y + __import__('math').radians(30.0)) < 1e-5
zset.eyelid_angle = 0.0
assert abs(zhandle.rotation_euler.y) < 1e-6 and tuple(zhandle.lock_rotation) == (True, False, True)
assert zhandle.users_collection[0] == bpy.data.collections['zoe Rig']
zhandle.scale = (zscale,) * 3
zhandle.location.z -= 0.02
bpy.context.view_layer.update()
assert abs(zset.eye_scale - zscale) < 1e-6 and all(abs(a - b) < 1e-5 for a, b in zip(zset.eye_position, where))

# Sizes: guides and eyes follow the panel's radii and eye scale.
zs = zoe.ballistica_character
zs.torso_radius, zs.thigh_radius, zs.ankle_radius, zs.eye_scale = 0.25, 0.06, 0.045, 1.5
bpy.context.view_layer.update()
import re  # noqa: E402
guide = {re.sub(r'\.\d{3}$', '', o.name): o for o in bpy.data.collections['zoe Guides'].objects}


def dims(obj):
	return tuple(round(d, 3) for d in obj.dimensions)


assert dims(guide['guide_torso'])[0] == 0.5, dims(guide['guide_torso'])
assert dims(guide['guide_upper_leg.R'])[0] == 0.12 and dims(guide['guide_upper_leg.L'])[1] == round(0.12 + 2 * 0.06, 3), dims(guide['guide_upper_leg.L'])
assert dims(guide['guide_lower_leg.R'])[0] == 0.09 and dims(guide['guide_lower_leg.R'])[1] == 0.26, dims(guide['guide_lower_leg.R'])
assert dims(eye_obj)[0] == round(0.18 * 1.5, 3), dims(eye_obj)  # the game's eyeball: radius 0.09 x eye_scale
eyes = [o for o in bpy.data.collections['zoe Eyes'].objects if o.name.startswith('eye.')]
lids = [o for o in bpy.data.collections['zoe Eyes'].objects if o.name.startswith('eyelid.')]
assert len(eyes) == 2 and len(lids) == 2
assert all([s.material.name for s in o.material_slots] == ['zoe_eye', 'zoe_iris'] for o in eyes)  # ball, iris
assert {o.data.name for o in eyes} == {'eye_ball'} and {o.data.name for o in lids} == {'eye_lid'}  # shared meshes
assert all(lid.parent in eyes for lid in lids)
left = next(o for o in eyes if o.ballistica_part.side == 'L')
assert tuple(round(v, 3) for v in left.scale) == (-1.5, 1.5, 1.5), tuple(left.scale)  # the -X eye is the mirrored one

bpy.ops.ballistica.export_character()
import json  # noqa: E402
saved = json.load(open(os.path.join(ws, 'characters', 'agent_johnson.bchar')))['data']
assert saved['shoulder_offset'] == [0.03, -0.02, 0.01], saved.get('shoulder_offset')
assert saved['eye_offset'] == [0.07, -0.03, 0.2], saved.get('eye_offset')

# Eyes: both always exist and hide while their style is 'none'.
agent_eyes = {o.ballistica_part.side: o for o in bpy.data.collections['agent_johnson Eyes'].objects if o.name.startswith('eye.')}
agent_lids = {o.ballistica_part.side: o for o in bpy.data.collections['agent_johnson Eyes'].objects if o.name.startswith('eyelid.')}
assert set(agent_eyes) == {'L', 'R'}
assert agent_eyes['L'].hide_viewport and agent_eyes['R'].hide_render  # Agent Johnson's eyes are 'none'
agent.ballistica_character.eye_style_left = 'regular'
bpy.context.view_layer.update()
assert not agent_eyes['L'].hide_viewport and not agent_eyes['L'].hide_render
assert agent_eyes['R'].hide_viewport  # the right eye is still 'none'
assert not agent_lids['L'].hide_viewport  # regular: lid shown
agent.ballistica_character.eye_style_left = 'lidless'
bpy.context.view_layer.update()
assert not agent_eyes['L'].hide_viewport and agent_lids['L'].hide_viewport  # lidless: ball, no lid
agent.ballistica_character.eyelid_angle = 20.0
bpy.context.view_layer.update()
import math  # noqa: E402
assert abs(agent_lids['L'].rotation_euler.y - math.radians(-20.0)) < 1e-6, agent_lids['L'].rotation_euler.y
agent.ballistica_character.eyelid_angle = 0.0
agent.ballistica_character.eye_style_left = 'none'
bpy.context.view_layer.update()
assert agent_eyes['L'].hide_viewport

# Parts start with identity transforms. Reset to T-Pose resets only the
# pose; Repair puts moved parts back (all, or only the selected ones).
legs = [o for o in agent.all_objects if o.ballistica_part.role in ('upper_leg', 'toes')]
assert all(o.matrix_basis == __import__('mathutils').Matrix.Identity(4) for o in legs)
home = {o.name: o.matrix_world.copy() for o in legs}
for o in legs:
	o.location = (0.5, 0.2, -0.1)
	o.rotation_euler = (0.3, 0.0, 1.0)
arm.pose.bones['upper_leg.R'].rotation_quaternion = (0.7, 0.7, 0.0, 0.0)  # pose a leg too
arm.location = (0.3, 0.0, 0.2)  # and move the rig off its root
for o in bpy.context.view_layer.objects:
	o.select_set(False)
make_active(legs[0])
bpy.context.view_layer.update()
assert bpy.ops.ballistica.reset_parts() == {'FINISHED'}
bpy.context.view_layer.update()
assert tuple(arm.pose.bones['upper_leg.R'].rotation_quaternion) == (1.0, 0.0, 0.0, 0.0)
assert tuple(arm.location) == (0.0, 0.0, 0.0)
assert all((o.location - __import__('mathutils').Vector((0.5, 0.2, -0.1))).length < 1e-6 for o in legs)  # parts untouched
from ballistica_cloud_tools import repair  # noqa: E402
assert sorted(i.name for i in repair.issues(agent) if i.kind == repair.MOVED) == sorted(o.name for o in legs)
legs[0].select_set(True)
assert bpy.ops.ballistica.repair(selected=True) == {'FINISHED'}
assert legs[0].location.length == 0 and legs[1].location.length > 0.5
arm.pose.bones['upper_leg.R'].rotation_quaternion = (0.7, 0.7, 0.0, 0.0)  # Repair never changes the pose
posed = tuple(arm.pose.bones['upper_leg.R'].rotation_quaternion)
assert bpy.ops.ballistica.repair() == {'FINISHED'}
assert tuple(arm.pose.bones['upper_leg.R'].rotation_quaternion) == posed, tuple(arm.pose.bones['upper_leg.R'].rotation_quaternion)
arm.pose.bones['upper_leg.R'].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
bpy.context.view_layer.update()
for o in legs:
	assert all(abs(a - b) < 1e-6 for ra, rb in zip(o.matrix_world, home[o.name]) for a, b in zip(ra, rb)), o.name
assert repair.issues(agent) == [], repair.issues(agent)
moved = tuple(round(c, 4) for c in game_head('upper_arm.R') - base['upper_arm.R'])
assert moved == (0.03, -0.02, 0.01), moved  # driven shoulder offset survives the reset

# Root: a flat circle curve in the character collection, parent of the rig;
# moving it moves the whole character.
root = next(o for o in agent.objects if o.name.endswith('_root'))
assert root.type == 'CURVE' and arm.parent == root
assert all(abs(p.co.z) < 1e-9 for p in root.data.splines[0].points)  # flat on the ground
assert tuple(root.rotation_euler) == (0.0, 0.0, 0.0)
head_obj = next(o for o in agent.all_objects if o.name == 'head')
before = head_obj.matrix_world.translation.copy()
root.location = (1.0, 2.0, 0.0)
bpy.context.view_layer.update()
assert (head_obj.matrix_world.translation - before - __import__('mathutils').Vector((1.0, 2.0, 0.0))).length < 1e-6
root.location = (0.0, 0.0, 0.0)
bpy.context.view_layer.update()

# Standard colors: sets the view transform, then has nothing left to do.
from ballistica_cloud_tools import operators as ops  # noqa: E402
assert not ops.uses_standard_colors(bpy.context.scene)  # factory default is AgX
assert bpy.ops.ballistica.standard_colors() == {'FINISHED'}
assert ops.uses_standard_colors(bpy.context.scene)
assert not bpy.ops.ballistica.standard_colors.poll()

from types import SimpleNamespace  # noqa: E402

# Exploded view: Spread moves each part by the web UI's spread offset.
from ballistica_cloud_tools import pose  # noqa: E402

forearms = {o.ballistica_part.side: o for o in agent.all_objects if o.ballistica_part.role == 'forearm'}
before = {k: scene.TO_GAME @ o.matrix_world.translation for k, o in forearms.items()}
agent.ballistica_character.spread = 1.0
bpy.context.view_layer.update()
for side, sign in (('R', 1), ('L', -1)):
	moved = scene.TO_GAME @ forearms[side].matrix_world.translation - before[side]
	expect = (sign * pose.SPREAD['forearm'][0], pose.SPREAD['forearm'][1], pose.SPREAD['forearm'][2])
	assert all(abs(a - b) < 1e-4 for a, b in zip(moved, expect)), (side, tuple(moved), expect)
agent.ballistica_character.spread = 0.0
bpy.context.view_layer.update()
assert all(abs(a - b) < 1e-5 for a, b in zip(scene.TO_GAME @ forearms['R'].matrix_world.translation, before['R']))

# Eyes: the eyeball is turned by eyeball_pitch (its up axis tips back); its lid is not.
zoe_eye = next(o for o in bpy.data.collections['zoe Eyes'].objects if o.name.startswith('eye.R'))
zoe_lid = next(o for o in bpy.data.collections['zoe Eyes'].objects if o.name.startswith('eyelid.R'))
up = (scene.TO_GAME @ zoe_eye.matrix_world.to_3x3() @ scene.TO_BLENDER @ Vector((0, 1, 0))).normalized()
assert abs(up.z + __import__('math').sin(__import__('math').radians(10))) < 1e-4, tuple(up)
lid_up = (scene.TO_GAME @ zoe_lid.matrix_world.to_3x3() @ scene.TO_BLENDER @ Vector((0, 1, 0))).normalized()
assert abs(lid_up.z) < 1e-4, tuple(lid_up)

# Pixel against the web UI's preview data (tests/fixtures/pixel_preview.json).
pixel = bpy.data.collections['pixel']
with open(os.path.join(ADDON, 'tests', 'fixtures', 'pixel_preview.json')) as f:
	web = json.load(f)
pixel_objects = list(pixel.all_objects)
torso_obj = next(o for o in pixel_objects if o.ballistica_part.role == 'torso')
centre = scene.TO_GAME @ torso_obj.matrix_world.translation


def game_frame(obj):
	"""(position relative to the torso, unit axes as columns) in game space."""
	m = scene.TO_GAME @ obj.matrix_world.to_3x3() @ scene.TO_BLENDER
	axes = [m.col[i].normalized() for i in range(3)]
	return scene.TO_GAME @ obj.matrix_world.translation - centre, axes


def web_frame(entry):
	x = entry['xform']
	cols = [Vector(x[i * 4:i * 4 + 3]).normalized() for i in range(3)]
	return Vector(x[12:15]), cols


def close(a, b, tol=1e-3):
	return all(abs(p - q) < tol for p, q in zip(a, b))


pixel_eye = next(o for o in pixel_objects if o.name.startswith('eye.') and (scene.TO_GAME @ o.matrix_world.translation).x > 0)
pixel_lid = next(o for o in pixel_objects if o.name.startswith('eyelid.') and (scene.TO_GAME @ o.matrix_world.translation).x > 0)
for obj, key in ((pixel_eye, 'eye_left'), (pixel_lid, 'eyelid_left')):
	(pos, axes), (wpos, waxes) = game_frame(obj), web_frame(web[key])
	assert close(pos, wpos), (key, tuple(pos), tuple(wpos))
	for a, b in zip(axes, waxes):
		assert close(a, b), (key, tuple(a), tuple(b))
guide = {re.sub(r'\.\d{3}$', '', o.name): o for o in bpy.data.collections['pixel Guides'].objects}
assert dims(guide['guide_upper_leg.R'])[0] == 0.12 and dims(guide['guide_upper_leg.R'])[1] == 0.24, dims(guide['guide_upper_leg.R'])
assert dims(guide['guide_lower_leg.R'])[0] == 0.09 and dims(guide['guide_lower_leg.R'])[1] == 0.26, dims(guide['guide_lower_leg.R'])
wings = [o for o in pixel_objects if o.ballistica_part.role == 'attachment']
before = {o.name: scene.TO_GAME @ o.matrix_world.translation for o in wings}
pixel.ballistica_character.spread = 1.0
bpy.context.view_layer.update()
for o in wings:
	moved = scene.TO_GAME @ o.matrix_world.translation - before[o.name]
	side = -1 if moved.x < 0 else 1  # right wing spreads toward -X
	assert close(moved, (side * 0.42183, 0.0, -0.26844)), (o.name, tuple(moved))
pixel.ballistica_character.spread = 0.0
bpy.context.view_layer.update()

# Frame Character: framable while only its Rig toggle hides it; otherwise a
# specific problem is reported (headless Blender can't run View Selected).
ctx = SimpleNamespace(view_layer=bpy.context.view_layer)
assert operators._framable_rig(ctx, agent)[2] is None  # Rig collection hidden by its toggle: fine
arm.hide_set(True)
assert 'unhide it' in operators._framable_rig(ctx, agent)[2]
arm.hide_set(False)
agent_layer = next(_layer_collections(bpy.context.view_layer.layer_collection, agent))
agent_layer.hide_viewport = True
assert operators._framable_rig(ctx, agent)[2] == 'agent_johnson is hidden; show it in the outliner to frame the character.'
agent_layer.hide_viewport = False
rig_layer = next(_layer_collections(bpy.context.view_layer.layer_collection, bpy.data.collections['agent_johnson Rig']))
rig_layer.exclude = True
assert 'excluded' in operators._framable_rig(ctx, agent)[2]
rig_layer.exclude = False
rig_layer.hide_viewport = True  # excluding resets the toggle; keep it hidden as imported

# A missing assets file must fail the import loudly, building nothing.
real = nodegroup.ASSETS_BLEND
nodegroup.ASSETS_BLEND = real + '.missing'
# Hide the loaded group by renaming it, rather than deleting it: deleting
# would strip the inputs every existing material's tint drivers point at
# (36 "Invalid driver" warnings for the rest of the run).
loaded = bpy.data.node_groups[nodegroup.GROUP_NAME]
loaded.name = nodegroup.GROUP_NAME + ' (hidden by test)'
count = len(bpy.data.collections)
try:
	bpy.ops.ballistica.import_character(filepath=os.path.join(ws, 'characters', 'spaz.bchar'))
	raise AssertionError('import should have failed')
except RuntimeError as exc:
	assert 'Bundled asset file not found' in str(exc), exc
assert len(bpy.data.collections) == count
nodegroup.ASSETS_BLEND = real
loaded.name = nodegroup.GROUP_NAME

# Attachments: handles hold the placement; meshes move freely.
import json  # noqa: E402
from ballistica_cloud_tools import attach_scene, props  # noqa: E402
zoe = bpy.data.collections['zoe']
with open(os.path.join(ws, 'characters', 'zoe.bchar')) as infile:
	zoe_attachments = json.load(infile)['data']['attachments']


def written_attachments(collection):
	attach_scene.sync_from_handles(collection)
	return props.to_character(collection.ballistica_character).data['attachments']


assert len(attach_scene.tagged(zoe, attach_scene.ANCHOR)) == 3
assert written_attachments(zoe) == zoe_attachments  # untouched: identical
hair = next(o for o in attach_scene.tagged(zoe, attach_scene.MESH) if o[attach_scene.INDEX_KEY] == 0)
hair.location.x += 0.5  # moved away to paint it
assert written_attachments(zoe) == zoe_attachments  # mesh moves aren't placement
for o in bpy.context.view_layer.objects:
	o.select_set(False)
hair.select_set(True)
make_active(hair)
assert [i.kind for i in repair.issues(zoe)] == [repair.MOVED]
assert bpy.ops.ballistica.repair(selected=True) == {'FINISHED'}
assert tuple(hair.location) == (0.0, 0.0, 0.0)
spot = attach_scene.anchor(zoe, 0)
spot.location.z += 0.01  # Blender +Z is game +Y: up by 0.01
assert written_attachments(zoe)[0]['transform']['translate'] == [-0.173, 0.134, 0.153]
spot.location.z -= 0.01
assert written_attachments(zoe) == zoe_attachments

# Rebuild keeps handle edits and follows kind changes.
spot.location.z += 0.02
zoe.ballistica_character.attachments[2].kind = 'antenna_4'  # triggers a rebuild
assert len([o for o in attach_scene.tagged(zoe, attach_scene.HANDLE) if o[attach_scene.INDEX_KEY] == 2]) == 4
assert abs(zoe.ballistica_character.attachments[0].translate[1] - (0.124 + 0.02)) < 1e-5
zoe.ballistica_character.attachments[2].target = 'hand'  # limbs: static only, both sides
assert zoe.ballistica_character.attachments[2].kind == 'static'
sides = sorted(o[attach_scene.SIDE_KEY] for o in attach_scene.tagged(zoe, attach_scene.ANCHOR, 2))
assert sides == ['L', 'R'], sides

# Attachment operators: add, move, remove, select.
from ballistica_cloud_tools import ui  # noqa: E402
zoe = bpy.data.collections['zoe']
settings = zoe.ballistica_character
for obj in bpy.context.view_layer.objects:
	obj.select_set(False)
make_active(next(o for o in zoe.all_objects if o.ballistica_part.role == 'head'))
attach_scene.sync_from_handles(zoe)
before_ops = props.to_character(settings).data['attachments']
third = (settings.attachments[2].target, settings.attachments[2].kind)
assert bpy.ops.ballistica.attachment_add() == {'FINISHED'}
assert len(settings.attachments) == 4 and settings.active_attachment_index == 3
added = settings.attachments[3]
assert (added.target, added.kind, len(added.segments)) == ('head', 'antenna', 1)
assert added.segments[0].mesh.startswith('meshes/zoe_attachment')
assert attach_scene.anchor(zoe, 3) is not None
assert not [p for p in operators.check(zoe) if 'attachments[3]' in p or 'Attachment 4' in p], operators.check(zoe)
assert bpy.ops.ballistica.attachment_move(direction='UP') == {'FINISHED'}
assert settings.active_attachment_index == 2
assert settings.attachments[2].segments[0].mesh.startswith('meshes/zoe_attachment')
assert (settings.attachments[3].target, settings.attachments[3].kind) == third  # Zoe's third moved down
assert bpy.ops.ballistica.attachment_select(segment=-1) == {'FINISHED'}
assert bpy.context.view_layer.objects.active == attach_scene.anchor(zoe, 2)
make_active(next(o for o in zoe.all_objects if o.ballistica_part.role == 'head'))
assert bpy.ops.ballistica.attachment_remove() == {'FINISHED'}
assert len(settings.attachments) == 3
assert sorted({o[attach_scene.INDEX_KEY] for o in attach_scene.tagged(zoe, attach_scene.ANCHOR)}) == [0, 1, 2]
assert written_attachments(zoe) == before_ops


# Clicking a list row selects its meshes; making a mesh active picks its row.
def meshes_of(index, segment=None):
	return {o.name for o in attach_scene.tagged(zoe, attach_scene.MESH, index)
		if segment is None or o[attach_scene.SEGMENT_KEY] == segment}


settings.active_attachment_index = 1
assert {o.name for o in bpy.context.selected_objects} == meshes_of(1)
assert bpy.context.view_layer.objects.active.name in meshes_of(1)
settings.active_attachment_index = 0
assert {o.name for o in bpy.context.selected_objects} == meshes_of(0)
settings.attachments[0].active_segment_index = 0
assert {o.name for o in bpy.context.selected_objects} == meshes_of(0, 0)
other = next(o for o in attach_scene.tagged(zoe, attach_scene.MESH, 1))
make_active(other)
assert settings.active_attachment_index == 1
settings.active_attachment_index = 1  # selects its mesh, then a rebuild replaces it
settings.attachments[1].kind = 'static'
assert ui.active_character(bpy.context) == zoe  # still on the character after the rebuild
assert {o.name for o in bpy.context.selected_objects} == meshes_of(1)
bpy.context.scene.cursor.location = (2.0, -1.0, 0.5)
assert bpy.ops.ballistica.import_character(filepath=os.path.join(ws, 'characters', 'pixel.bchar')) == {'FINISHED'}
bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
new_root = bpy.context.view_layer.objects.active  # import selects the new character's root
assert new_root.name == 'pixel.001_root' and new_root.select_get(), new_root
assert tuple(new_root.location) == (2.0, -1.0, 0.5), tuple(new_root.location)  # placed at the 3D cursor
assert [o.name for o in bpy.context.selected_objects] == ['pixel.001_root']

# Parts list: each row holds its part's mesh; the scene follows the rows.
from ballistica_cloud_tools import part_scene  # noqa: E402
agent = bpy.data.collections['agent_johnson']
agent_settings = agent.ballistica_character
assert [(r.part, r.side) for r in agent_settings.parts] == part_scene.ROWS
rows = {(r.part, r.side): r for r in agent_settings.parts}
head_obj = next(o for o in agent.all_objects if o.ballistica_part.role == 'head')
torso_obj = next(o for o in agent.all_objects if o.ballistica_part.role == 'torso')
head_row, torso_row = rows[('head', 'CENTER')], rows[('torso', 'CENTER')]
assert head_row.mesh == head_obj.data and head_row.enabled
agent_head_mesh = head_row.mesh
head_row.mesh = torso_row.mesh  # picked another mesh
assert head_obj.data == torso_obj.data
head_row.mesh = agent_head_mesh
assert head_obj.data == agent_head_mesh
hand_row = rows[('hand', 'R')]
hand_row.enabled = False  # optional part off: objects removed, mesh kept
assert not [o for o in agent.all_objects if o.ballistica_part.role == 'hand'] and hand_row.mesh is not None
assert part_scene.fields(agent)['hand_mesh'] == ''
hand_row.enabled = True  # on again: both sides, same mesh
hands = [o for o in agent.all_objects if o.ballistica_part.role == 'hand']
assert sorted(o.ballistica_part.side for o in hands) == ['L', 'R'] and all(o.parent_bone for o in hands)
assert all(o.data == hand_row.mesh for o in hands) and part_scene.fields(agent)['hand_mesh'] == 'meshes/agent_hand'
right_toes = next(o for o in agent.all_objects if o.ballistica_part.role == 'toes' and o.ballistica_part.side == 'R')
left_toes = next(o for o in agent.all_objects if o.ballistica_part.role == 'toes' and o.ballistica_part.side == 'L')
left_row = rows[('toes', 'L')]
assert not left_row.enabled and left_toes.data == right_toes.data
left_row.enabled = True  # own left mesh: a copy of the right one
assert left_toes.data == left_row.mesh != right_toes.data and len(left_row.mesh.vertices) == len(right_toes.data.vertices)
assert part_scene.fields(agent)['left_toes_mesh'] == 'meshes/agent_johnson_left_toes'
left_row.enabled = False  # mirrors the right again
assert left_toes.data == right_toes.data and part_scene.fields(agent)['left_toes_mesh'] == ''
was_active = bpy.context.scene.ballistica_active_character
bpy.context.scene.ballistica_active_character = agent
agent_settings.active_part_index = list(rows).index(('head', 'CENTER'))
assert bpy.ops.ballistica.new_part_mesh() == {'FINISHED'}  # a box to model from, no export path yet
assert head_obj.data != agent_head_mesh and len(head_obj.data.polygons) > 0, (head_obj.data, head_row.mesh, agent_head_mesh, head_obj.name)
assert part_scene.fields(agent)['head_mesh'] == 'meshes/agent_johnson_head'
head_row.mesh = None  # cleared with the picker's X
assert any(p.startswith('Head: no mesh picked') for p in operators.check(agent)), operators.check(agent)
head_row.mesh = agent_head_mesh
head_obj = next(o for o in agent.all_objects if o.ballistica_part.role == 'head')  # made again
# Clicking a row selects its object; making a part active picks its row.
for o in bpy.context.view_layer.objects:
	o.select_set(False)
agent_settings.active_part_index = list(rows).index(('hand', 'R'))
assert [o.name for o in bpy.context.view_layer.objects.selected] == [o.name for o in hands if o.ballistica_part.side == 'R']
make_active(left_toes)
assert agent_settings.parts[agent_settings.active_part_index] == left_row
bpy.context.scene.ballistica_active_character = was_active

agent_settings.flippers = True  # with forearm and hand meshes still set
assert any('Flippers is on' in p for p in operators.check(agent))
agent_settings.flippers = False
assert not any('Flippers' in p for p in operators.check(agent))

# The character list: the scene's active character, independent of selection.
scene = bpy.context.scene
assert [c.name for c in ui.characters(scene)][:3] == ['agent_johnson', 'zoe', 'pixel']
assert scene.ballistica_active_character == bpy.data.collections['pixel.001']  # import made it active
make_active(next(o for o in zoe.all_objects if o.ballistica_part.role == 'torso'))
assert scene.ballistica_active_character == zoe  # clicking any part of a character picks it
scene.ballistica_character_index = list(bpy.data.collections).index(bpy.data.collections['agent_johnson'])
assert ui.active_character(bpy.context).name == 'agent_johnson'  # clicking its row
bpy.context.view_layer.objects.active = None
assert ui.active_character(bpy.context).name == 'agent_johnson'  # nothing selected: still shown
bpy.data.collections.new('zzz_not_a_character')  # re-sorts bpy.data.collections
assert ui.active_character(bpy.context).name == 'agent_johnson'
assert bpy.data.collections[scene.ballistica_character_index].name == 'agent_johnson'
scene.ballistica_character_index = list(bpy.data.collections).index(bpy.data.collections['zzz_not_a_character'])
assert ui.active_character(bpy.context).name == 'agent_johnson'  # non-characters can't be picked
scene.ballistica_active_character = zoe

# Visibility buttons toggle a group's viewport visibility.
from ballistica_cloud_tools.scene import _layer_collections  # noqa: E402
eyes_group = bpy.data.collections['zoe Eyes']
eyes_layer = next(_layer_collections(bpy.context.view_layer.layer_collection, eyes_group))
was_hidden = eyes_layer.hide_viewport
assert bpy.ops.ballistica.toggle_group(collection=eyes_group.name) == {'FINISHED'}
assert eyes_layer.hide_viewport == (not was_hidden)
bpy.ops.ballistica.toggle_group(collection=eyes_group.name)
assert eyes_layer.hide_viewport == was_hidden

# New Character starting from an existing one: own copies of its files.
with open(os.path.join(ws, 'characters', 'zoe.bchar')) as infile:
	zoe_data = json.load(infile)['data']
before_copy = snapshot()
assert bpy.ops.ballistica.new_character(directory=ws, name='zoey', start_from='characters/zoe') == {'FINISHED'}
zoey = bpy.data.collections['zoey']
assert snapshot() == before_copy  # nothing written before export
zs = zoey.ballistica_character
assert zs.head_mesh == 'meshes/zoey_head' and zs.color_texture == 'textures/zoey_color'
assert tuple(round(c, 4) for c in zs.color) == tuple(round(c, 4) for c in zoe_data['color'])
assert len(zs.attachments) == len(zoe_data.get('attachments', []))
assert all(seg.mesh.startswith('meshes/zoey_') for a in zs.attachments for seg in a.segments)
assert operators.check(zoey) == [], operators.check(zoey)
make_active(next(o for o in zoey.all_objects if o.ballistica_part.role == 'head'))
assert bpy.ops.ballistica.export_character() == {'FINISHED'}
changed = sorted(k for k, v in snapshot().items() if before_copy.get(k) != v)
assert all('zoey' in k or k == 'workspace.json' for k in changed), changed
assert 'characters/zoey.bchar' in changed and 'textures/zoey_color.png' in changed
assert not [k for k in changed if 'zoe_' in k or k.endswith('zoe.bchar')]  # the original is untouched
assert bpy.ops.ballistica.import_character(filepath=os.path.join(ws, 'characters', 'zoey.bchar')) == {'FINISHED'}
assert operators.check(bpy.data.collections['zoey.001']) == []
scene.ballistica_active_character = zoe  # the checks below work on Zoe

# New Character, Empty: the whole setup with empty part meshes.
before_empty = snapshot()
assert bpy.ops.ballistica.new_character(directory=ws, name='blanky', start_from='EMPTY') == {'FINISHED'}
blanky = bpy.data.collections['blanky']
assert snapshot() == before_empty  # nothing written before export
parts = [o for o in blanky.all_objects if o.ballistica_part.role in [p for p, _, _ in rig.PARTS]]
assert len(parts) == 15 and all(len(o.data.polygons) == 0 for o in parts)
assert all(o.data.uv_layers.active is not None for o in parts)
assert any(o.ballistica_part.role == 'eye' for o in blanky.all_objects)  # the rest of the setup is there
assert bpy.data.images['blanky_color'].size[:] == (256, 256)
empty_problems = [p for p in operators.check(blanky) if 'mesh is empty' in p]
assert len(empty_problems) == 9, empty_problems  # every right/centre part
import bmesh  # noqa: E402
blanky_head = next(o for o in parts if o.ballistica_part.role == 'head')
bm = bmesh.new()
bm.from_mesh(blanky_head.data)  # keeps its UV map, as modelling in Edit Mode does
bmesh.ops.create_cube(bm, size=0.4)
bm.to_mesh(blanky_head.data)
bm.free()
assert not any(blanky_head.name in p for p in operators.check(blanky))  # modelled: no longer flagged
uv_layer = blanky_head.data.uv_layers.active
uv_layer.data[0].uv = (1.6, 0.5)  # a UV dragged off the texture
assert any(blanky_head.name in p and 'outside the texture' in p for p in operators.check(blanky)), operators.check(blanky)
uv_layer.data[0].uv = (0.5, 0.5)
assert not any('outside the texture' in p for p in operators.check(blanky))
assert not any('outside the texture' in p for p in operators.check(zoe))  # classic meshes are fine
scene.ballistica_active_character = zoe

# The Attachments panel draws (against a stand-in layout that checks every
# property it shows exists).
class StubLayout:
	use_property_split = use_property_decorate = False

	def __getattr__(self, name):
		return lambda *args, **kwargs: StubLayout()

	def prop(self, data, name, **kwargs):
		assert name in data.bl_rna.properties, name

	def panel(self, idname, default_closed=False):
		return StubLayout(), StubLayout()  # (header, body): drawn open

	def template_list(self, listtype, listid, data, prop, active_data, active_prop, **kwargs):
		assert prop in data.bl_rna.properties and active_prop in active_data.bl_rna.properties

	def operator(self, idname, **kwargs):
		category, name = idname.split('.')
		assert hasattr(getattr(bpy.ops, category), name), idname
		return StubLayout()


def draw_panels():
	"""Draw every panel of the addon; a draw error would hide the rest of a panel."""
	for cls in ui.classes:
		if not issubclass(cls, bpy.types.Panel):
			continue
		if hasattr(cls, 'poll') and not cls.poll(bpy.context):
			continue
		panel = type('StubPanel', (), {
			'layout': StubLayout(),
			# Class attributes (fields, groups, header_icon) come from the panel.
			'__getattr__': lambda self, name, cls=cls: getattr(cls, name),
		})()
		if hasattr(cls, 'draw_header'):
			cls.draw_header(panel, bpy.context)
		cls.draw(panel, bpy.context)


for index in range(len(settings.attachments)):
	settings.active_attachment_index = index
	draw_panels()
assert ui.active_character(bpy.context) == zoe
bpy.context.view_layer.objects.active = None
draw_panels()  # nothing selected: the panel still shows the chosen character
settings.flippers = True  # Zoe has forearm and hand meshes: the Meshes note draws
assert rig.flippers_hint(settings.flippers, settings.forearm_mesh, settings.hand_mesh)
draw_panels()
settings.flippers = False

# The character list's eye hides or shows a whole character.
zoe_layer = next(_layer_collections(bpy.context.view_layer.layer_collection, zoe))
assert not zoe_layer.hide_viewport
ui.BALLISTICA_UL_characters.draw_item(None, bpy.context, StubLayout(), None, zoe, 0, None, None, 0)
assert bpy.ops.ballistica.toggle_group(collection=zoe.name) == {'FINISHED'} and zoe_layer.hide_viewport
assert bpy.ops.ballistica.toggle_group(collection=zoe.name) == {'FINISHED'} and not zoe_layer.hide_viewport

# Deleting the active character falls back to another one.
doomed = bpy.data.collections['pixel.001']
scene.ballistica_active_character = doomed
# Two characters using the same mesh files share meshes but not materials.
first_torso = next(o for o in bpy.data.collections['pixel'].all_objects if o.ballistica_part.role == 'torso')
second_torso = next(o for o in doomed.all_objects if o.ballistica_part.role == 'torso')
assert first_torso.data == second_torso.data
assert first_torso.active_material != second_torso.active_material
doomed_materials = {s.material.name for o in doomed.all_objects for s in o.material_slots if s.material}
assert bpy.ops.ballistica.remove_character() == {'FINISHED'}
assert 'pixel.001' not in bpy.data.collections
assert not doomed_materials & set(bpy.data.materials.keys())  # no tint drivers left pointing at nothing
for material in bpy.data.materials:
	drivers = material.node_tree.animation_data.drivers if material.node_tree and material.node_tree.animation_data else []
	assert all(v.targets[0].id is not None for d in drivers for v in d.driver.variables), material.name
assert ui.active_character(bpy.context) is not None and ui.active_character(bpy.context).name != 'pixel.001'
scene.ballistica_active_character = zoe

# New Character: a cuboid character, written only on export, then re-imported.
assert 'cubey' not in bpy.data.collections
assert bpy.ops.ballistica.new_character(directory=os.path.join(ws, 'characters'), name='cubey') == {'FINISHED'}
cubey = bpy.data.collections['cubey']
assert not os.path.exists(os.path.join(ws, 'characters', 'cubey.bchar'))  # nothing written yet
parts = {o.name for o in cubey.all_objects if o.ballistica_part.role in [p for p, _, _ in rig.PARTS]}
assert len(parts) == 15, sorted(parts)  # 3 center parts + 6 paired parts on both sides
assert operators.check(cubey) == [], operators.check(cubey)
mask = bpy.data.images['cubey_color_mask']
pelvis = ((int(2.5 / 3 * 256)) * 256 + int(2.5 / 3 * 256)) * 4  # centre of the pelvis's atlas cell (shorts)
assert tuple(mask.pixels[pelvis:pelvis + 3]) == (1.0, 0.0, 0.0), tuple(mask.pixels[pelvis:pelvis + 3])
for bad_name, message in (('spaz', 'is taken'), ('Bad Name', 'lowercase')):
	try:
		bpy.ops.ballistica.new_character(directory=ws, name=bad_name)
		raise AssertionError(f'new_character should refuse {bad_name!r}')
	except RuntimeError as exc:
		assert message in str(exc), exc
before_cubey = snapshot()
make_active(next(o for o in cubey.all_objects if o.ballistica_part.role == 'head'))
assert bpy.ops.ballistica.export_character() == {'FINISHED'}
new_files = sorted(k for k, v in snapshot().items() if before_cubey.get(k) != v)
expected = sorted(
	[f'meshes/cubey_{p}.obj' for p, _, _ in rig.PARTS]
	+ [f'textures/cubey_{t}.png' for t in ('color', 'color_mask', 'icon', 'icon_color_mask')]
	+ ['characters/cubey.bchar', 'workspace.json'])
assert new_files == expected, new_files
from ballistica_cloud_tools import bchar as _bchar, workspace as _workspace  # noqa: E402
written = _bchar.Character.load(os.path.join(ws, 'characters', 'cubey.bchar'))
assert written.get('torso_mesh') == 'meshes/cubey_torso' and written.get('name') == 'strings/characters/cubey'
assert _workspace.texture_role(ws, os.path.join(ws, 'textures', 'cubey_color_mask.png')) == 'data'
box = objfile.read(os.path.join(ws, 'meshes', 'cubey_head.obj'))
assert len(box.faces) == 12 and len(box.uvs) > 0
after_export = snapshot()
make_active(next(o for o in cubey.all_objects if o.ballistica_part.role == 'head'))
assert bpy.ops.ballistica.export_character() == {'FINISHED'}
assert snapshot() == after_export  # a second export changes nothing
# Add an attachment to the new character; export writes its placeholder mesh.
make_active(next(o for o in cubey.all_objects if o.ballistica_part.role == 'head'))
assert bpy.ops.ballistica.attachment_add() == {'FINISHED'}
cubey.ballistica_character.attachments[0].translate = (0.0, 0.3, 0.0)  # typed in the panel: moves the handle
assert abs(attach_scene.anchor(cubey, 0).location.z - 0.3) < 1e-6
assert bpy.ops.ballistica.export_character() == {'FINISHED'}
assert os.path.isfile(os.path.join(ws, 'meshes', 'cubey_attachment0.obj'))
written = _bchar.Character.load(os.path.join(ws, 'characters', 'cubey.bchar'))
assert written.attachments == [{
	'kind': 'antenna', 'segments': [{'mesh': 'meshes/cubey_attachment0'}], 'target': 'head',
	'transform': {'rotate': [0.0, 90.0, 0.0], 'translate': [0.0, 0.3, 0.0]},
}], written.attachments
assert bpy.ops.ballistica.import_character(filepath=os.path.join(ws, 'characters', 'cubey.bchar')) == {'FINISHED'}
assert operators.check(bpy.data.collections['cubey.001']) == []

# Repair: break the character in the ways Blender makes easy, then fix it.
from ballistica_cloud_tools import scene as bscene  # noqa: E402
cubey2 = bpy.data.collections['cubey.001']
scene.ballistica_active_character = cubey2
bpy.context.view_layer.update()


def placed(collection):
	"""World matrices of the character's parts, eyes and attachment meshes."""
	return {
		(o.ballistica_part.role, o.ballistica_part.side, o.name.split('.')[0]): o.matrix_world.copy()
		for o in collection.all_objects if o.ballistica_part.role not in ('NONE', 'guide')
	}


def same_place(a, b):
	assert a.keys() == b.keys(), sorted(set(a) ^ set(b))
	for key in a:
		assert all(abs(x - y) < 1e-4 for ra, rb in zip(a[key], b[key]) for x, y in zip(ra, rb)), (key, a[key], b[key])


home = placed(cubey2)
rig_obj = repair.armature(cubey2)
bpy.data.objects.remove(rig_obj)  # the rig deleted
assert repair.NO_RIG in [i.kind for i in repair.issues(cubey2)]
draw_panels()  # the Needs fixing box draws
assert bpy.ops.ballistica.repair() == {'FINISHED'}
assert repair.issues(cubey2) == [], repair.issues(cubey2)
bpy.context.view_layer.update()
same_place(placed(cubey2), home)
assert len(bscene.group(cubey2, 'Guides').objects) > 0

rig_obj = repair.armature(cubey2)
with bscene._edit_mode(rig_obj):
	rig_obj.data.edit_bones['head'].tail.z += 0.3  # a bone dragged in Edit Mode
assert repair.RIG_MOVED in [i.kind for i in repair.issues(cubey2)]  # (parts on that bone show as detached too)
assert bpy.ops.ballistica.fix_issue(kind=repair.RIG_MOVED, name='') == {'FINISHED'}
assert repair.issues(cubey2) == []
bpy.context.view_layer.update()
same_place(placed(cubey2), home)

bpy.data.collections.remove(bscene.group(cubey2, 'Legs'))  # its objects drop out of the character
kinds = {i.kind for i in repair.issues(cubey2)}
assert {repair.NO_GROUP, repair.NO_PART} <= kinds, kinds
assert bpy.ops.ballistica.repair() == {'FINISHED'}
assert repair.issues(cubey2) == [], repair.issues(cubey2)
bpy.context.view_layer.update()
same_place(placed(cubey2), home)

spot = attach_scene.anchor(cubey2, 0)
assert tuple(spot.lock_scale) == (True, True, True)  # soft lock: unlockable
spot.scale = (2.0, 2.0, 2.0)
hand = next(o for o in cubey2.all_objects if o.ballistica_part.role == 'hand' and o.ballistica_part.side == 'R')
hand.hide_set(True)
torso = next(o for o in cubey2.all_objects if o.ballistica_part.role == 'torso')
torso.material_slots[0].material = bpy.data.materials.new('kid_paint')
issues = {(i.kind, i.name) for i in repair.issues(cubey2)}
assert issues == {(repair.ANCHOR_SCALED, spot.name), (repair.HIDDEN, hand.name), (repair.MATERIAL, torso.name)}, issues
assert any('anchor' in p for p in operators.check(cubey2))  # Check lists them too
for kind, name in issues:
	assert bpy.ops.ballistica.fix_issue(kind=kind, name=name) == {'FINISHED'}
assert repair.issues(cubey2) == []
assert tuple(spot.scale) == (1.0, 1.0, 1.0) and hand.visible_get() and torso.material_slots[0].material == cubey2.ballistica_character.body_material

bpy.data.objects.remove(eye_scene.handle(cubey2))  # an older file, or deleted
assert [i.kind for i in repair.issues(cubey2)] == [repair.NO_EYE_HANDLE]
assert bpy.ops.ballistica.repair() == {'FINISHED'} and eye_scene.handle(cubey2) is not None
eye_scene.handle(cubey2).scale = (1.0, 2.0, 1.0)
eye_scene.handle(cubey2).rotation_euler.x = 0.3
assert [i.kind for i in repair.issues(cubey2)] == [repair.EYE_HANDLE_SKEWED]
assert bpy.ops.ballistica.repair() == {'FINISHED'} and repair.issues(cubey2) == []

cubey_rows = [(r.part, r.side, r.enabled, r.mesh) for r in cubey2.ballistica_character.parts]
cubey2.ballistica_character.parts.clear()  # a file from before the Parts list
assert [i.kind for i in repair.issues(cubey2)] == [repair.NO_PART_ROWS]
draw_panels()
assert bpy.ops.ballistica.repair() == {'FINISHED'} and repair.issues(cubey2) == []
assert [(r.part, r.side, r.enabled, r.mesh) for r in cubey2.ballistica_character.parts] == cubey_rows

# Keep: an Object Mode scale applied to the mesh, so it is exported.
head_part = next(o for o in cubey2.all_objects if o.ballistica_part.role == 'head')
size = head_part.data.vertices[0].co.copy()
head_part.scale = (2.0, 2.0, 2.0)
assert [i.keepable for i in repair.issues(cubey2)] == [True]
assert bpy.ops.ballistica.fix_issue(kind=repair.MOVED, name=head_part.name, keep=True) == {'FINISHED'}
assert tuple(head_part.scale) == (1.0, 1.0, 1.0)
assert (head_part.data.vertices[0].co - size * 2).length < 1e-5
assert repair.issues(cubey2) == []

# Textures list: the body's colour texture and mask, with their settings.
from ballistica_cloud_tools import texture_scene  # noqa: E402

cs = cubey2.ballistica_character
assert [r.field for r in cs.textures] == list(texture_scene.ROWS)
color_row, mask_row = cs.textures
body = cs.body_material
group_node = next(n for n in body.node_tree.nodes if n.type == 'GROUP')
assert color_row.image is not None and group_node.inputs['Color'].links[0].from_node.image == color_row.image
cubey_color = color_row.image
color_row.image = None  # cleared: plain white, not a broken texture
assert not group_node.inputs['Color'].links and texture_scene.fields(cubey2)['color_texture'] == ''
color_row.image = cubey_color
assert group_node.inputs['Color'].links[0].from_node.image == cubey_color
scene.ballistica_active_character = cubey2
cs.active_texture_index = 1
cubey_mask = mask_row.image
assert bpy.ops.ballistica.new_texture_image() == {'FINISHED'}
assert mask_row.image != cubey_mask and mask_row.image.colorspace_settings.name == 'Non-Color'
assert mask_row.image.ballistica_texture.role == 'data'
assert texture_scene.fields(cubey2)['color_mask_texture'] == 'textures/cubey_color_mask_2'  # cubey's own is taken
mask_row.image = cubey_mask
draw_panels()
cubey_color.ballistica_texture.wrap_h = 'repeat'  # build settings go to workspace.json on export
cubey_color.ballistica_texture.alpha = 'no'
assert bpy.ops.ballistica.export_character() == {'FINISHED'}
from ballistica_cloud_tools import jsonfile  # noqa: E402
entries = jsonfile.read(os.path.join(ws, 'workspace.json'))['path']
assert entries['textures/cubey_color.png'] == {'type': 'tex_v1', 'texture_wrapping_h': 'repeat', 'texture_alpha': 'no'}
assert entries['textures/cubey_color_mask.png']['texture_role'] == 'data'
cubey_color.ballistica_texture.wrap_h = 'clamp'
cubey_color.ballistica_texture.alpha = 'auto'
assert bpy.ops.ballistica.export_character() == {'FINISHED'}
assert 'textures/cubey_color.png' not in jsonfile.read(os.path.join(ws, 'workspace.json'))['path']
# An image picked from elsewhere is saved under its export path.
painted = bpy.data.images.new('kid_painting', 32, 32)
painted.generated_color = (1.0, 0.0, 0.0, 1.0)
color_row.image = painted
painted.ballistica_texture.path = 'textures/cubey_red'
assert bpy.ops.ballistica.export_character() == {'FINISHED'}
assert os.path.isfile(os.path.join(ws, 'textures', 'cubey_red.png'))
assert _bchar.Character.load(os.path.join(ws, 'characters', 'cubey.bchar')).get('color_texture') == 'textures/cubey_red'

# Shared meshes and images: who uses them, Make Unique, and duplicate paths.
from ballistica_cloud_tools import sharing  # noqa: E402

pixel_one, pixel_two = bpy.data.collections['pixel'], bpy.data.collections.get('pixel.001')
if pixel_two is None:  # removed earlier: share through a fresh import
	assert bpy.ops.ballistica.import_character(filepath=os.path.join(ws, 'characters', 'pixel.bchar')) == {'FINISHED'}
	pixel_two = bpy.context.scene.ballistica_active_character
p1, p2 = pixel_one.ballistica_character, pixel_two.ballistica_character
torso_index = [(r.part, r.side) for r in p1.parts].index(('torso', 'CENTER'))
shared = p1.parts[torso_index].mesh
assert shared == p2.parts[torso_index].mesh and set(sharing.users(shared)) == {pixel_one, pixel_two}
bpy.context.scene.ballistica_active_character = pixel_two
p2.active_part_index = torso_index
draw_panels()  # the shared note draws
assert bpy.ops.ballistica.make_unique(kind='PART') == {'FINISHED'}
own = p2.parts[torso_index].mesh
assert own != shared and sharing.users(own) == [pixel_two] and sharing.users(shared) == [pixel_one]
assert own.ballistica_asset.path == 'meshes/pixel_torso' or own.ballistica_asset.path.startswith('meshes/pixel_torso_')
assert len(own.vertices) == len(shared.vertices)
p2.active_texture_index = 0
assert bpy.ops.ballistica.make_unique(kind='TEXTURE') == {'FINISHED'}
assert p2.textures[0].image != p1.textures[0].image and tuple(p2.textures[0].image.size) == tuple(p1.textures[0].image.size)
assert not sharing.duplicate_paths(pixel_two)
own.ballistica_asset.path = shared.ballistica_asset.path  # typed the other one's path
assert any('overwrite each other' in p for p in operators.check(pixel_two))

package.unregister()
assert nodegroup.LIBRARY_NAME not in [lib.name for lib in bpy.context.preferences.filepaths.asset_libraries]
shutil.rmtree(os.path.dirname(ws))
print('blender_smoke: OK')
