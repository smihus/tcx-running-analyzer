"""Synthetic agent workflow tests; no real person's TCX or metadata."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from helpers import synthetic_tcx
from tcx_running_analyzer.metadata_cli import main as metadata_main
from tcx_running_analyzer.workflow_cli import main as workflow_main


class WorkflowTests(unittest.TestCase):
    def execute(self, fn, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = fn(list(map(str, args)))
        return code, out.getvalue(), err.getvalue()

    def test_complete_ingest_metadata_and_repeat_without_duplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = synthetic_tcx(root / 'inbox' / 'run.tcx')
            workspace = root / 'local-data'
            args = ['ingest', '--workspace', workspace, '--tz-offset', '+04:00', inp]
            code, _, error = self.execute(workflow_main, *args)
            self.assertEqual(code, 0, error)
            raw = json.loads((workspace / 'running-activities.json').read_text('utf-8'))
            original = raw['activities'][0]
            self.assertEqual(raw['summary']['files_found'], 1)
            self.assertEqual(original['datetime']['start_local'][-6:], '+04:00')
            self.assertIsNone(original['subjective']['foot_pain'])
            self.assertFalse((workspace / 'running-metadata.json').exists())

            patch = root / 'user-feedback.json'
            patch.write_text(json.dumps({'hr_source':'polar_h10', 'treadmill_km': 1.86,
                    'subjective': {'foot_pain':False, 'overall_fatigue':'mild'}}), encoding='utf-8')
            code, _, error = self.execute(metadata_main, '--report', workspace/'running-activities.json',
                    '--metadata', workspace/'running-metadata.json', '--file', 'run.tcx', '--patch', patch)
            self.assertEqual(code, 0, error)
            code, _, error = self.execute(workflow_main, 'rebuild', '--workspace', workspace)
            self.assertEqual(code, 0, error)
            hist = json.loads((workspace / 'running-history.json').read_text('utf-8'))
            enriched = hist['activities'][0]
            self.assertEqual(enriched['total']['treadmill_distance_m'], 1860)
            self.assertFalse(enriched['subjective']['foot_pain'])
            self.assertEqual(enriched['source']['hr_sensor']['value'], 'polar_h10')
            self.assertEqual(enriched['total']['run_hr_avg_bpm'], original['total']['run_hr_avg_bpm'])
            self.assertIsNone(raw['activities'][0]['total']['treadmill_distance_m'])
            self.assertEqual(list((workspace/'tcx').iterdir())[0].read_bytes(), inp.read_bytes())

            # Repeat ingestion: no duplicate workout and no lost user notes.
            code, output, error = self.execute(workflow_main, 'ingest', '--workspace', workspace, inp)
            self.assertEqual(code, 0, error)
            self.assertIn('0 new, 1 already present', output)
            repeated = json.loads((workspace / 'running-history.json').read_text('utf-8'))
            self.assertEqual(repeated['summary']['files_found'], 1)
            self.assertEqual(repeated['activities'][0]['subjective']['overall_fatigue'], 'mild')
            self.assertEqual(repeated['activities'][0]['datetime']['start_local'][-6:], '+04:00')

    def test_patch_merges_without_erasing_unmentioned_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = synthetic_tcx(root/'in'/'run.tcx')
            w = root/'local-data'
            self.assertEqual(self.execute(workflow_main,'ingest','--workspace',w,path)[0],0)
            patch=root/'patch.json'
            patch.write_text('{"subjective":{"foot_pain":false,"notes":"first"}}','utf-8')
            call=['--report',w/'running-activities.json','--metadata',w/'running-metadata.json',
                  '--file','run.tcx','--patch',patch]
            self.assertEqual(self.execute(metadata_main,*call)[0],0)
            old=(w/'running-metadata.json').read_bytes()
            self.assertEqual(self.execute(metadata_main,*call)[0],0)
            self.assertEqual((w/'running-metadata.json').read_bytes(),old)
            patch.write_text('{"subjective":{"overall_fatigue":"none"}}','utf-8')
            self.assertEqual(self.execute(metadata_main,*call)[0],0)
            j=json.loads((w/'running-metadata.json').read_text('utf-8'))['files']['run.tcx']
            self.assertEqual(j['subjective'],{'foot_pain':False,'notes':'first','overall_fatigue':'none'})
            self.assertEqual(len(j['identity']['sha256']),64)

    def test_identity_conflict_refuses_update_and_keeps_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inp=synthetic_tcx(root/'input'/'one.tcx');w=root/'local-data'
            self.assertEqual(self.execute(workflow_main,'ingest','--workspace',w,inp)[0],0)
            patch=root/'patch.json';patch.write_text('{"subjective":{"foot_pain":false}}','utf-8')
            kwargs=['--report',w/'running-activities.json','--metadata',w/'running-metadata.json',
                    '--file','one.tcx','--patch',patch]
            self.assertEqual(self.execute(metadata_main,*kwargs)[0],0)
            before=(w/'running-metadata.json').read_bytes()
            raw=json.loads((w/'running-activities.json').read_text('utf-8'))
            raw['activities'][0]['source']['sha256']='a'*64
            (w/'running-activities.json').write_text(json.dumps(raw),'utf-8')
            code,_,err=self.execute(metadata_main,*kwargs)
            self.assertEqual(code,2)
            self.assertIn('identity conflict',err)
            self.assertEqual(before,(w/'running-metadata.json').read_bytes())
            code,_,err=self.execute(workflow_main,'rebuild','--workspace',w)
            self.assertEqual(code,0,err)  # original TCX still matches metadata

    def test_bad_patch_keeps_existing_metadata_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inp=synthetic_tcx(root/'in'/'one.tcx');w=root/'local-data'
            self.assertEqual(self.execute(workflow_main,'ingest','--workspace',w,inp)[0],0)
            hist=(w/'running-history.json').read_bytes()
            patch=root/'bad.json';patch.write_text('{"subjective":{"foot_pain":null}}','utf-8')
            code,_,_=self.execute(metadata_main,'--report',w/'running-activities.json',
                  '--metadata',w/'running-metadata.json','--file','one.tcx','--patch',patch)
            self.assertEqual(code,2)
            self.assertFalse((w/'running-metadata.json').exists())
            self.assertEqual(hist,(w/'running-history.json').read_bytes())

    def test_different_file_same_basename_refused_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            one=synthetic_tcx(root/'a'/'one.tcx')
            two=synthetic_tcx(root/'b'/'one.tcx',pattern=[('walk',300,100,95)])
            w=root/'local-data'
            self.assertEqual(self.execute(workflow_main,'ingest','--workspace',w,one)[0],0)
            contents=(w/'tcx'/'one.tcx').read_bytes()
            history=(w/'running-history.json').read_bytes()
            code,_,err=self.execute(workflow_main,'ingest','--workspace',w,two)
            self.assertEqual(code,2)
            self.assertIn('filename conflict',err)
            self.assertEqual(contents,(w/'tcx'/'one.tcx').read_bytes())
            self.assertEqual(history,(w/'running-history.json').read_bytes())

    def test_bad_identity_blocks_rebuild_without_overwriting_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inp=synthetic_tcx(root/'in'/'one.tcx');w=root/'local-data'
            self.assertEqual(self.execute(workflow_main,'ingest','--workspace',w,inp)[0],0)
            before=(w/'running-history.json').read_bytes()
            (w/'running-metadata.json').write_text(json.dumps({'files':{'one.tcx':{'identity':{
               'activity_id':'wrong','sha256':'a'*64},'subjective':{'foot_pain':False}}}}),'utf-8')
            code,_,err=self.execute(workflow_main,'rebuild','--workspace',w)
            self.assertEqual(code,2)
            self.assertIn('analyzer failed',err)
            self.assertEqual(before,(w/'running-history.json').read_bytes())

    def test_renamed_byte_identical_tcx_does_not_duplicate_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=synthetic_tcx(root/'in'/'one.tcx')
            renamed=root/'in'/'copy.tcx';renamed.write_bytes(original.read_bytes())
            w=root/'local-data'
            code, out, error=self.execute(workflow_main,'ingest','--workspace',w,original,renamed)
            self.assertEqual(code,0,error)
            self.assertIn('1 new, 1 already present',out)
            self.assertEqual(len(list((w/'tcx').iterdir())),1)
            self.assertEqual(json.loads((w/'running-history.json').read_text('utf-8'))['summary']['files_found'],1)

    def test_timezone_change_requires_explicit_workspace_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);inp=synthetic_tcx(root/'in'/'one.tcx');w=root/'local-data'
            self.assertEqual(self.execute(workflow_main,'ingest','--workspace',w,'--tz-offset','+04:00',inp)[0],0)
            code,_,error=self.execute(workflow_main,'ingest','--workspace',w,'--tz-offset','+01:00',inp)
            self.assertEqual(code,2)
            self.assertIn('timezone differs',error)


if __name__ == '__main__':
    unittest.main()
