"""Self-contained synthetic outdoor tests. No private GPS locations or TCX files."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from garmin_tcx_running_analyzer.core import parse_tz, summarize
from garmin_tcx_running_analyzer.cli import resolve_activity_identities, batch_summary, read_metadata
from garmin_tcx_running_analyzer.metadata_cli import validate_patch

NS='http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'
EX='http://www.garmin.com/xmlschemas/ActivityExtension/v2'
ET.register_namespace('',NS)
ET.register_namespace('ext',EX)
S={'threshold':145,'min_seconds':45,'join_gap':12}


def fixture(path: Path, *, raw_cad=83, speed=2.8, spacing=1, samples=240,
            pause_after=None, pause_seconds=0, hr=True, gps=True):
    start=datetime(2026,1,3,12,0,tzinfo=timezone.utc)
    def sub(p,n,v=None,ns=NS):
        x=ET.SubElement(p,f'{{{ns}}}{n}')
        if v is not None: x.text=str(v)
        return x
    root=sub(None,'TrainingCenterDatabase') if False else ET.Element(f'{{{NS}}}TrainingCenterDatabase')
    acts=sub(root,'Activities'); act=sub(acts,'Activity');act.set('Sport','Running')
    sub(act,'Id',start.isoformat().replace('+00:00','Z'))
    lap=sub(act,'Lap');lap.set('StartTime',start.isoformat().replace('+00:00','Z'))
    sub(lap,'TotalTimeSeconds',str((samples-1)*spacing+1))
    sub(lap,'DistanceMeters',str((samples-1)*spacing*speed))
    track=sub(lap,'Track')
    for i in range(samples):
        t=start+timedelta(seconds=i*spacing+(pause_seconds if pause_after is not None and i>pause_after else 0))
        tp=sub(track,'Trackpoint')
        sub(tp,'Time',t.isoformat().replace('+00:00','Z'))
        if gps:
            pos=sub(tp,'Position');sub(pos,'LatitudeDegrees',51.0+i*.00001)
            sub(pos,'LongitudeDegrees',-1.0+i*.00001)
            sub(tp,'AltitudeMeters',20+i*.03)
        if hr:
            bpm=sub(tp,'HeartRateBpm');sub(bpm,'Value',125)
        # Keep zero distance gain across inferred pause, resume after next sample.
        offset = (1 if pause_after is not None and i>pause_after else 0)
        sub(tp,'DistanceMeters',max(0, (i-offset)*spacing*speed))
        ext=sub(tp,'Extensions');tpx=sub(ext,'TPX',ns=EX)
        sub(tpx,'RunCadence',raw_cad,ns=EX)
        sub(tpx,'Speed',speed,ns=EX)
    path.parent.mkdir(parents=True,exist_ok=True)
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    return path


class OutdoorTests(unittest.TestCase):
    def test_outdoor_elapsed_timer_and_pauses_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            p=fixture(Path(td)/'pause.tcx',pause_after=119,pause_seconds=61)
            r=summarize(p,parse_tz('+00:00'),None,None,'unknown',S)
            self.assertEqual(r['source']['activity_mode']['value'],'outdoor')
            self.assertEqual(r['total']['elapsed_duration_s'],300)
            self.assertEqual(r['total']['timer_duration_s'],240)
            self.assertEqual(r['total']['inferred_paused_duration_s'],62)
            self.assertEqual(r['total']['run_count'],2)
            self.assertLessEqual(r['total']['running_moving_duration_s'],240)
            self.assertGreater(r['total']['running_moving_duration_s'],220)
            self.assertEqual(len(r['outdoor']['inferred_pauses']),1)
            self.assertTrue(r['outdoor']['gps_available'])
            self.assertEqual(len(r['outdoor']['kilometer_splits']),0)
            self.assertNotIn('LatitudeDegrees',json.dumps(r))
            self.assertNotIn('LongitudeDegrees',json.dumps(r))
            self.assertEqual(r['quality']['warning_count'],0)
            timeline=r['movement']['segments']
            self.assertEqual(round(sum(x['duration_s'] for x in timeline),1),r['total']['elapsed_duration_s'])
            self.assertEqual(sum(x['duration_s'] for x in timeline if x['kind']=='inferred_stationary'),62)

    def test_sparse_walking_not_a_false_run_or_gap_warning(self):
        with tempfile.TemporaryDirectory() as td:
            p=fixture(Path(td)/'walk.tcx',raw_cad=58,speed=1.53,spacing=13,samples=70)
            r=summarize(p,parse_tz('+00:00'),None,None,'unknown',S)
            self.assertEqual(r['movement']['inferred_activity']['value'],'walking')
            self.assertEqual(r['total']['run_duration_s'],0)
            self.assertEqual(r['quality']['warning_count'],0)
            self.assertFalse(any(i['code']=='RUN_SEGMENTS_NOT_FOUND' for i in r['quality']['issues']))

    def test_sparse_outdoor_running_and_missing_hr(self):
        with tempfile.TemporaryDirectory() as td:
            p=fixture(Path(td)/'run.tcx',raw_cad=84,speed=3.0,spacing=8,samples=65,hr=False)
            r=summarize(p,parse_tz('+00:00'),None,None,'unknown',S)
            self.assertEqual(r['total']['run_count'],1)
            self.assertLessEqual(r['total']['run_duration_s'],r['total']['elapsed_duration_s'])
            self.assertEqual(len(r['outdoor']['kilometer_splits']),1)
            self.assertEqual(r['outdoor']['kilometer_splits'][0]['index'],1)
            codes={i['code'] for i in r['quality']['issues']}
            self.assertIn('HR_DATA_MISSING',codes)
            self.assertNotIn('HR_SOURCE_UNKNOWN',codes)
            self.assertNotIn('TRACKPOINT_GAPS',codes)
            self.assertIsNone(r['total']['run_hr_avg_bpm'])


    def test_unobserved_moving_gap_interrupts_running_but_is_not_pause(self):
        with tempfile.TemporaryDirectory() as td:
            p=fixture(Path(td)/'gap.tcx',pause_after=119,pause_seconds=90)
            tree=ET.parse(p)
            trackpoints=[node for node in tree.iter() if node.tag.endswith('Trackpoint')]
            # 100 m of Garmin distance progress recorded across a 91s gap.
            for tp in trackpoints[120:]:
                dist=next(node for node in tp if node.tag.endswith('DistanceMeters'))
                dist.text=str(float(dist.text)+100)
            tree.write(p,encoding='utf-8',xml_declaration=True)
            result=summarize(p,parse_tz('+00:00'),None,None,'unknown',S)
            self.assertEqual(result['total']['run_count'],2)
            self.assertEqual(result['total']['inferred_paused_duration_s'],0)
            self.assertEqual(len(result['outdoor']['unobserved_gaps']),1)
            self.assertEqual(result['outdoor']['unobserved_gaps'][0]['classification'],'unobserved_gap')
            self.assertLess(result['total']['running_moving_duration_s'],result['outdoor']['active_estimated_duration_s'])
            self.assertIn('UNOBSERVED_GAP',[x['code'] for x in result['quality']['issues']])

    def test_km_split_subtracts_inferred_pause_from_active_pace(self):
        with tempfile.TemporaryDirectory() as td:
            p=fixture(Path(td)/'split.tcx',samples=500,speed=3.0,pause_after=200,pause_seconds=60)
            result=summarize(p,parse_tz('+00:00'),None,None,'unknown',S)
            splits=result['outdoor']['kilometer_splits']
            self.assertEqual(len(splits),1)
            self.assertGreater(splits[0]['elapsed_s']-splits[0]['active_estimated_s'],59)
            self.assertIsNotNone(splits[0]['pace_active_sec_per_km'])


    def test_outdoor_mile_lap_does_not_force_walking_into_running(self):
        with tempfile.TemporaryDirectory() as td:
            p=fixture(Path(td)/'mixed.tcx',samples=300)
            tree=ET.parse(p)
            trackpoints=[n for n in tree.iter() if n.tag.endswith('Trackpoint')]
            for i, tp in enumerate(trackpoints):
                for node in tp.iter():
                    if node.tag.endswith('RunCadence') and 120<=i<190:
                        node.text='58'
                    if node.tag.endswith('Speed') and 120<=i<190:
                        node.text='1.5'
                    if node.tag.endswith('DistanceMeters'):
                        node.text=str(2.8*min(i,120) + 1.5*max(0,min(i,190)-120) + 2.8*max(0,i-190))
            lap=next(n for n in tree.iter() if n.tag.endswith('Lap'))
            ext=ET.SubElement(lap,f'{{{NS}}}Extensions')
            lx=ET.SubElement(ext,f'{{{EX}}}LX')
            ET.SubElement(lx,f'{{{EX}}}AvgRunCadence').text='80'
            tree.write(p,encoding='utf-8',xml_declaration=True)
            r=summarize(p,parse_tz('+00:00'),None,None,'unknown',S)
            self.assertEqual(r['total']['run_count'],2)
            self.assertGreater(r['movement']['likely_walking_duration_s'],40)
            self.assertEqual(r['quality']['run_detection'],'outdoor_cadence')
            self.assertLess(r['total']['run_duration_s'],r['total']['elapsed_duration_s']-50)

    def test_metadata_mode_override_validation(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'metadata.json'
            f.write_text('{"files":{"run.tcx":{"activity_mode":"outdoor"}}}',encoding='utf-8')
            self.assertEqual(read_metadata(f)['run.tcx']['activity_mode'],'outdoor')
            validate_patch({'activity_mode':'treadmill'})
            f.write_text('{"files":{"run.tcx":{"activity_mode":"space"}}}',encoding='utf-8')
            with self.assertRaises(ValueError): read_metadata(f)
            with self.assertRaises(ValueError): validate_patch({'activity_mode':'space'})


    def test_outdoor_speed_fallback_has_low_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            path=fixture(Path(td)/'speedonly.tcx',raw_cad=83,speed=3.1,samples=130)
            tree=ET.parse(path)
            for parent in tree.iter():
                for node in list(parent):
                    if node.tag.endswith('RunCadence'):
                        parent.remove(node)
            tree.write(path,encoding='utf-8',xml_declaration=True)
            result=summarize(path,parse_tz('+00:00'),None,None,'unknown',S)
            self.assertEqual(result['total']['run_count'],1)
            self.assertEqual(result['quality']['run_detection'],'outdoor_speed_fallback')
            self.assertEqual(result['quality']['run_detection_confidence'],'low')

    def test_same_activity_id_equivalent_exports_count_once(self):
        with tempfile.TemporaryDirectory() as td:
            r=summarize(fixture(Path(td)/'a.tcx'),parse_tz('+00:00'),None,None,'unknown',S)
            r2=copy.deepcopy(r)
            r2['source']['filename']='b.tcx'
            r2['source']['sha256']='2'*64
            unique, dupl, conflicts=resolve_activity_identities([r,r2])
            self.assertEqual((len(unique),len(dupl),len(conflicts)),(1,1,0))
            self.assertEqual(len([x for x in (r,r2) if x['source']['identity_status']=='duplicate_export']),1)
            summary=batch_summary(unique,2,[],raw_count=2)
            self.assertEqual(summary['activities_succeeded'],2)
            self.assertEqual(summary['unique_activities_counted'],1)
            self.assertAlmostEqual(summary['total_running_minutes'],r['total']['run_duration_s']/60,places=2)

    def test_same_id_conflicting_distance_is_preserved_with_warning(self):
        with tempfile.TemporaryDirectory() as td:
            r=summarize(fixture(Path(td)/'a.tcx'),parse_tz('+00:00'),None,None,'unknown',S)
            r2=copy.deepcopy(r)
            r2['source']['filename']='b.tcx'
            r2['total']['garmin_distance_m']+=1000
            unique, dupl, conflicts=resolve_activity_identities([r,r2])
            self.assertEqual(len(unique),2)
            self.assertEqual(len(dupl),0)
            self.assertEqual(len(conflicts),1)
            self.assertTrue(all(a['source']['identity_status']=='id_conflict' for a in (r,r2)))

if __name__=='__main__': unittest.main()
