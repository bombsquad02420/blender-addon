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
settings.shoulder_offset = (0.03, -0.02, 0.01)
settings.eye_offset = (0.07, -0.03, 0.2)
bpy.context.view_layer.update()


def moved(bone):
	return tuple(round(c, 4) for c in game_head(bone) - base[bone])


assert moved('upper_arm.R') == (0.03, -0.02, 0.01), moved('upper_arm.R')
assert moved('upper_arm.L') == (-0.03, -0.02, 0.01), moved('upper_arm.L')
assert moved('eye_offset.L') == (0.07, -0.03, 0.2), moved('eye_offset.L')
assert moved('eye_offset.R') == (-0.07, -0.03, 0.2), moved('eye_offset.R')
# The eye stand-in sits at head centre + eye_offset (Zoe has visible eyes).
zoe = bpy.data.collections['zoe']
zoe.ballistica_character.eye_offset = (0.07, -0.03, 0.2)
bpy.context.view_layer.update()
zoe_arm = next(o for o in zoe.all_objects if o.type == 'ARMATURE')
eye_obj = next(o for o in bpy.data.collections['zoe Eyes'].objects if o.ballistica_part.role == 'eye' and o.ballistica_part.side == 'L')
head_centre = scene.TO_GAME @ (zoe_arm.matrix_world @ zoe_arm.pose.bones['head'].tail)
offset = tuple(round(c, 4) for c in (scene.TO_GAME @ eye_obj.matrix_world.translation) - head_centre)
assert offset == (0.07, -0.03, 0.2), offset
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
assert dims(eye_obj)[0] == round(0.09 * 1.78 * 1.5, 3), dims(eye_obj)
eyes = [o for o in bpy.data.collections['zoe Eyes'].objects]
assert len({o.data.name for o in eyes}) == 1, [o.data.name for o in eyes]  # one shared mesh
right = next(o for o in eyes if o.ballistica_part.side == 'R')
assert tuple(round(v, 3) for v in right.scale) == (-1.5, 1.5, 1.5), tuple(right.scale)

bpy.ops.ballistica.export_character()
import json  # noqa: E402
saved = json.load(open(os.path.join(ws, 'characters', 'agent_johnson.bchar')))['data']
assert saved['shoulder_offset'] == [0.03, -0.02, 0.01], saved.get('shoulder_offset')
assert saved['eye_offset'] == [0.07, -0.03, 0.2], saved.get('eye_offset')

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
