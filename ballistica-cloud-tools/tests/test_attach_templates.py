import os
import unittest

from _addon import load

attachments = load('attachments')
objfile = load('objfile')
templates = load('attach_templates')


class TemplateTest(unittest.TestCase):
	def test_templates_have_unique_keys(self):
		self.assertEqual(len(templates.TEMPLATES), 12)
		self.assertEqual(len(templates.BY_KEY), len(templates.TEMPLATES))

	def test_hand_items_go_on_the_expected_hands(self):
		sides = {t.key: t.side for t in templates.TEMPLATES if t.target == 'hand'}
		self.assertEqual(sides, {'sword': 'right', 'shield': 'left', 'claws': 'both'})

	def test_records_follow_the_attachment_rules(self):
		for template in templates.TEMPLATES:
			with self.subTest(template.key):
				count = attachments.segment_count(template.kind)
				self.assertEqual(template.segment_count, count)
				record = template.record([f'meshes/x_{i}' for i in range(count)], 'textures/a', 'textures/a_mask')
				self.assertEqual(attachments.problems(record), [])
				self.assertEqual([s['mesh'] for s in record['segments']], [f'meshes/x_{i}' for i in range(count)])

	def test_shipped_meshes_have_uvs_inside_the_texture(self):
		for template in templates.TEMPLATES:
			for path in template.obj_paths():
				with self.subTest(os.path.basename(path)):
					self.assertTrue(os.path.isfile(path), path)
					mesh = objfile.read(path)
					self.assertGreater(len(mesh.faces), 0)
					for face in mesh.faces:  # no zero-area faces (Blender can crash on them)
						self.assertEqual(len({mesh.positions[c[0]] for c in face}), 3)
					self.assertTrue(all(c[1] is not None and c[2] is not None for face in mesh.faces for c in face))
					self.assertIsNone(objfile.uv_range_problem([c for uv in mesh.uvs for c in uv]))
					for axis in range(3):  # small: an attachment, not a body
						values = [p[axis] for p in mesh.positions]
						self.assertLess(max(values) - min(values), 0.8)

	def test_the_atlas_ships_with_its_mask(self):
		for mask in (False, True):
			self.assertTrue(os.path.isfile(templates.texture_path(mask)))
		names = {os.path.splitext(f)[0] for f in os.listdir(templates.TEMPLATE_DIR) if f.endswith('.obj')}
		expected = {os.path.splitext(os.path.basename(p))[0] for t in templates.TEMPLATES for p in t.obj_paths()}
		self.assertEqual(names, expected)  # no leftovers

	def test_the_atlas_is_a_multiple_of_8(self):
		import struct

		for mask in (False, True):
			with open(templates.texture_path(mask), 'rb') as infile:
				width, height = struct.unpack('>II', infile.read(24)[16:24])
			self.assertEqual((width % 8, height % 8), (0, 0), (width, height))
