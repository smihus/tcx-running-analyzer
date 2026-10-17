"""Core tests use generated synthetic data only."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tcx_running_analyzer.core import summarize,parse_tz,load_tcx
from helpers import synthetic_tcx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

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

    def test_info_vs_actionable_quality_and_detection_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            file=synthetic_tcx(Path(td)/'workout.tcx',
                pattern=[('walk',300,100,100),('run',300,166,100),('walk',60,100,100),
                         ('run',300,168,100),('walk',300,102,100)])
            result=summarize(file,parse_tz('+04:00'),6,None,'unknown',SETTINGS)
            self.assertIn('HR_SOURCE_UNKNOWN', [x['code'] for x in result['quality']['issues']])
            self.assertEqual(result['quality']['warning_count'],0)
            self.assertEqual(result['quality']['info_count'],1)
            self.assertEqual(result['quality']['run_detection_confidence'],'high')
            self.assertTrue(all(x['detection']['confidence']=='high' for x in result['runs']))
            self.assertGreaterEqual(result['runs'][0]['detection']['cadence_support_fraction'],0.98)

    def test_anomalous_hr_events_timestamp_magnitude_and_phase(self):
        with tempfile.TemporaryDirectory() as td:
            file=synthetic_tcx(Path(td)/'workout.tcx')
            xml=ET.parse(file)
            ns={'t':'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
            laps=xml.findall('.//t:Lap',ns)
            # First run at 300 s, cooldown after 960 s.
            def set_hr(lap_i, sec, value):
                tp=laps[lap_i].findall('t:Track/t:Trackpoint',ns)[sec]
                tp.find('t:HeartRateBpm/t:Value',ns).text=str(value)
            # Two independent one-second jumps, in distinct phases.
            set_hr(1,99,122)
            set_hr(1,100,143)
            set_hr(1,101,143)
            set_hr(4,99,96)
            set_hr(4,100,120)
            set_hr(4,101,120)
            xml.write(file,encoding='utf-8',xml_declaration=True)
            result=summarize(file,parse_tz('+04:00'),None,None,'polar_h10',SETTINGS)
            events=result['quality']['hr_abrupt_jumps']
            self.assertTrue(any(e['phase']=='running' and e['absolute_delta_bpm']==21 for e in events))
            self.assertTrue(any(e['phase']=='post_run_5min' and e['absolute_delta_bpm']==24 for e in events))
            self.assertTrue(all(e['time_utc'] and e['time_local'] for e in events))
            self.assertEqual(result['quality']['warning_count'],1)
            self.assertEqual(result['quality']['info_count'],0)

    def test_adjacent_hr_jumps_are_grouped_into_one_episode(self):
        from tcx_running_analyzer.core import group_hr_jump_episodes
        events = [
            {'time_utc':'2026-03-23T16:25:04+00:00','time_local':'2026-03-23T20:25:04+04:00',
             'phase':'before_running','run_index':None,
             'hr_previous_bpm':79,'hr_current_bpm':102,'delta_bpm':23},
            {'time_utc':'2026-03-23T16:25:05+00:00','time_local':'2026-03-23T20:25:05+04:00',
             'phase':'before_running','run_index':None,
             'hr_previous_bpm':102,'hr_current_bpm':116,'delta_bpm':14},
        ]
        episodes=group_hr_jump_episodes(events)
        self.assertEqual(len(episodes),1)
        e=episodes[0]
        self.assertEqual((e['hr_start_bpm'],e['hr_end_bpm'],e['net_delta_bpm']),(79,116,37))
        self.assertEqual((e['jump_samples'],e['duration_s']),(2,2))
        self.assertEqual(e['start_local'],'2026-03-23T20:25:03+04:00')
        self.assertEqual(e['end_local'],'2026-03-23T20:25:05+04:00')

    def test_jump_episode_grouping_does_not_merge_phase_gap_or_direction(self):
        from tcx_running_analyzer.core import group_hr_jump_episodes
        def make(t,prev,cur,phase):
            return {'time_utc':f'2026-09-17T16:46:{t:02d}+00:00',
                    'time_local':f'2026-09-17T20:46:{t:02d}+04:00',
                    'phase':phase,'run_index':None,
                    'hr_previous_bpm':prev,'hr_current_bpm':cur,'delta_bpm':cur-prev}
        events=[make(12,135,152,'post_run_5min'),make(13,152,165,'post_run_5min'),
                make(14,165,151,'post_run_5min'),make(15,151,167,'after_running'),
                make(18,167,155,'after_running')]
        e=group_hr_jump_episodes(events)
        self.assertEqual(len(e),4)
        self.assertEqual(e[0]['net_delta_bpm'],30)
        self.assertEqual(e[1]['direction'],'fall')
        self.assertEqual(e[2]['phase'],'after_running')

    def test_non_running_low_cadence_lap_is_flagged_as_candidate_not_run(self):
        from tcx_running_analyzer.core import ambiguous_low_cadence_laps
        date=datetime(2026,3,9,tzinfo=timezone.utc)
        laps=[{'number':2,'start':date,'seconds':176.1,'avg_run_cadence_raw':64},
              {'number':4,'start':date,'seconds':1200,'avg_run_cadence_raw':50}]
        r=ambiguous_low_cadence_laps(laps,parse_tz('+04:00'),145,45)
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['lap_number'],2)
        self.assertEqual(r[0]['avg_cadence_spm'],128)

    def test_manual_override_is_not_claimed_as_high_auto_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            file=synthetic_tcx(Path(td)/'workout.tcx')
            r=summarize(file,parse_tz('+00:00'),None,None,'unknown',SETTINGS,
                        manual_windows=[(300,600)])
            self.assertEqual(r['quality']['run_detection_confidence'],'manual_override')
            self.assertEqual(r['runs'][0]['detection']['confidence'],'manual_override')
            self.assertEqual(r['total']['run_count'],1)

    def test_manual_window_beyond_activity_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f=synthetic_tcx(Path(td)/'test.tcx')
            with self.assertRaisesRegex(ValueError,'outside available TCX'):
                summarize(f,parse_tz('+00:00'),None,None,'unknown',SETTINGS,
                          manual_windows=[(999999,1000010)])

    def test_invalid_xml_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/'bad.tcx';file.write_text('<broken>',encoding='utf-8')
            with self.assertRaises(ValueError):
                load_tcx(file)

if __name__=='__main__': unittest.main()
