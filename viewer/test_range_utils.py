import unittest

from range_utils import parse_range


class RangeTests(unittest.TestCase):
    def test_full_range(self):
        self.assertEqual(parse_range("bytes=0-99", 100), (0, 99))

    def test_open_ended_range(self):
        self.assertEqual(parse_range("bytes=50-", 100), (50, 99))

    def test_suffix_range(self):
        self.assertEqual(parse_range("bytes=-20", 100), (80, 99))

    def test_end_is_clamped(self):
        self.assertEqual(parse_range("bytes=90-999", 100), (90, 99))

    def test_invalid_range(self):
        self.assertIsNone(parse_range("bytes=100-100", 100))
        self.assertIsNone(parse_range("bytes=90-80", 100))
        self.assertIsNone(parse_range("bytes=0-1,3-4", 100))
        self.assertIsNone(parse_range("items=0-1", 100))


if __name__ == "__main__":
    unittest.main()
