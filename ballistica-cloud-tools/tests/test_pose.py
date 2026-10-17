import math
import os
import tempfile
import unittest

from _addon import load

pose = load('pose')
rig = load('rig')
objfile = load('objfile')

SAMPLE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ClassicCharacterAssets')


def close(a, b, tol=1e-9):
	return all(abs(x - y) < tol for x, y in zip(a, b))


class PoseTest(unittest.TestCase):
	def setUp(self):
		self.placements, self.joints = pose.compute()

	def test_joints_meet(self):
		p, j = self.placements, self.joints
		self.assertTrue(close(p['upper_arm'].point(rig.SHOULDER_ON_UPPER_ARM), j['shoulder']))
		self.assertTrue(close(p['forearm'].point(rig.ELBOW_ON_LOWER_ARM), j['elbow']))
		self.assertTrue(close(p['upper_leg'].point(rig.HIP_ON_UPPER_LEG), j['hip']))
		self.assertTrue(close(p['lower_leg'].point(rig.KNEE_ON_LOWER_LEG), p['upper_leg'].point(rig.KNEE_ON_UPPER_LEG)))
		self.assertTrue(close(p['toes'].point(rig.ANKLE_ON_TOES), j['ankle']))

	def test_shape(self):
		j = self.joints
		self.assertLess(j['shoulder'][0], 0)  # right side is -X
		self.assertLess(j['elbow'][0], j['shoulder'][0])  # arm goes out
		self.assertLess(j['elbow'][1], j['shoulder'][1])  # and a little down
		self.assertAlmostEqual(j['knee'][0], j['hip'][0])  # leg straight down
		self.assertLess(j['ankle'][1], j['knee'][1])
		self.assertGreater(j['toe_tip'][2], j['ankle'][2])  # toes point forward
		self.assertGreater(j['head'][1], j['neck'][1])
		self.assertAlmostEqual(self.placements['toes'].location[1], rig.TOES_RADIUS)  # feet on the ground

	def test_rotations_are_orthonormal(self):
		for name, placement in self.placements.items():
			m = placement.rotation
			for i in range(3):
				col = [m[r][i] for r in range(3)]
				self.assertAlmostEqual(sum(c * c for c in col), 1.0, msg=name)

	def test_shoulder_offset_moves_shoulder(self):
		_, joints = pose.compute(shoulder_offset=(0.03, 0.0, -0.02))
		self.assertAlmostEqual(joints['shoulder'][0] - self.joints['shoulder'][0], 0.03)


class ObjTest(unittest.TestCase):
	@unittest.skipUnless(os.path.isdir(SAMPLE), 'ClassicCharacterAssets not cloned next to the addon repo')
	def test_round_trip_keeps_geometry(self):
		src = os.path.join(SAMPLE, 'meshes', 'agent_head.obj')
		mesh = objfile.read(src)
		self.assertEqual(len(mesh.faces), 488)
		out = os.path.join(tempfile.mkdtemp(), 'x.obj')
		objfile.write(out, mesh)
		again = objfile.read(out)
		self.assertEqual(len(again.faces), len(mesh.faces))
		for fa, fb in zip(mesh.faces, again.faces):
			for (va, ta, na), (vb, tb, nb) in zip(fa, fb):
				self.assertTrue(close(mesh.positions[va], again.positions[vb], 1e-6))
				self.assertTrue(close(mesh.uvs[ta], again.uvs[tb], 1e-6))
				self.assertTrue(close(mesh.normals[na], again.normals[nb], 1e-6))

	def test_quads_are_triangulated_and_negative_indices_work(self):
		path = os.path.join(tempfile.mkdtemp(), 'q.obj')
		with open(path, 'w') as f:
			f.write('v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 -1\n')
		mesh = objfile.read(path)
		self.assertEqual(len(mesh.faces), 2)
		self.assertEqual(mesh.faces[1][2], (3, None, None))


if __name__ == '__main__':
	unittest.main()
