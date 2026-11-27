"""Check coordinate conversion and tracker invalidation."""
import unittest
from backend.tracking import pixel_box
from backend.app import Lab


class TrackingTest(unittest.TestCase):
    def test_full_frame(self) -> None:
        self.assertEqual(pixel_box([0, 0, 1000, 1000], 640, 480), (0, 0, 640, 480))

    def test_subregion(self) -> None:
        self.assertEqual(pixel_box([250, 500, 750, 1000], 640, 480), (160, 240, 320, 240))

    def test_reset(self) -> None:
        lab = Lab()
        lab.tracking = True
        lab.track_job = object()
        epoch = lab.track_epoch
        lab.reset_tracking()
        self.assertFalse(lab.tracking)
        self.assertIsNone(lab.track_job)
        self.assertEqual(lab.track_epoch, epoch + 1)
