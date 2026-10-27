import math
import unittest
from scene3d import rotate_point, project_point, advance_particle


class Scene3DTests(unittest.TestCase):
    def test_perspective_near_ball_is_larger_and_further_from_center(self):
        near = project_point(0.5, 0.2, -0.8)
        far = project_point(0.5, 0.2, 0.8)
        self.assertGreater(near[2], far[2])
        self.assertGreater(near[0] - 170, far[0] - 170)
        with self.assertRaises(ValueError):
            project_point(0, 0, -4)

    def test_rotating_camera_preserves_3d_distance(self):
        point = (0.4, -0.3, 0.6)
        for angle in (0, 0.5, 1.4, 3.1):
            rotated = rotate_point(*point, angle)
            self.assertAlmostEqual(sum(v * v for v in point), sum(v * v for v in rotated))

    def test_balls_remain_inside_spherical_drum(self):
        position, velocity = (0.8, 0.1, 0.1), (0.04, 0.01, 0.03)
        for _ in range(2000):
            position, velocity = advance_particle(position, velocity)
            self.assertLessEqual(math.sqrt(sum(v * v for v in position)), 0.86000001)
            self.assertLessEqual(math.sqrt(sum(v * v for v in velocity)), 0.04300001)
