import json
import math
import os
import shutil
import tempfile
import unittest

from _addon import load

bchar = load('bchar')
jsonfile = load('jsonfile')
transforms = load('transforms')
workspace = load('workspace')

SAMPLE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ClassicCharacterAssets')


def _mul(a, b):
	return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _apply(m, v):
	return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


class TempWorkspace(unittest.TestCase):
	def setUp(self):
		self.root = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, self.root)
		with open(os.path.join(self.root, 'workspace.json'), 'w') as f:
			f.write(jsonfile.dumps({'path': {'textures/a_mask.png': {'type': 'tex_v1', 'texture_role': 'data'}}, 'type': 'assets_v1'}, False))
		for rel in ('meshes/a_head.obj', 'textures/a_color.png', 'textures/a_mask.png', 'audio/a1.wav', 'strings/characters/a.bstr', 'characters/a.bchar'):
			path = os.path.join(self.root, *rel.split('/'))
			os.makedirs(os.path.dirname(path), exist_ok=True)
			open(path, 'w').close()


class WorkspaceTest(TempWorkspace):
	def test_find_root_from_nested_file(self):
		self.assertEqual(workspace.find_root(os.path.join(self.root, 'characters', 'a.bchar')), self.root)
		self.assertIsNone(workspace.find_root(tempfile.gettempdir()))

	def test_lists_assets_by_kind_and_ignores_strings(self):
		self.assertEqual(workspace.list_assets(self.root, 'texture'), ['textures/a_color', 'textures/a_mask'])
		self.assertEqual(workspace.list_assets(self.root, 'mesh'), ['meshes/a_head'])
		self.assertEqual(workspace.list_assets(self.root, 'sound'), ['audio/a1'])
		self.assertNotIn('strings/characters/a', workspace.list_assets(self.root, 'character'))

	def test_file_path_resolves_logical_paths(self):
		self.assertTrue(workspace.file_path(self.root, 'meshes/a_head', 'mesh').endswith('a_head.obj'))
		self.assertIsNone(workspace.file_path(self.root, 'meshes/missing', 'mesh'))

	def test_texture_settings_default_unless_listed(self):
		mask = os.path.join(self.root, 'textures', 'a_mask.png')
		color = os.path.join(self.root, 'textures', 'a_color.png')
		self.assertEqual(workspace.texture_settings(self.root, mask)['texture_role'], 'data')
		self.assertEqual(workspace.texture_settings(self.root, color), {
			'texture_role': 'default', 'texture_quality': 'default',
			'texture_wrapping_h': 'clamp', 'texture_wrapping_v': 'clamp', 'texture_alpha': 'auto'})

	def test_set_texture_settings_keeps_other_keys_and_drops_defaults(self):
		mask = os.path.join(self.root, 'textures', 'a_mask.png')
		color = os.path.join(self.root, 'textures', 'a_color.png')
		self.assertTrue(workspace.set_texture_settings(self.root, {
			color: {'texture_wrapping_h': 'repeat', 'texture_quality': 'default'},
			mask: {'texture_role': 'data', 'texture_alpha': 'no'},
		}))
		entries = jsonfile.read(os.path.join(self.root, 'workspace.json'))['path']
		self.assertEqual(entries['textures/a_color.png'], {'type': 'tex_v1', 'texture_wrapping_h': 'repeat'})
		self.assertEqual(entries['textures/a_mask.png'], {'type': 'tex_v1', 'texture_role': 'data', 'texture_alpha': 'no'})
		# Back to defaults: the color texture's entry goes; nothing else is touched.
		self.assertTrue(workspace.set_texture_settings(self.root, {color: {'texture_wrapping_h': 'clamp'}}))
		entries = jsonfile.read(os.path.join(self.root, 'workspace.json'))['path']
		self.assertNotIn('textures/a_color.png', entries)
		self.assertIn('textures/a_mask.png', entries)
		self.assertFalse(workspace.set_texture_settings(self.root, {color: {'texture_wrapping_h': 'clamp'}}))

	def test_mark_data_textures_only_adds_missing_roles(self):
		color = os.path.join(self.root, 'textures', 'a_color.png')
		mask = os.path.join(self.root, 'textures', 'a_mask.png')
		with open(os.path.join(self.root, 'workspace.json')) as f:
			before = f.read()
		self.assertFalse(workspace.mark_data_textures(self.root, [mask]))
		with open(os.path.join(self.root, 'workspace.json')) as f:
			self.assertEqual(f.read(), before)
		self.assertTrue(workspace.mark_data_textures(self.root, [color]))
		self.assertEqual(workspace.texture_role(self.root, color), 'data')
		with open(os.path.join(self.root, 'workspace.json')) as f:
			self.assertFalse(f.read().endswith('\n'))  # kept as found


