import os
import unittest

from _addon import load

template = load('template')
objfile = load('objfile')
rig = load('rig')

SAMPLE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ClassicCharacterAssets')


def _sub(a, b):
	return [x - y for x, y in zip(a, b)]


def _cross(a, b):
	return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class CuboidTest(unittest.TestCase):
	def test_every_part_has_a_box_and_cell(self):
		parts = [p for p, _, _ in rig.PARTS]
		self.assertEqual(sorted(template.CUBOIDS), sorted(parts))
		self.assertEqual(sorted(template.CELLS), sorted(parts))
		self.assertEqual(len(set(template.CELLS.values())), len(parts))

	def test_box_matches_extents(self):
		for part, (lo, hi) in template.CUBOIDS.items():
			mesh = template.cuboid(part)
			self.assertEqual(len(mesh.faces), 12)
			for axis in range(3):
				self.assertAlmostEqual(min(p[axis] for p in mesh.positions), lo[axis])
				self.assertAlmostEqual(max(p[axis] for p in mesh.positions), hi[axis])

	def test_triangles_face_outward(self):
		for part in template.CUBOIDS:
			mesh = template.cuboid(part)
			for face in mesh.faces:
				a, b, c = (mesh.positions[v] for v, _, _ in face)
				normal = mesh.normals[face[0][2]]
				winding = _cross(_sub(b, a), _sub(c, a))
				self.assertGreater(sum(w * n for w, n in zip(winding, normal)), 0, part)

	def test_uvs_stay_in_the_parts_cell(self):
		for part in template.CUBOIDS:
			for u, v in template.cuboid(part).uvs:
				self.assertEqual(template.part_at(u, v), part)

	def test_limbs_span_their_joints_and_are_long(self):
		spans = {
			'upper_arm': (rig.SHOULDER_ON_UPPER_ARM[2], rig.ELBOW_ON_UPPER_ARM[2]),
			'forearm': (rig.ELBOW_ON_LOWER_ARM[2], rig.HAND_OFFSET),
			'upper_leg': (rig.HIP_ON_UPPER_LEG[2], rig.KNEE_ON_UPPER_LEG[2]),
			'lower_leg': (rig.KNEE_ON_LOWER_LEG[2], rig.ANKLE_ON_LOWER_LEG[2]),
		}
		for part, (start, end) in spans.items():
			lo, hi = template.CUBOIDS[part]
			self.assertLess(lo[2], start, part)
			self.assertGreater(hi[2], end, part)
			length = hi[2] - lo[2]
			self.assertGreater(length, 1.4 * (hi[0] - lo[0]), f'{part} should be long and slim')

	@unittest.skipUnless(os.path.isdir(SAMPLE), 'ClassicCharacterAssets not cloned next to the addon repo')
	def test_limb_lengths_match_the_default_spaz(self):
		for part in ('upper_arm', 'forearm', 'upper_leg', 'lower_leg'):
			name = {'forearm': 'fore_arm'}.get(part, part)
			mesh = objfile.read(os.path.join(SAMPLE, 'meshes', f'neo_spaz_{name}.obj'))
			zs = [p[2] for p in mesh.positions]
			lo, hi = template.CUBOIDS[part]
			self.assertAlmostEqual(hi[2] - lo[2], max(zs) - min(zs), delta=0.06, msg=part)

	def test_parts_are_slimmer_than_the_armoured_spaz(self):
		# The default Spaz's bounding boxes include armour; the template's
		# limbs should be thinner than that.
		self.assertLess(template.CUBOIDS['upper_arm'][1][0] - template.CUBOIDS['upper_arm'][0][0], 0.229)
		self.assertLess(template.CUBOIDS['lower_leg'][1][0] - template.CUBOIDS['lower_leg'][0][0], 0.168)

	def test_head_sits_in_the_head_ball_with_eyes_on_its_face(self):
		lo, hi = template.CUBOIDS['head']
		corner = sum(c * c for c in hi) ** 0.5
		self.assertLess(max(hi), rig.HEAD_RADIUS)  # faces inside the ball
		self.assertGreater(corner, rig.HEAD_RADIUS)  # corners poke out, cube-like
		self.assertAlmostEqual(hi[2], rig.DEFAULTS['eye_offset'][2], delta=0.01)  # eyes at the face


class TextureTest(unittest.TestCase):
	def test_atlas_and_mask(self):
		size = 30
		color, mask = template.textures(size)
		self.assertEqual(len(color), size * size * 4)

		def pixel(data, part):
			col, row = template.CELLS[part]
			x = int((col + 0.5) / template.GRID * size)
			y = int((row + 0.5) / template.GRID * size)
			i = (y * size + x) * 4
			return tuple(data[i:i + 3])

		self.assertEqual(pixel(mask, 'pelvis'), (1.0, 0.0, 0.0))  # shorts
		self.assertEqual(pixel(mask, 'hand'), (0.0, 1.0, 0.0))  # gloves
		self.assertEqual(pixel(mask, 'toes'), (0.0, 1.0, 0.0))  # shoes
		for part in ('head', 'torso', 'upper_arm', 'forearm', 'upper_leg', 'lower_leg'):
			self.assertEqual(pixel(mask, part), (0.0, 0.0, 0.0), part)
		for part in template.CELLS:
			self.assertEqual(pixel(color, part), (1.0, 1.0, 1.0), part)  # all white

	def test_icon(self):
		pixels, mask = template.icon(16)
		self.assertEqual(len(pixels), 16 * 16 * 4)
		self.assertEqual(len(mask), 16 * 16 * 4)


class ShippedTemplateTest(unittest.TestCase):
	"""assets/template/ is what New Character loads; it must match template.py."""

	def test_objs_match_the_generator(self):
		for part in template.CUBOIDS:
			shipped = objfile.read(template.obj_path(part))
			made = template.cuboid(part)
			corners = lambda mesh: sorted(tuple(round(c, 5) for c in mesh.positions[v]) for face in mesh.faces for v, _, _ in face)
			self.assertEqual(corners(shipped), corners(made), f'{part}: run make template')

	def test_textures_exist(self):
		for name in template.TEXTURES:
			self.assertTrue(os.path.isfile(template.texture_path(name)), name)


if __name__ == '__main__':
	unittest.main()
