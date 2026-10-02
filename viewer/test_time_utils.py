import unittest
from datetime import datetime, timezone

from time_utils import LOCAL_TZ, iso_local, parse_filename_start, segment_end


class TimeUtilsTests(unittest.TestCase):
    def test_filename_start_has_explicit_vietnam_offset(self):
        dt = parse_filename_start("20260930", "080805")
        self.assertEqual(dt.tzinfo, LOCAL_TZ)
        self.assertEqual(iso_local(dt), "2026-09-30T08:08:05+07:00")

    def test_utc_is_converted_to_vietnam_time(self):
        dt = datetime(2026, 9, 30, 1, 8, 5, tzinfo=timezone.utc)
        self.assertEqual(iso_local(dt), "2026-09-30T08:08:05+07:00")

    def test_segment_end_preserves_offset(self):
        start = parse_filename_start("20260930", "080805")
        end = segment_end(start, 300.25)
        self.assertEqual(iso_local(end), "2026-09-30T08:13:05+07:00")


if __name__ == "__main__":
    unittest.main()
