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
from ballistica_cloud_tools import objfile, operators  # noqa: E402

ws = os.path.join(tempfile.mkdtemp(), 'ws')
shutil.copytree(SAMPLE, ws, ignore=shutil.ignore_patterns('.git'))


def snapshot():
	out = {}
	for base, _, files in os.walk(ws):
		for name in files:
			path = os.path.join(base, name)
			with open(path, 'rb') as infile:
				out[os.path.relpath(path, ws)] = hashlib.sha1(infile.read()).hexdigest()
	return out


before = snapshot()
for name, attachments in (('agent_johnson', 0), ('zoe', 4), ('pixel', 2)):
	assert bpy.ops.ballistica.import_character(filepath=os.path.join(ws, 'characters', f'{name}.bchar')) == {'FINISHED'}
	collection = bpy.data.collections[name]
	found = [o for o in collection.all_objects if o.ballistica_part.role == 'attachment']
	assert all(o.users_collection[0].name == f'{name} Attachments' for o in found)
	assert len(found) == attachments, (name, [o.name for o in found])
	assert operators.check(collection) == [], operators.check(collection)

# Colorize: the bundled asset group, driven by the collection's tints.
from ballistica_cloud_tools import nodegroup  # noqa: E402

libraries = [lib.name for lib in bpy.context.preferences.filepaths.asset_libraries]
assert nodegroup.LIBRARY_NAME in libraries, libraries
group = bpy.data.node_groups[nodegroup.GROUP_NAME]
assert group.asset_data is not None, 'node group should stay marked as an asset'
assert [s.name for s in group.interface.items_tree if s.in_out == 'INPUT'] == [n for n, _ in nodegroup.INPUTS]
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
bpy.context.view_layer.objects.active = head
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

# Parts start with identity transforms; moving one and resetting puts it back.
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
bpy.context.view_layer.objects.active = legs[0]
bpy.context.view_layer.update()
assert bpy.ops.ballistica.reset_parts() == {'FINISHED'}
bpy.context.view_layer.update()
for o in legs:
	assert all(abs(a - b) < 1e-6 for ra, rb in zip(o.matrix_world, home[o.name]) for a, b in zip(ra, rb)), o.name
assert tuple(arm.pose.bones['upper_leg.R'].rotation_quaternion) == (1.0, 0.0, 0.0, 0.0)
assert tuple(arm.location) == (0.0, 0.0, 0.0)
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

# Frame Character: the rig is framable while only its Rig toggle hides it,
# not when hidden any other way (headless Blender can't run View Selected).
ctx = SimpleNamespace(view_layer=bpy.context.view_layer)
assert operators._framable_rig(ctx, agent) is not None  # Rig collection hidden by its toggle: fine
arm.hide_set(True)
assert operators._framable_rig(ctx, agent) is None
arm.hide_set(False)
agent_layer = next(_layer_collections(bpy.context.view_layer.layer_collection, agent))
agent_layer.hide_viewport = True
assert operators._framable_rig(ctx, agent) is None  # a parent collection hidden
agent_layer.hide_viewport = False

# A missing assets file must fail the import loudly, building nothing.
real = nodegroup.ASSETS_BLEND
nodegroup.ASSETS_BLEND = real + '.missing'
bpy.data.node_groups.remove(bpy.data.node_groups[nodegroup.GROUP_NAME])
count = len(bpy.data.collections)
try:
	bpy.ops.ballistica.import_character(filepath=os.path.join(ws, 'characters', 'spaz.bchar'))
	raise AssertionError('import should have failed')
except RuntimeError as exc:
	assert 'Bundled asset file not found' in str(exc), exc
assert len(bpy.data.collections) == count
nodegroup.ASSETS_BLEND = real

package.unregister()
assert nodegroup.LIBRARY_NAME not in [lib.name for lib in bpy.context.preferences.filepaths.asset_libraries]
shutil.rmtree(os.path.dirname(ws))
print('blender_smoke: OK')
