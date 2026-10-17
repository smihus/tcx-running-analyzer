"""Core tests use generated synthetic data only."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from garmin_tcx_running_analyzer.core import summarize,parse_tz,load_tcx
from helpers import synthetic_tcx

SETTINGS={'threshold':145,'min_seconds':45,'join_gap':12}

class CoreTests(unittest.TestCase):
    def test_detect_2x5min_with_one_minute_recovery(self):
        with tempfile.TemporaryDirectory() as t:
            file=synthetic_tcx(Path(t)/'synthetic.tcx')
            data=summarize(file,parse_tz('+04:00'),6,1.7,'polar_h10',SETTINGS)
            self.assertEqual(data['total']['run_count'],2)
            self.assertEqual(data['total']['run_duration_s'],600)
            self.assertEqual(data['total']['run_hr_avg_bpm'],124)
            self.assertEqual([r['duration_s'] for r in data['runs']],[300,300])
            self.assertEqual(data['source']['hr_sensor']['value'],'polar_h10')
            self.assertTrue(data['datetime']['start_local'].endswith('+04:00'))
            self.assertEqual(len(data['recoveries_between_runs']),1)
            self.assertEqual(data['recoveries_between_runs'][0]['duration_s'],60)
            self.assertEqual(data['warmup_last5min_before_running']['duration_s'],300)
            self.assertEqual(data['cooldown_first5min_after_running']['duration_s'],300)
            self.assertEqual(len(data['runs'][0]['five_minute_splits']),1)
            self.assertEqual(data['quality']['missing_hr_points'],0)
            self.assertEqual(data['quality']['duplicate_boundary_timestamps'],4)
            self.assertAlmostEqual(data['runs'][0]['treadmill_expected_running_m'],500.0,places=1)

    def test_no_default_hr_source_or_speed_inferred(self):
        with tempfile.TemporaryDirectory() as t:
            file=synthetic_tcx(Path(t)/'synthetic.tcx')
            data=summarize(file,parse_tz('+00:00'),None,None,'unknown',SETTINGS)
            self.assertEqual(data['source']['hr_sensor']['value'],'unknown')
            self.assertIsNone(data['total']['treadmill_distance_m'])
            self.assertNotIn('treadmill_expected_running_m',data['runs'][0])
            self.assertIsNone(data['subjective']['foot_pain'])

    def test_manual_windows_override_detector(self):
        with tempfile.TemporaryDirectory() as t:
            file=synthetic_tcx(Path(t)/'synthetic.tcx')
            data=summarize(file,parse_tz('+04:00'),None,None,'unknown',SETTINGS,
                           manual_windows=[(300,600),(660,960)])
            self.assertEqual(data['quality']['run_detection'],'manual_windows')
            self.assertEqual(data['total']['run_duration_s'],600)

    def test_continuous_30_minutes(self):
        with tempfile.TemporaryDirectory() as t:
            file=synthetic_tcx(Path(t)/'synthetic.tcx',pattern=[('walk',300,104,90),('run',1800,166,125),('walk',300,106,104)])
            data=summarize(file,parse_tz('+04:00'),6,None,'unknown',SETTINGS)
            self.assertEqual(data['total']['run_count'],1)
            self.assertEqual(data['total']['run_duration_s'],1800)
            self.assertEqual(len(data['runs'][0]['five_minute_splits']),6)
            self.assertAlmostEqual(data['runs'][0]['treadmill_expected_running_m'],3000,places=1)

    def test_missing_hr_does_not_become_zero(self):
        with tempfile.TemporaryDirectory() as t:
            file=synthetic_tcx(Path(t)/'synthetic.tcx',include_hr=False)
            data=summarize(file,parse_tz('+04:00'),6,None,'unknown',SETTINGS)
            self.assertIsNone(data['total']['run_hr_avg_bpm'])
            self.assertGreater(data['quality']['missing_hr_points'],0)

    def test_invalid_xml_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/'bad.tcx';file.write_text('<broken>',encoding='utf-8')
            with self.assertRaises(ValueError):
                load_tcx(file)

if __name__=='__main__': unittest.main()
