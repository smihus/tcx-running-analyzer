"""Brand-neutral API contract; synthetic fixture only."""
from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tcx_running_analyzer.core import VERSION, parse_tz, summarize
from helpers import synthetic_tcx

SETTINGS = {"threshold": 145, "min_seconds": 45, "join_gap": 12}
OLD_KEYS = {"garmin_distance_m", "distance_garmin_m", "garmin_distance_error_pct"}


class BrandingTests(unittest.TestCase):
    def test_brand_neutral_fields_and_schema(self):
        with tempfile.TemporaryDirectory() as td:
            file = synthetic_tcx(Path(td) / "run.tcx")
            report = summarize(file, parse_tz("+00:00"), 6, 1.5, "unknown", SETTINGS)
            self.assertEqual(report["schema_version"], "2.0")
            self.assertIn("tcx_distance_m", report["total"])
            self.assertIn("distance_tcx_m", report["runs"][0])
            self.assertIn("tcx_distance_error_pct", report["runs"][0])
            self.assertIn("tcx_distance_m", report["lap_metadata"][0])
            self.assertFalse(OLD_KEYS.intersection(set(report["total"])))
            self.assertFalse(OLD_KEYS.intersection(set(report["runs"][0])))
            self.assertFalse(OLD_KEYS.intersection(set(report["lap_metadata"][0])))

    def test_distribution_and_module_names(self):
        import tcx_running_analyzer
        self.assertEqual(tcx_running_analyzer.__version__, VERSION)
        manifest = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text("utf-8")
        self.assertIn('name = "tcx-running-analyzer"', manifest)
        self.assertIn('tcx-running-analyzer = "tcx_running_analyzer.cli:main"', manifest)
        self.assertNotIn('garmin-tcx-running-analyzer', manifest)
