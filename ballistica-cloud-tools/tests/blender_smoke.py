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
	found = [o for o in collection.objects if o.ballistica_part.role == 'attachment']
	assert len(found) == attachments, (name, [o.name for o in found])
	assert operators.check(collection) == [], operators.check(collection)

# Colorize: the bundled asset group, driven by the collection's tints.
from ballistica_cloud_tools import nodegroup  # noqa: E402

libraries = [lib.name for lib in bpy.context.preferences.filepaths.asset_libraries]
assert nodegroup.LIBRARY_NAME in libraries, libraries
group = bpy.data.node_groups[nodegroup.GROUP_NAME]
assert group.asset_data is not None, 'node group should stay marked as an asset'
assert [s.name for s in group.interface.items_tree if s.in_out == 'INPUT'] == [n for n, _ in nodegroup.INPUTS]
agent = bpy.data.collections['agent_johnson']
material = bpy.data.materials['agent_johnson']
node = next(n for n in material.node_tree.nodes if n.type == 'GROUP')
agent.ballistica_character.highlight = (0.25, 0.5, 0.75)
bpy.context.view_layer.update()
value = tuple(round(v, 4) for v in node.inputs['Highlight 2'].default_value[:3])
assert value == (0.25, 0.5, 0.75), value
agent.ballistica_character.highlight = (1.0, 0.5, 0.3)  # back to the file's value

head = next(o for o in agent.objects if o.name == 'head')
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

package.unregister()
assert nodegroup.LIBRARY_NAME not in [lib.name for lib in bpy.context.preferences.filepaths.asset_libraries]
shutil.rmtree(os.path.dirname(ws))
print('blender_smoke: OK')