class CharacterTest(unittest.TestCase):
	def test_set_follows_web_ui_rules(self):
		c = bchar.Character()
		c.set('torso_radius', 0.15)  # default, absent: not written
		self.assertNotIn('torso_radius', c.data)
		c.set('torso_radius', 0.2)
		self.assertEqual(c.data['torso_radius'], 0.2)
		c.set('torso_radius', 0.15)  # present: kept even at default
		self.assertEqual(c.data['torso_radius'], 0.15)
		c.set('forearm_mesh', 'meshes/x')
		c.set('forearm_mesh', '')
		self.assertNotIn('forearm_mesh', c.data)
		c.set('color', (0.30000001192092896, 0.5, 1))
		self.assertEqual(c.data['color'], [0.3, 0.5, 1])

	def test_unknown_fields_survive(self):
		c = bchar.Character({'data': {'type': 'basic_spaz', 'highlight_team_coloring_strength': 0.4, 'future': {'x': 1}}, 'extra': True})
		c.set('color', [1, 1, 1])
		self.assertEqual(c.data['highlight_team_coloring_strength'], 0.4)
		self.assertEqual(c.data['future'], {'x': 1})
		self.assertTrue(c.raw['extra'])

	def test_rejects_non_character(self):
		with self.assertRaises(ValueError):
			bchar.Character({'path': {}})

	@unittest.skipUnless(os.path.isdir(SAMPLE), 'ClassicCharacterAssets not cloned next to the addon repo')
	def test_classic_characters_round_trip_byte_for_byte(self):
		chars = os.path.join(SAMPLE, 'characters')
		tmp = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, tmp)
		for name in sorted(os.listdir(chars)):
			src = os.path.join(chars, name)
			dst = os.path.join(tmp, name)
			shutil.copy(src, dst)
			c = bchar.Character.load(dst)
			for field in list(c.data):
				c.set(field, c.data[field])
			self.assertFalse(c.save(dst), name)
			with open(src) as a, open(dst) as b:
				self.assertEqual(a.read(), b.read(), name)

	@unittest.skipUnless(os.path.isdir(SAMPLE), 'ClassicCharacterAssets not cloned next to the addon repo')
	def test_classic_references_resolve(self):
		for name in os.listdir(os.path.join(SAMPLE, 'characters')):
			c = bchar.Character.load(os.path.join(SAMPLE, 'characters', name))
			for field, kind, logical in c.referenced_assets():
				self.assertIsNotNone(workspace.file_path(SAMPLE, logical, kind), f'{name}: {field} -> {logical}')


class TransformTest(unittest.TestCase):
	def test_vectors_round_trip(self):
		v = (0.1, 0.2, 0.3)
		self.assertEqual(transforms.vec_to_blender(v), (0.1, -0.3, 0.2))
		self.assertEqual(transforms.vec_to_game(transforms.vec_to_blender(v)), v)

	def test_rotate_round_trip(self):
		for rotate in ([48.427, 28.318, 12.945], [-180.0, 63.025, 0.0], [0, 0, 0]):
			back = transforms.blender_euler_to_rotate(transforms.rotate_to_blender_euler(rotate))
			for a, b in zip(rotate, back):
				self.assertAlmostEqual(a, b, places=3)

	def _nose_and_top(self, rotate):
		"""Where the part's nose (+Z) and top (+Y) end up, in game axes."""
		m = transforms.euler_to_matrix(transforms.rotate_to_blender_euler(rotate))
		to_game = lambda v: transforms.vec_to_game(v)
		nose = to_game(_apply(m, transforms.vec_to_blender((0, 0, 1))))
		top = to_game(_apply(m, transforms.vec_to_blender((0, 1, 0))))
		return nose, top

	def test_heading_turns_nose_to_characters_right(self):
		nose, _ = self._nose_and_top([30, 0, 0])
		self.assertLess(nose[0], -0.4)  # right is -X

	def test_pitch_raises_nose(self):
		nose, _ = self._nose_and_top([0, 30, 0])
		self.assertGreater(nose[1], 0.4)

	def test_roll_is_clockwise_from_behind(self):
		# From behind, the character's right (-X) is the viewer's right, so
		# clockwise tips the top toward -X.
		_, top = self._nose_and_top([0, 0, 30])
		self.assertLess(top[0], -0.4)


if __name__ == '__main__':
	unittest.main()
