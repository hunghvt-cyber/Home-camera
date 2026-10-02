import unittest

from resolver import resolve_event, resolve_events


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.segments = [
            {
                "file": "cam1-20260930-080000.mp4",
                "relative_path": "cam1/cam1-20260930-080000.mp4",
                "start": "2026-09-30T08:00:00+07:00",
                "end": "2026-09-30T08:05:00+07:00",
                "duration": 300,
            },
            {
                "file": "cam1-20260930-080500.mp4",
                "relative_path": "cam1/cam1-20260930-080500.mp4",
                "start": "2026-09-30T08:05:00+07:00",
                "end": "2026-09-30T08:10:00+07:00",
                "duration": 300,
            },
        ]

    def test_resolves_inside_segment(self):
        event = {"event_local": "2026-09-30T08:03:12"}
        result = resolve_event(event, self.segments)
        self.assertTrue(result["resolved"])
        self.assertEqual(result["segment"], self.segments[0]["relative_path"])
        self.assertAlmostEqual(result["offset_seconds"], 192.0)

    def test_boundary_is_next_segment(self):
        event = {"event_local": "2026-09-30T08:05:00+07:00"}
        result = resolve_event(event, self.segments)
        self.assertTrue(result["resolved"])
        self.assertEqual(result["segment"], self.segments[1]["relative_path"])
        self.assertEqual(result["offset_seconds"], 0.0)

    def test_unresolved_gap_is_not_guessed(self):
        event = {"event_local": "2026-09-30T08:12:00+07:00"}
        result = resolve_event(event, self.segments)
        self.assertFalse(result["resolved"])
        self.assertEqual(result["reason"], "no_recording_segment")

    def test_invalid_timestamp_is_not_guessed(self):
        event = {"event_local": "not-a-date"}
        result = resolve_event(event, self.segments)
        self.assertFalse(result["resolved"])
        self.assertEqual(result["reason"], "invalid_event_timestamp")

    def test_stale_hint_cannot_override_timestamp(self):
        event = {
            "event_local": "2026-09-30T08:06:00+07:00",
            "segment": "cam1-20260930-080000.mp4",
        }
        result = resolve_event(event, self.segments)
        self.assertTrue(result["resolved"])
        self.assertEqual(result["segment"], self.segments[1]["relative_path"])

    def test_batch_keeps_unresolved_events(self):
        events = [
            {"event_local": "2026-09-30T08:01:00"},
            {"event_local": "2026-09-30T08:20:00"},
        ]
        result = resolve_events(events, self.segments)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]["resolved"])
        self.assertFalse(result[1]["resolved"])


if __name__ == "__main__":
    unittest.main()
