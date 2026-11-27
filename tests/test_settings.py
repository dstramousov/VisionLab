"""Validate basic configuration and control contracts."""
import unittest
from pydantic import ValidationError
from backend.app import Lab, Settings


class SettingsTest(unittest.TestCase):
    def test_invalid_device(self) -> None:
        values = Lab().settings.model_dump()
        values['camera'] = '/etc/passwd'
        with self.assertRaises(ValidationError):
            Settings(**values)

    def test_submit_without_camera(self) -> None:
        with self.assertRaises(RuntimeError):
            Lab().submit('test', 'manual')

    def test_default(self) -> None:
        self.assertEqual(Lab().settings.width, 640)

    def test_reasoning(self) -> None:
        from backend.app import split_reasoning
        self.assertEqual(split_reasoning('<think>abc</think>answer', ''), ('answer', 'abc'))
        self.assertEqual(split_reasoning('<think>abc', ''), ('', 'abc'))

    def test_difference(self) -> None:
        import cv2
        import numpy as np
        from backend.app import frame_difference
        black = cv2.imencode('.jpg', np.zeros((60, 80), dtype=np.uint8))[1].tobytes()
        white = cv2.imencode('.jpg', np.full((60, 80), 255, dtype=np.uint8))[1].tobytes()
        self.assertEqual(frame_difference(black, black), 0)
        self.assertEqual(frame_difference(black, white), 100)
