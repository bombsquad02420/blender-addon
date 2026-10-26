import unittest

from _addon import load

attachments = load('attachments')
objfile = load('objfile')
templates = load('attach_templates')


class TemplateTest(unittest.TestCase):
	def test_templates_have_unique_keys(self):
		self.assertEqual(len(templates.TEMPLATES), 13)
		self.assertEqual(len(templates.BY_KEY), len(templates.TEMPLATES))

	def test_hand_items_go_on_the_expected_hands(self):
		sides = {t.key: t.side for t in templates.TEMPLATES if t.target == 'hand'}
		self.assertEqual(sides, {'sword': 'right', 'shield': 'left', 'claws': 'both'})

	def test_records_follow_the_attachment_rules(self):
		for template in templates.TEMPLATES:
			with self.subTest(template.key):
				count = attachments.segment_count(template.kind)
				self.assertEqual(len(template.segments), count)
				record = template.record([f'meshes/x_{i}' for i in range(count)])
				self.assertEqual(attachments.problems(record), [])
				self.assertEqual([s['mesh'] for s in record['segments']], [f'meshes/x_{i}' for i in range(count)])

	def test_meshes_are_closed_triangles_with_uvs_inside_the_texture(self):
		for template in templates.TEMPLATES:
			for index, make in enumerate(template.segments):
				with self.subTest(template.key, segment=index):
					mesh = make()
					self.assertGreater(len(mesh.faces), 4)
					self.assertTrue(all(len(face) == 3 for face in mesh.faces))
					self.assertIsNone(objfile.uv_range_problem([c for uv in mesh.uvs for c in uv]))
					for normal in mesh.normals:
						self.assertAlmostEqual(sum(c * c for c in normal), 1.0, places=5)
					# Small: an attachment, not a body.
					for axis in range(3):
						values = [p[axis] for p in mesh.positions]
						self.assertLess(max(values) - min(values), 0.7)

	def test_textures_are_flat_color_and_one_mask_channel(self):
		size = 4
		for template in templates.TEMPLATES:
			with self.subTest(template.key):
				color, mask = template.textures(size)
				self.assertEqual(len(color), size * size * 4)
				self.assertEqual(color[:4], list(template.color) + [1.0])
				channels = mask[:3]
				self.assertEqual(sum(channels), 0.0 if template.tint is None else 1.0)
