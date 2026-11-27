"""Exercise crop geometry and verification overlap."""
import unittest
import cv2
import numpy as np
from backend.attention import crop_region, restore_box, overlap
from backend.app import AttentionSettings


class AttentionTest(unittest.TestCase):
    def test_crop(self) -> None:
        ok, jpeg = cv2.imencode('.jpg', np.zeros((480, 640, 3), np.uint8))
        self.assertTrue(ok)
        _, region, size = crop_region(jpeg.tobytes(), [250, 250, 750, 750])
        self.assertEqual(region, (0, 0, 640, 480))
        self.assertEqual(restore_box([250, 250, 750, 750], region, size), [250, 250, 750, 750])

    def test_offset(self) -> None:
        self.assertEqual(restore_box([0, 0, 1000, 1000], (160, 120, 480, 360), (640, 480)), [250, 250, 750, 750])

    def test_overlap(self) -> None:
        self.assertEqual(overlap((0, 0, 10, 10), (0, 0, 10, 10)), 1)
        self.assertEqual(overlap((0, 0, 10, 10), (10, 0, 10, 10)), 0)
        self.assertAlmostEqual(overlap((0, 0, 10, 10), (5, 0, 10, 10)), 1/3)

    def test_default(self) -> None:
        self.assertEqual(AttentionSettings().verify_interval, 0)
