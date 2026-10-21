import json
import os
import unittest

from _addon import load

attachments = load('attachments')
rig = load('rig')

SAMPLE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ClassicCharacterAssets')
ZOE_HAIR = {
	'damping': 0.7, 'kind': 'antenna', 'radius': 0.375,
	'segments': [{'mesh': 'meshes/hair_tuft1', 'transform': {'translate': [0.02, 0.16, 0.05]}}],
	'stiffness': 0.2, 'target': 'head',
	'transform': {'rotate': [48.427, 28.318, 12.945], 'translate': [-0.173, 0.124, 0.153]},
}


class RoundTripTest(unittest.TestCase):
	def test_untouched_attachment_is_unchanged(self):
		record = attachments.from_json(ZOE_HAIR)
		self.assertEqual(attachments.to_json(record, ZOE_HAIR), ZOE_HAIR)

	def test_defaults_are_filled_in(self):
		record = attachments.from_json(ZOE_HAIR)
		self.assertEqual(record['side'], 'both')
		self.assertEqual(record['drag'], 0.5)
		self.assertEqual(record['segments'][0]['rotate'], (0.0, 0.0, 0.0))
		self.assertEqual(record['segments'][0]['scale'], (1.0, 1.0, 1.0))

	def test_edits_are_written_and_unknown_keys_kept(self):
		raw = dict(ZOE_HAIR, future_key={'x': 1})
		record = attachments.from_json(raw)
		record['drag'] = 0.25
		record['translate'] = (0.0, 0.2, 0.30000001192092896)
		record['segments'][0]['texture'] = 'textures/hair'
		out = attachments.to_json(record, raw)
		self.assertEqual(out['drag'], 0.25)
		self.assertEqual(out['transform']['translate'], [0.0, 0.2, 0.3])
		self.assertEqual(out['transform']['rotate'], [48.427, 28.318, 12.945])
		self.assertEqual(out['segments'][0]['texture'], 'textures/hair')
		self.assertEqual(out['future_key'], {'x': 1})

	def test_float32_noise_is_removed(self):
		import array
		record = attachments.from_json(ZOE_HAIR)
		record['rotate'] = tuple(array.array('f', record['rotate']))  # as Blender stores it
		self.assertEqual(attachments.to_json(record, ZOE_HAIR), ZOE_HAIR)

	def test_new_attachment_writes_only_whats_needed(self):
		record = attachments.new_attachment(mesh='meshes/x')
		self.assertEqual(attachments.to_json(record), {'target': 'head', 'kind': 'antenna', 'segments': [{'mesh': 'meshes/x'}]})

	def test_cleared_refs_and_transforms_disappear(self):
		raw = {'target': 'head', 'kind': 'static', 'segments': [{'mesh': 'm', 'texture': 't', 'transform': {'translate': [1, 0, 0]}}]}
		record = attachments.from_json(raw)
		record['segments'][0]['texture'] = ''
		record['segments'][0]['translate'] = (0.0, 0.0, 0.0)
		self.assertEqual(attachments.to_json(record, raw)['segments'][0], {'mesh': 'm', 'transform': {'translate': [0.0, 0.0, 0.0]}})

	@unittest.skipUnless(os.path.isdir(SAMPLE), 'ClassicCharacterAssets not cloned next to the addon repo')
	def test_classic_attachments_round_trip(self):
		count = 0
		for name in sorted(os.listdir(os.path.join(SAMPLE, 'characters'))):
			with open(os.path.join(SAMPLE, 'characters', name)) as f:
				data = json.load(f)['data']
			for raw in data.get('attachments', []):
				self.assertEqual(attachments.to_json(attachments.from_json(raw), raw), raw, name)
				self.assertEqual(attachments.problems(attachments.from_json(raw)), [], name)
				count += 1
		self.assertGreaterEqual(count, 4)  # Zoe's three, Pixel's wing (more if the sample was edited)


class RulesTest(unittest.TestCase):
	def test_allowed_options(self):
		self.assertEqual(attachments.allowed_sides('head'), ('both',))
		self.assertEqual(attachments.allowed_sides('hand'), ('both', 'right', 'left'))
		self.assertEqual(attachments.allowed_kinds('wing'), ('static',))
		self.assertIn('antenna_4', attachments.allowed_kinds('torso'))

	def test_problems(self):
		record = attachments.new_attachment('hand', 'antenna_2', 'm')
		found = attachments.problems(record)
		self.assertTrue(any("kind 'antenna_2'" in p for p in found), found)
		record = attachments.new_attachment('head', 'antenna_2', 'm')
		record['side'] = 'left'
		record['segments'].pop()
		found = attachments.problems(record)
		self.assertTrue(any("side 'left'" in p for p in found), found)
		self.assertTrue(any('needs 2 segment' in p for p in found), found)

	def test_fix_makes_records_valid(self):
		record = attachments.new_attachment('head', 'antenna_3', 'm')
		record['target'] = 'hand'
		record['side'] = 'right'
		attachments.fix(record)
		self.assertEqual((record['kind'], record['side'], len(record['segments'])), ('static', 'right', 1))
		self.assertEqual(attachments.problems(record), [])
		record['target'] = 'head'
		record['kind'] = 'antenna_4'
		attachments.fix(record)
		self.assertEqual((record['side'], len(record['segments'])), ('both', 4))
		self.assertEqual(record['segments'][3]['mesh'], 'm')  # new segments reuse the last mesh


if __name__ == '__main__':
	unittest.main()
