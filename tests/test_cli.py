"""Batch API and CLI regression tests; only synthetic TCX data."""
from __future__ import annotations

from contextlib import redirect_stderr,redirect_stdout
from datetime import datetime,timedelta,timezone
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tcx_running_analyzer.cli import main,parse_run_windows,find_files
from helpers import synthetic_tcx

class CLITests(unittest.TestCase):
    def call(self,*args):
        output=StringIO();errors=StringIO()
        with redirect_stdout(output),redirect_stderr(errors):
            code=main(list(map(str,args)))
        return code,output.getvalue(),errors.getvalue()

    def test_folder_creates_one_json_with_every_complete_report(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            early=synthetic_tcx(folder/'z_early.tcx',start=datetime(2026,1,1,tzinfo=timezone.utc))
            late=synthetic_tcx(folder/'a_late.tcx.xml',start=datetime(2026,1,4,tzinfo=timezone.utc))
            code,_,errs=self.call(folder,'--tz-offset','+04:00','--run-speed-kmh','6')
            self.assertEqual(code,0,errs)
            out=folder/'running-activities.json'
            self.assertTrue(out.is_file())
            j=json.loads(out.read_text('utf-8'))
            self.assertEqual(j['report_type'],'tcx_running_collection')
            self.assertEqual(j['summary']['activities_succeeded'],2)
            self.assertEqual(j['summary']['total_running_minutes'],20)
            self.assertEqual(len(j['activities']),2)
            self.assertEqual([a['source']['filename'] for a in j['activities']],[early.name,late.name])
            self.assertEqual([a['total']['run_count'] for a in j['activities']],[2,2])
            self.assertEqual([len(a['runs']) for a in j['activities']],[2,2])
            self.assertFalse((folder/'z_early.tcx.running.json').exists())
            self.assertFalse((folder/'a_late.tcx.xml.running.json').exists())
            self.assertEqual(j['activities'][0]['runs'][0]['treadmill_expected_running_m'],500)

    def test_single_file_creates_single_report(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            file=synthetic_tcx(folder/'one.tcx')
            code,_,errs=self.call(file,'--treadmill-km','1.7','--hr-source','polar_h10')
            self.assertEqual(code,0,errs)
            out=folder/'one.running.json'
            j=json.loads(out.read_text('utf-8'))
            self.assertNotIn('activities',j)
            self.assertEqual(j['total']['treadmill_distance_m'],1700)
            self.assertEqual(j['source']['hr_sensor']['value'],'polar_h10')

    def test_recursive_is_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            synthetic_tcx(folder/'first.tcx')
            synthetic_tcx(folder/'sub'/'second.TCX.XML')
            code,_,_=self.call(folder)
            self.assertEqual(code,0)
            first=json.loads((folder/'running-activities.json').read_text('utf-8'))
            self.assertEqual(len(first['activities']),1)
            code,_,errs=self.call(folder,'--recursive')
            self.assertEqual(code,0,errs)
            second=json.loads((folder/'running-activities.json').read_text('utf-8'))
            self.assertEqual(len(second['activities']),2)
            self.assertEqual({a['source']['relative_path'] for a in second['activities']},{'first.tcx','sub/second.TCX.XML'})

    def test_bad_file_records_error_but_preserves_other_reports(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            synthetic_tcx(folder/'valid.tcx')
            (folder/'invalid.tcx').write_text('<corrupted',encoding='utf-8')
            code,_,_=self.call(folder)
            self.assertEqual(code,1)
            out=json.loads((folder/'running-activities.json').read_text('utf-8'))
            self.assertEqual(out['summary']['activities_failed'],1)
            self.assertEqual(len(out['activities']),1)
            self.assertEqual(out['errors'][0]['filename'],'invalid.tcx')

    def test_metadata_per_file_no_guessing(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            synthetic_tcx(folder/'train_a.tcx')
            synthetic_tcx(folder/'train_b.tcx')
            meta=folder/'notes.json'
            meta.write_text(json.dumps({'files':{'train_a.tcx':{
                'treadmill_km':1.75,'run_speed_kmh':6,
                'hr_source':'polar_h10','subjective':{'foot_pain':False,'overall_fatigue':'mild'}
            }}}),encoding='utf-8')
            code,_,errs=self.call(folder,'--metadata',meta)
            self.assertEqual(code,0,errs)
            j=json.loads((folder/'running-activities.json').read_text('utf-8'))
            a={r['source']['filename']:r for r in j['activities']}
            self.assertEqual(a['train_a.tcx']['subjective']['foot_pain'],False)
            self.assertEqual(a['train_a.tcx']['subjective']['provenance'],'user_supplied_metadata')
            self.assertEqual(a['train_a.tcx']['source']['hr_sensor']['value'],'polar_h10')
            self.assertEqual(a['train_b.tcx']['source']['hr_sensor']['value'],'unknown')
            self.assertIsNone(a['train_b.tcx']['subjective']['foot_pain'])

    def test_folder_disallows_single_treadmill_km(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);synthetic_tcx(folder/'train.tcx')
            code,_,_=self.call(folder,'--treadmill-km','3.82')
            self.assertEqual(code,2)
            self.assertFalse((folder/'running-activities.json').exists())

    def test_run_windows_validation(self):
        self.assertEqual(parse_run_windows('00:05:00-00:10:00,00:11:00-00:12:00'),[(300,600),(660,720)])
        for spec in ['bad','00:01:00-00:00:59','00:10:00-00:20:00,00:19:00-00:21:00']:
            with self.assertRaises(ValueError): parse_run_windows(spec)

    def test_invalid_negative_and_nonfinite_parameters(self):
        with tempfile.TemporaryDirectory() as td:
            f=synthetic_tcx(Path(td)/'train.tcx')
            for s in ['-1','nan','inf']:
                # argparse exits on invalid types
                with self.assertRaises(SystemExit):self.call(f,'--run-speed-kmh',s)

    def test_folder_manual_windows_per_file(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            synthetic_tcx(d/'one.tcx',pattern=[('walk',300,100,90),('walk',300,100,90)])
            synthetic_tcx(d/'two.tcx')
            metadata=d/'my-metadata.json'
            metadata.write_text(json.dumps({'files':{'one.tcx':{
                'run_windows':[{'start_s':300,'end_s':600}],
                'run_speed_kmh':6
            }}}),encoding='utf-8')
            code,_,err=self.call(d,'--metadata',metadata)
            self.assertEqual(code,0,err)
            report=json.loads((d/'running-activities.json').read_text('utf-8'))
            activities={a['source']['filename']:a for a in report['activities']}
            self.assertEqual(activities['one.tcx']['total']['run_duration_s'],300)
            self.assertEqual(activities['one.tcx']['quality']['run_detection'],'manual_windows')
            self.assertEqual(activities['one.tcx']['quality']['run_detection_confidence'],'manual_override')
            self.assertEqual(activities['two.tcx']['total']['run_count'],2)

    def test_folder_manual_windows_string_and_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);synthetic_tcx(d/'one.tcx')
            metadata=d/'metadata.json'
            metadata.write_text(json.dumps({'files':{'one.tcx':{
                'run_windows':'00:05:00-00:10:00,00:11:00-00:16:00'
            }}}),encoding='utf-8')
            code,_,e=self.call(d,'--metadata',metadata)
            self.assertEqual(code,0,e)
            report=json.loads((d/'running-activities.json').read_text('utf-8'))
            self.assertEqual(report['activities'][0]['total']['run_count'],2)
            metadata.write_text(json.dumps({'files':{'one.tcx':{
                'run_windows':[{'start_s':400,'end_s':300}]
            }}}),encoding='utf-8')
            code,_,e=self.call(d,'--metadata',metadata)
            self.assertEqual(code,2)

    def test_archive_expected_manifest_and_date_gaps(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            synthetic_tcx(d/'first.tcx',start=datetime(2026,1,1,tzinfo=timezone.utc),
                pattern=[('walk',300,100,100),('run',300,166,100),('walk',60,100,100),('run',300,168,100),('walk',300,102,100)])
            synthetic_tcx(d/'second.tcx',start=datetime(2026,1,13,tzinfo=timezone.utc),
                pattern=[('walk',300,100,100),('run',300,166,100),('walk',60,100,100),('run',300,168,100),('walk',300,102,100)])
            manifest=d/'expected.json'
            manifest.write_text(json.dumps({'expected_files':['first.tcx','not-there.tcx']}),encoding='utf-8')
            code,_,e=self.call(d,'--expected-manifest',manifest,'--date-gap-days','7')
            self.assertEqual(code,0,e)
            report=json.loads((d/'running-activities.json').read_text('utf-8'))
            completion=report['summary']['archive_completeness']
            self.assertEqual(completion['status'],'missing_expected_files')
            self.assertEqual(completion['missing_files'],['not-there.tcx'])
            self.assertEqual(completion['unexpected_files'],['second.tcx'])
            self.assertEqual(report['summary']['observed_date_gaps'][0]['days_between'],12)
            self.assertEqual(report['summary']['activities_with_actionable_warnings'],0)
            self.assertEqual(report['summary']['quality_issue_counts_by_code']['HR_SOURCE_UNKNOWN'],2)
            manifest.write_text(json.dumps({'expected_files':['first.tcx','second.tcx']}),encoding='utf-8')
            code,_,e=self.call(d,'--expected-manifest',manifest)
            self.assertEqual(code,0,e)
            report=json.loads((d/'running-activities.json').read_text('utf-8'))
            self.assertEqual(report['summary']['archive_completeness']['status'],'complete')

    def test_expected_manifest_txt_and_uncertain_default(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);synthetic_tcx(d/'one.tcx')
            code,_,_=self.call(d)
            self.assertEqual(code,0)
            r=json.loads((d/'running-activities.json').read_text('utf-8'))
            self.assertEqual(r['summary']['archive_completeness']['status'],'not_assessed')
            manifest=d/'expected.txt'
            manifest.write_text('# comment\none.tcx\n',encoding='utf-8')
            code,_,e=self.call(d,'--expected-manifest',manifest)
            self.assertEqual(code,0,e)
            manifest.write_text('../bad.tcx',encoding='utf-8')
            code,_,e=self.call(d,'--expected-manifest',manifest)
            self.assertEqual(code,2)

    def test_metadata_windows_outside_trace_partial_batch_failure(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);synthetic_tcx(d/'valid.tcx');synthetic_tcx(d/'invalid_bounds.tcx')
            m=d/'meta.json';m.write_text(json.dumps({'files':{'invalid_bounds.tcx':{
                'run_windows':[{'start_s':99999,'end_s':100000}]
            }}}),encoding='utf-8')
            code,_,_=self.call(d,'--metadata',m)
            self.assertEqual(code,1)
            report=json.loads((d/'running-activities.json').read_text('utf-8'))
            self.assertEqual(report['summary']['activities_failed'],1)
            self.assertEqual(report['summary']['activities_succeeded'],1)

    def test_duplicate_basename_metadata_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);synthetic_tcx(d/'a'/'same.tcx');synthetic_tcx(d/'b'/'same.tcx')
            m=d/'meta.json';m.write_text('{"files":{"same.tcx":{"run_speed_kmh":6}}}',encoding='utf-8')
            code,_,errs=self.call(d,'--recursive','--metadata',m)
            self.assertEqual(code,2)

if __name__=='__main__': unittest.main()
