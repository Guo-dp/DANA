"""Independent checks against the manuscript's reported dynamic-cycle values."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dynamic_cycle_data import DATA, compute_cycle, expected_files, load_dynamic_cycle


class DynamicCycleDataTest(unittest.TestCase):
    def test_manuscript_table9(self):
        rows = load_dynamic_cycle()
        expected = [
            ("Base", .9993, 10.81, 92.55, 0, 0, "no"),
            ("Insert", .9993, 26.64, 37.54, 166667, 0, "no"),
            ("Update", .9994, 43.27, 23.11, 333334, 166667, "no"),
            ("Delete", .9994, 44.69, 22.38, 333334, 333334, "triggered"),
            ("After rebuild", .9991, 14.37, 69.59, 0, 0, "done"),
        ]
        self.assertEqual(len(rows), len(expected))
        for row, values in zip(rows, expected):
            actual = (row["state"], round(row["recall"], 4), round(row["approx_ms"], 2),
                      round(row["qps"], 2), row["delta_size"], row["tombstones"], row["rebuild"])
            self.assertEqual(actual, values)

    def test_all_repeats_are_pooled(self):
        rows, runs = compute_cycle()
        self.assertEqual(len(runs), 3)
        self.assertEqual(rows[-1]["queries"], 3000)
        self.assertAlmostEqual(rows[-1]["approx_ms"], (13.3833 + 9.3682 + 20.3599) / 3)
        self.assertAlmostEqual(rows[-1]["qps"], 1000 / rows[-1]["approx_ms"])
        self.assertNotAlmostEqual(rows[-1]["qps"], sum(r["qps"] for r in runs) / 3, places=2)

    def test_stale_csv_is_rejected(self):
        with TemporaryDirectory() as directory:
            data = Path(directory)
            for name in ("dynamic_metrics.txt", "post_rebuild_metrics.txt"):
                (data / name).write_bytes((DATA / name).read_bytes())
            for name, content in expected_files(data).items():
                (data / name).write_text(content, encoding="utf-8")
            (data / "table9.csv").write_text("stale\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Stale table9.csv"):
                load_dynamic_cycle(data)


if __name__ == "__main__":
    unittest.main()
