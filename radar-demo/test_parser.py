import unittest
from parser import PreviewParser, describe


class PreviewTests(unittest.TestCase):
    def test_truncated_frame_preserves_reported_count(self):
        p = PreviewParser()
        p.push("[RADAR] \x1b[1;32muart:~$ \x1b[mPoint Cloud=10:", 1)
        for i in range(4):
            self.assertEqual(p.push(f"[RADAR] P{i}: x=-20cm\ty=150cm\tz=-40cm\t-75cm/s\t2800", 1), [])
        frames = p.push("[RADAR] Point Cloud=0:", 2)
        self.assertEqual([f["reported_points"] for f in frames], [10, 0])
        self.assertTrue(frames[0]["preview_incomplete"])
        self.assertEqual(len(frames[0]["points"]), 4)
        self.assertEqual(frames[0]["points"][0]["velocity_cm_s"], -75)
        self.assertFalse(frames[1]["preview_incomplete"])

    def test_duplicate_and_orphan_coordinates(self):
        p = PreviewParser()
        line = "P0: x=20cm y=150cm z=-40cm -75cm/s 2800"
        self.assertEqual(p.push(line, 1), [])
        p.push("Point Cloud=2:", 2)
        p.push(line, 2)
        p.push(line, 2)
        frame = p.flush()[0]
        self.assertEqual(len(frame["points"]), 1)
        self.assertTrue(frame["preview_incomplete"])
        self.assertEqual(p.flush(), [])

    def test_missing_report_is_distinct_from_zero(self):
        self.assertIsNone(describe(None)["motion"])
        self.assertFalse(describe({"reported_points": 0, "points": []})["motion"])
        self.assertIsNone(describe({"reported_points": 3, "points": []})["motion"])


if __name__ == "__main__":
    unittest.main()
