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

	@unittest.skipUnless(os.path.isdir(SAMPLE), 'ClassicCharacterAssets not cloned next to the addon repo')
	def test_boxes_cover_the_default_spaz(self):
		# The boxes are the neo_spaz bounding boxes, rounded.
		for part, field, _ in rig.PARTS:
			name = {'forearm': 'fore_arm'}.get(part, part)
			mesh = objfile.read(os.path.join(SAMPLE, 'meshes', f'neo_spaz_{name}.obj'))
			lo, hi = template.CUBOIDS[part]
			for axis in range(3):
				self.assertAlmostEqual(min(p[axis] for p in mesh.positions), lo[axis], delta=0.01, msg=part)
				self.assertAlmostEqual(max(p[axis] for p in mesh.positions), hi[axis], delta=0.01, msg=part)


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

		self.assertEqual(pixel(mask, 'torso'), (1.0, 0.0, 0.0))
		self.assertEqual(pixel(mask, 'forearm'), (0.0, 1.0, 0.0))
		self.assertEqual(pixel(mask, 'head'), (0.0, 0.0, 0.0))
		self.assertEqual(pixel(color, 'head'), template.SKIN)

	def test_icon(self):
		pixels, mask = template.icon(16)
		self.assertEqual(len(pixels), 16 * 16 * 4)
		self.assertEqual(len(mask), 16 * 16 * 4)


if __name__ == '__main__':
	unittest.main()
