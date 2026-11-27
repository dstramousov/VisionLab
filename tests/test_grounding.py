"""Check strict grounding response validation."""
import unittest
from backend.grounding import parse_box


class GroundingTest(unittest.TestCase):
    def test_found(self) -> None:
        self.assertEqual(parse_box('{"box":[0,20,1000,900]}'), [0,20,1000,900])

    def test_missing(self) -> None:
        self.assertIsNone(parse_box('{"box":null}'))

    def test_invalid(self) -> None:
        for text in ('{"box":[10,0,5,9]}', '{"box":[0,0,1001,9]}',
                     '{"box":[false,0,10,9]}', 'not JSON', '{"box":[0,0,1,1],"extra":1}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_box(text)
