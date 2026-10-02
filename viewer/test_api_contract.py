import unittest

from resolver import resolve_event


class EventApiContractTests(unittest.TestCase):
    def test_resolved_event_has_playback_mapping(self):
        segments = [{
            "file": "cam1-20260930-080000.mp4",
            "relative_path": "cam1/cam1-20260930-080000.mp4",
            "start": "2026-09-30T08:00:00+07:00",
            "end": "2026-09-30T08:05:00+07:00",
        }]
        event = {"event_local": "2026-09-30T08:02:30"}
        result = resolve_event(event, segments)

        self.assertEqual(result["timestamp"], "2026-09-30T08:02:30+07:00")
        self.assertTrue(result["resolved"])
        self.assertEqual(result["segment"], segments[0]["relative_path"])
        self.assertEqual(result["offset_seconds"], 150.0)

    def test_unresolved_event_keeps_reason(self):
        segments = [{
            "file": "cam1-20260930-080000.mp4",
            "relative_path": "cam1/cam1-20260930-080000.mp4",
            "start": "2026-09-30T08:00:00+07:00",
            "end": "2026-09-30T08:05:00+07:00",
        }]
        result = resolve_event(
            {"event_local": "2026-09-30T08:10:00+07:00"},
            segments,
        )

        self.assertFalse(result["resolved"])
        self.assertEqual(result["reason"], "no_recording_segment")


if __name__ == "__main__":
    unittest.main()
