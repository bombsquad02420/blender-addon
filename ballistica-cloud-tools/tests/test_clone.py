import os
import unittest

from _addon import load

bchar = load('bchar')
clone = load('clone')

SAMPLE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ClassicCharacterAssets')


class PlanTest(unittest.TestCase):
	def test_every_file_gets_a_new_path_and_settings_are_kept(self):
		source = bchar.Character({'data': {
			'type': 'basic_spaz', 'name': 'strings/characters/zoe',
			'color_texture': 'textures/zoe_color', 'color_mask_texture': 'textures/zoe_color_mask',
			'icon_texture': 'textures/zoe_icon', 'icon_mask_texture': 'textures/zoe_icon_color_mask',
			'head_mesh': 'meshes/zoe_head', 'torso_mesh': 'meshes/shared', 'pelvis_mesh': 'meshes/shared',
			'left_toes_mesh': 'meshes/zoe_left_toes', 'color': [0.1, 0.2, 0.3],
			'jump_sounds': ['audio/zoe1'], 'highlight_name': 'strings/hair',
			'attachments': [
				{'target': 'head', 'kind': 'antenna_2', 'segments': [{'mesh': 'meshes/tuft3'}, {'mesh': 'meshes/tuft4'}]},
				{'target': 'wing', 'kind': 'static', 'segments': [
					{'mesh': 'meshes/wing', 'texture': 'textures/wings', 'mask_texture': 'textures/wings_mask'}]},
			],
		}})
		new, meshes, textures = clone.plan(source, 'robo')
		d = new.data
		self.assertEqual(d['name'], 'strings/characters/robo')
		self.assertEqual(d['head_mesh'], 'meshes/robo_head')
		self.assertEqual(d['torso_mesh'], 'meshes/robo_torso')
		self.assertEqual(d['pelvis_mesh'], 'meshes/robo_torso')  # shared file stays shared
		self.assertEqual(d['left_toes_mesh'], 'meshes/robo_left_toes')
		self.assertEqual(d['color_mask_texture'], 'textures/robo_color_mask')
		self.assertEqual(d['icon_mask_texture'], 'textures/robo_icon_color_mask')
		self.assertEqual([s['mesh'] for s in d['attachments'][0]['segments']], ['meshes/robo_attachment0_0', 'meshes/robo_attachment0_1'])
		self.assertEqual(d['attachments'][1]['segments'][0], {
			'mesh': 'meshes/robo_attachment1', 'texture': 'textures/robo_attachment1', 'mask_texture': 'textures/robo_attachment1_mask'})
		self.assertEqual(d['color'], [0.1, 0.2, 0.3])
		self.assertEqual(d['jump_sounds'], ['audio/zoe1'])  # sounds aren't copied
		self.assertEqual(d['highlight_name'], 'strings/hair')
		self.assertEqual(meshes['meshes/shared'], 'meshes/robo_torso')
		self.assertEqual(textures['textures/wings_mask'], 'textures/robo_attachment1_mask')
		self.assertEqual(clone.mask_textures(new), {
			'textures/robo_color_mask', 'textures/robo_icon_color_mask', 'textures/robo_attachment1_mask'})
		self.assertEqual(source.data['head_mesh'], 'meshes/zoe_head')  # source untouched

	@unittest.skipUnless(os.path.isdir(SAMPLE), 'ClassicCharacterAssets not cloned next to the addon repo')
	def test_classic_characters_copy_cleanly(self):
		for name in sorted(os.listdir(os.path.join(SAMPLE, 'characters'))):
			source = bchar.Character.load(os.path.join(SAMPLE, 'characters', name))
			new, meshes, textures = clone.plan(source, 'copy')
			for field, kind, logical in new.referenced_assets():
				if kind in ('mesh', 'texture'):
					self.assertIn('/copy_', logical, f'{name}: {field}')
			self.assertEqual(set(meshes), {l for _, k, l in source.referenced_assets() if k == 'mesh'}, name)
			self.assertEqual(set(textures), {l for _, k, l in source.referenced_assets() if k == 'texture'}, name)


if __name__ == '__main__':
	unittest.main()
