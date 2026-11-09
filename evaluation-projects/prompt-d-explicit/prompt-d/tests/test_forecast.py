import tempfile, unittest
from pathlib import Path
from devpilot import forecast as f


class T(unittest.TestCase):
    def test_mae_hand_computed(self):
        self.assertAlmostEqual(f.mae([1, 2, 3], [2, 2, 5]), (1 + 0 + 2) / 3)

    def test_bad_inputs_rejected(self):
        for a, b in (([], []), ([1], [1, 2]), ([float("nan")], [1.0]), (["x"], [1.0])):
            with self.assertRaises(f.DataError): f.mae(a, b)

    def test_pipeline_is_chronological_and_leak_free(self):
        d = Path(tempfile.mkdtemp()) / "s.csv"; f.make_synthetic(d)
        _, v = f.load_series(d)
        # one_step must only see the past: changing the future must not change earlier forecasts
        v2 = v[:300] + [999.0] * (len(v) - 300)
        self.assertEqual(f.one_step(f.naive, v, 250, 300), f.one_step(f.naive, v2, 250, 300))
        r = f.evaluate(v)
        self.assertLess(r["test_mae_selected"], 5.0)
        self.assertIn("SYNTHETIC", r["label"])

    def test_error_demo_all_rejected(self):
        out = f.demo_errors(tempfile.mkdtemp())
        self.assertTrue(all(x.startswith("rejected") for x in out.values()), out)
