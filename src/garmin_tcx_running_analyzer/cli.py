"""Command-line interface: one file -> one JSON; folder -> ONE aggregated JSON."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, date
import glob
import json
import math
from pathlib import Path
import statistics
import sys

from .core import ET, VERSION, parse_tz, summarize

SUFFIXES = (".tcx", ".tcx.xml")
SENSORS = ("polar_h10", "wrist_optical", "other_chest", "unknown")


def positive_number(value: str) -> float:
    try:
        n = float(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("expected a positive number") from e
    if not math.isfinite(n) or n <= 0:
        raise argparse.ArgumentTypeError("expected a positive finite number")
    return n


def nonnegative_number(value: str) -> float:
    try:
        n = float(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("expected a nonnegative number") from e
    if not math.isfinite(n) or n < 0:
        raise argparse.ArgumentTypeError("expected a nonnegative finite number")
    return n


def is_tcx(path: Path) -> bool:
    return path.name.lower().endswith(SUFFIXES)


def find_files(inputs: list[str], recursive: bool) -> list[Path]:
    matches: set[Path] = set()
    for value in inputs:
        path = Path(value).expanduser()
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            matches.update(x.resolve() for x in iterator if x.is_file() and is_tcx(x))
        elif any(c in value for c in "*?[]"):
            matches.update(Path(x).resolve() for x in glob.glob(value, recursive=recursive)
                           if Path(x).is_file() and is_tcx(Path(x)))
        elif path.is_file():
            if not is_tcx(path):
                raise ValueError(f"Not a TCX file: {path}")
            matches.add(path.resolve())
        else:
            raise FileNotFoundError(f"Input does not exist: {path}")
    return sorted(matches, key=lambda p: (str(p).lower(), str(p)))


def parse_run_windows(spec: str | None):
    if not spec:
        return None
    def seconds(clock: str) -> int:
        parts = clock.strip().split(":")
        if len(parts) != 3 or not all(p.isdecimal() for p in parts):
            raise ValueError("run windows must be HH:MM:SS-HH:MM:SS")
        h, m, s = map(int, parts)
        if m > 59 or s > 59:
            raise ValueError("minutes and seconds must be less than 60")
        return h * 3600 + m * 60 + s
    ranges = []
    for item in spec.split(","):
        if item.count("-") != 1:
            raise ValueError("invalid run window, expected HH:MM:SS-HH:MM:SS")
        left, right = item.split("-", 1)
        a, b = seconds(left), seconds(right)
        if a >= b or (ranges and a < ranges[-1][1]):
            raise ValueError("run windows must be non-overlapping and chronological")
        ranges.append((a, b))
    return ranges



def metadata_windows(value):
    """Per-file windows as HH:MM:SS string or [{start_s,end_s}, ...]."""
    if isinstance(value, str):
        result = parse_run_windows(value)
        if not result:
            raise ValueError('run_windows cannot be empty')
        return result
    if not isinstance(value, list) or not value:
        raise ValueError('run_windows must be a nonempty string or array of {start_s,end_s}')
    result=[]
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {'start_s', 'end_s'}:
            raise ValueError('run_windows entries must have exactly start_s and end_s')
        a,b=entry['start_s'],entry['end_s']
        for x in (a,b):
            if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):
                raise ValueError('run_windows boundaries must be finite seconds')
        if a<0 or b<=a or (result and a<result[-1][1]):
            raise ValueError('run_windows must be chronological, nonnegative and non-overlapping')
        result.append((a,b))
    return result


def normalized_name(value: str) -> str:
    """Manifest-relative POSIX path; do not allow absolute or traversal paths."""
    if not isinstance(value,str) or not value.strip():
        raise ValueError('expected filenames must be nonempty strings')
    v=value.strip().replace('\\','/')
    if v.startswith('/') or ':' in v or any(x in ('.','..','') for x in v.split('/')):
        raise ValueError(f'invalid expected filename: {value!r}')
    if not is_tcx(Path(v)):
        raise ValueError(f'expected filename must end in .tcx or .tcx.xml: {v}')
    return v


def read_expected_manifest(path: Path | None) -> list[str] | None:
    if path is None: return None
    if path.suffix.lower()=='.json':
        doc=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(doc,dict) or not isinstance(doc.get('expected_files'),list):
            raise ValueError('expected manifest JSON must contain expected_files array')
        names=doc['expected_files']
    else:
        names=[v.strip() for v in path.read_text(encoding='utf-8-sig').splitlines()
               if v.strip() and not v.lstrip().startswith('#')]
    result=[normalized_name(v) for v in names]
    if not result:
        raise ValueError('expected manifest contains no filenames')
    if len(result)!=len(set(result)):
        raise ValueError('expected manifest contains duplicate paths')
    return result


def date_gap_report(activities: list[dict], min_gap_days: int) -> list[dict]:
    """Observed breaks between dates; never claims that a workout is missing."""
    days=sorted({date.fromisoformat(r['datetime']['start_local'][:10]) for r in activities})
    return [{'from_date':str(a),'to_date':str(b),'days_between':(b-a).days}
            for a,b in zip(days,days[1:]) if (b-a).days >= min_gap_days]


def archive_completeness(files: list[Path], root: Path, expected: list[str] | None) -> dict:
    if expected is None:
        return {'status':'not_assessed', 'expected_count':None, 'matched_count':None,
                'missing_files':[], 'unexpected_files':[],
                'note':'Without an expected-file manifest, finding every file in the folder does not prove the archive is complete.'}
    actual=set()
    for f in files:
        try: actual.add(f.relative_to(root).as_posix())
        except ValueError: actual.add(f.name)
    expected_set=set(expected)
    missing=sorted(expected_set-actual)
    unexpected=sorted(actual-expected_set)
    return {'status':'complete' if not missing else 'missing_expected_files',
            'expected_count':len(expected_set),'matched_count':len(expected_set & actual),
            'missing_files':missing,'unexpected_files':unexpected,
            'note':'Manifest checks input coverage, not whether TCX was successfully parsed; see activities_failed.'}


def read_metadata(path: Path | None) -> dict:
    if path is None:
        return {}
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict) or not isinstance(doc.get("files"), dict):
        raise ValueError('metadata must be a JSON object with a "files" mapping')
    for name, meta in doc["files"].items():
        if not isinstance(name, str) or not isinstance(meta, dict):
            raise ValueError('metadata "files" must map filenames to objects')
        unknown = set(meta) - {"treadmill_km", "run_speed_kmh", "hr_source", "subjective", "run_windows", "identity", "activity_mode"}
        if unknown:
            raise ValueError(f"unknown metadata properties for {name}: {sorted(unknown)}")
        for key in ("treadmill_km", "run_speed_kmh"):
            if key in meta and (not isinstance(meta[key], (int, float)) or isinstance(meta[key], bool)
                                or not math.isfinite(meta[key]) or meta[key] <= 0):
                raise ValueError(f"{name}.{key} must be a positive number")
        if 'run_windows' in meta:
            try: meta['run_windows'] = metadata_windows(meta['run_windows'])
            except ValueError as exc: raise ValueError(f'{name}.run_windows: {exc}') from exc
        if 'activity_mode' in meta and meta['activity_mode'] not in ('auto','treadmill','outdoor','unknown'):
            raise ValueError(f'unknown activity_mode in metadata for {name}')
        if "hr_source" in meta and meta["hr_source"] not in SENSORS:
            raise ValueError(f"unknown hr_source in metadata for {name}")
        if "identity" in meta:
            identity = meta["identity"]
            if not isinstance(identity, dict) or set(identity) != {"activity_id", "sha256"}:
                raise ValueError(f"{name}.identity requires activity_id and sha256")
            if not isinstance(identity["activity_id"], str) or not identity["activity_id"]:
                raise ValueError(f"{name}.identity.activity_id must be a nonempty string")
            sha = identity["sha256"]
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError(f"{name}.identity.sha256 must be a lowercase SHA-256 hex string")
        if "subjective" in meta:
            subj = meta["subjective"]
            if not isinstance(subj, dict):
                raise ValueError(f"subjective must be a JSON object for {name}")
            valid = {"foot_pain", "foot_fatigue", "heel_pain", "calf_fatigue", "back_pain", "overall_fatigue", "notes"}
            if set(subj) - valid:
                raise ValueError(f"unknown subjective properties for {name}")
    return doc["files"]


def apply_subjective(report: dict, values: dict):
    for k, v in values.items():
        if v is not None and not isinstance(v, (bool, str, int, float)):
            raise ValueError(f"invalid subjective value for {k}")
        report["subjective"][k] = v
    if values:
        report["subjective"]["provenance"] = "user_supplied_metadata"


def resolve_activity_identities(activities: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Deduplicate likely re-exports; never drop a conflicting Garmin activity ID.

    All file reports stay in `activities` with transparent provenance. Only
    statistically equivalent IDs count once in aggregate exercise statistics.
    """
    groups = {}
    for a in activities:
        key = a['source']['activity_id']
        groups.setdefault(key, []).append(a)
    unique, duplicates, collisions = [], [], []
    for activity_id, group in groups.items():
        if len(group) == 1:
            group[0]['source']['identity_status'] = 'unique'
            unique.extend(group)
            continue
        baseline = group[0]['total']
        sport = group[0]['source'].get('sport')
        distance = baseline.get('garmin_distance_m')
        duration = baseline.get('recorded_duration_s')
        def equivalent(row):
            dd = row['total'].get('garmin_distance_m')
            dt = row['total'].get('recorded_duration_s')
            return (row['source'].get('sport') == sport and
                    distance is not None and dd is not None and
                    duration is not None and dt is not None and
                    abs(distance-dd) <= max(25, distance*0.002) and
                    abs(duration-dt) <= max(10, duration*0.001))
        if all(equivalent(row) for row in group):
            # Prefer richer GPS and HR data, then sample count; lexical tie break.
            representative = sorted(group, key=lambda a: (
                -a['quality'].get('gps_points',0),
                -(a['quality']['trackpoints_unique']-a['quality']['missing_hr_points']),
                -a['quality']['trackpoints_unique'],
                -len(a.get('lap_metadata',[])),
                a['source']['filename']))[0]
            unique.append(representative)
            representative['source']['identity_status'] = 'canonical'
            for row in group:
                if row is representative: continue
                row['source']['identity_status'] = 'duplicate_export'
                row['source']['duplicate_of'] = representative['source']['filename']
            duplicates.append({'activity_id':activity_id,
                               'canonical_file':representative['source']['filename'],
                               'duplicate_files':[r['source']['filename'] for r in group if r is not representative],
                               'reason':'matching_Garmin_ID_distance_and_elapsed_time'})
        else:
            # Never silently merge diverging exports sharing an ID.
            unique.extend(group)
            collisions.append({'activity_id':activity_id,
                               'files':[r['source']['filename'] for r in group],
                               'reason':'same_ID_but_distance_or_duration_differs'})
            for row in group: row['source']['identity_status'] = 'id_conflict'
    return unique, duplicates, collisions


def batch_summary(activities: list[dict], files_found: int, errors: list[dict], raw_count: int | None = None) -> dict:
    dated = sorted(activities, key=lambda r: (r["datetime"]["start_utc"] or "", r["source"]["filename"]))
    duration = sum(r["total"]["run_duration_s"] or 0 for r in activities)
    hr_vals = [(r["total"]["run_hr_avg_bpm"], r["total"]["run_duration_s"])
               for r in activities if r["total"]["run_hr_avg_bpm"] is not None and (r["total"]["run_duration_s"] or 0) > 0]
    cadence_vals = [(r["total"]["run_cadence_avg_spm"], r["total"]["run_duration_s"])
                    for r in activities if r["total"]["run_cadence_avg_spm"] is not None and (r["total"]["run_duration_s"] or 0) > 0]
    def weighted(values):
        return round(sum(v*w for v,w in values)/sum(w for v,w in values), 1) if values else None
    hr_sources = Counter(r["source"]["hr_sensor"]["value"] for r in activities)
    return {
        "files_found":files_found,
        "activities_succeeded":raw_count if raw_count is not None else len(activities),
        "activities_failed":len(errors),
        "unique_activities_counted":len(activities),
        "activity_date_first_local":dated[0]["datetime"]["start_local"] if dated else None,
        "activity_date_last_local":dated[-1]["datetime"]["start_local"] if dated else None,
        "total_running_minutes":round(duration / 60, 2),
        "total_running_blocks":sum(r["total"]["run_count"] for r in activities),
        "longest_continuous_run_s":max((r["total"]["longest_continuous_run_s"] for r in activities),default=0),
        "running_hr_avg_bpm_duration_weighted":weighted(hr_vals),
        "running_cadence_avg_spm_duration_weighted":weighted(cadence_vals),
        "running_hr_max_bpm":max((r["total"]["run_hr_max_bpm"] for r in activities if r["total"]["run_hr_max_bpm"] is not None), default=None),
        "activities_by_hr_source":dict(sorted(hr_sources.items())),
        "activities_with_quality_warnings":sum(bool(r["quality"]["warnings"]) for r in activities),
        "activities_with_actionable_warnings":sum(r["quality"]["warning_count"]>0 for r in activities),
        "quality_issue_counts_by_severity":dict(sorted(Counter(
            issue['severity'] for r in activities for issue in r['quality']['issues']).items())),
        "quality_issue_counts_by_code":dict(sorted(Counter(
            issue['code'] for r in activities for issue in r['quality']['issues']).items())),
        "run_detection_confidence_counts":dict(sorted(Counter(
            r['quality']['run_detection_confidence'] for r in activities).items())),
        "notes":["Weighted averages are descriptive only; compare similar sessions and HR sensors.",
                 "A TCX collection does not measure pain, effort, treadmill calibration or confirmed speed."]
    }


def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser(prog="garmin-tcx-running-analyzer",
        description="Analyze one Garmin TCX or a folder/archive. Folder mode creates ONE comprehensive JSON.")
    ap.add_argument("inputs", nargs="+", help="TCX files, folders, or globs (all results go into ONE JSON)")
    ap.add_argument("-o", "--output", help="output JSON file; default: <file>.running.json or <folder>/running-activities.json")
    ap.add_argument("--recursive", action="store_true", help="include TCX files in subfolders")
    ap.add_argument("--tz-offset", type=parse_tz, default=parse_tz("+00:00"), help="local UTC offset, e.g. +04:00 (default +00:00)")
    ap.add_argument("--treadmill-km", type=positive_number, help="whole treadmill session distance; only for one file")
    ap.add_argument("--run-speed-kmh", type=positive_number, help="confirmed treadmill running speed; never inferred from Garmin")
    ap.add_argument("--hr-source", choices=SENSORS, default="unknown", help="manual sensor label, not detected from TCX")
    ap.add_argument("--activity-mode", choices=('auto','treadmill','outdoor','unknown'), default='auto',
                    help="training environment; auto uses treadmill input or GPS evidence")
    ap.add_argument("--metadata", type=Path, help="optional JSON file mapping filenames to per-workout overrides and feelings")
    ap.add_argument("--run-cadence-threshold", type=positive_number, default=145, help="cadence threshold, steps/min")
    ap.add_argument("--min-run-seconds", type=positive_number, default=45, help="shorter segments ignored")
    ap.add_argument("--join-gap-seconds", type=nonnegative_number, default=12, help="max seconds to join adjacent run fragments")
    ap.add_argument("--run-windows", help="manual run windows relative to activity start (one file only); batch uses metadata run_windows")
    ap.add_argument('--expected-manifest', type=Path, help='optional .json or .txt expected TCX file list; archive coverage check')
    ap.add_argument('--date-gap-days', type=int, default=7, help='report observed gaps of N+ days between workout dates (default 7)')
    args=ap.parse_args(argv)
    try:
        if args.date_gap_days < 1:
            raise ValueError('--date-gap-days must be an integer >= 1')
        files=find_files(args.inputs, args.recursive)
        if not files:
            raise ValueError("No .tcx or .tcx.xml files found")
        folders=any(Path(x).expanduser().is_dir() for x in args.inputs)
        multi=folders or len(files)>1 or len(args.inputs)>1
        if multi and args.treadmill_km is not None:
            raise ValueError("--treadmill-km applies to a single file; use --metadata for batch distances")
        if multi and args.run_windows:
            raise ValueError("--run-windows applies to a single file only")
        metadata=read_metadata(args.metadata)
        expected=read_expected_manifest(args.expected_manifest)
        if expected is not None and not multi:
            raise ValueError('--expected-manifest requires folder or multi-file mode')
        if len(set(f.name for f in files)) < len(files) and metadata:
            raise ValueError("duplicate basenames in the batch; --metadata requires unique filenames")
        windows=parse_run_windows(args.run_windows)
        if args.output:
            outfile=Path(args.output).expanduser().resolve()
            if outfile.suffix.lower() != '.json':
                raise ValueError("--output must name a .json file, not a directory")
        elif multi:
            base=Path(args.inputs[0]).expanduser()
            outfile=(base if base.is_dir() else base.parent)/"running-activities.json"
            outfile=outfile.resolve()
        else:
            file=files[0]
            # Match v1 single-file naming: foo.tcx -> foo.running.json,
            # foo.tcx.xml -> foo.tcx.running.json.
            outfile=file.with_name(file.stem + ".running.json")
        if outfile in files:
            raise ValueError("output path must differ from every TCX input")
        settings={"threshold":args.run_cadence_threshold,"min_seconds":args.min_run_seconds,"join_gap":args.join_gap_seconds}
        activities=[]
        errors=[]
        for f in files:
            try:
                m=metadata.get(f.name,{})
                sp=m.get("run_speed_kmh",args.run_speed_kmh)
                km=m.get("treadmill_km",args.treadmill_km)
                sensor=m.get("hr_source",args.hr_source)
                file_windows=m.get('run_windows',windows)
                report=summarize(f,args.tz_offset,sp,km,sensor,settings,file_windows,m.get('activity_mode',args.activity_mode))
                identity=m.get('identity')
                if identity and (identity['activity_id'] != report['source']['activity_id']
                                 or identity['sha256'] != report['source']['sha256']):
                    raise ValueError(f"metadata identity mismatch: {f.name}; refusing to apply metadata for a different TCX")
                if "subjective" in m:
                    apply_subjective(report,m["subjective"])
                if multi:
                    # Filename-relative location is useful when recursive filenames differ.
                    root=Path(args.inputs[0]).expanduser()
                    try:
                        report["source"]["relative_path"]=f.relative_to(root.resolve()).as_posix()
                    except ValueError:
                        report["source"]["relative_path"]=f.name
                activities.append(report)
                print(f"OK {f.name}: {report['total']['run_count']} running segments",file=sys.stderr)
            except (OSError,ValueError,ET.ParseError) as exc:
                errors.append({"filename":f.name,"error":str(exc)})
                print(f"ERROR {f.name}: {exc}",file=sys.stderr)
        activities.sort(key=lambda r: (r["datetime"]["start_utc"] or "",r["source"].get("relative_path",r["source"]["filename"])))
        if multi:
            batch_root=Path(args.inputs[0]).expanduser().resolve()
            if not batch_root.is_dir(): batch_root=batch_root.parent
            unique, duplicate_groups, id_conflicts = resolve_activity_identities(activities)
            summary=batch_summary(unique,len(files),errors,raw_count=len(activities))
            summary['duplicate_activity_groups']=duplicate_groups
            summary['duplicate_exports_excluded']=sum(len(g['duplicate_files']) for g in duplicate_groups)
            summary['activity_id_conflicts']=id_conflicts
            summary['activity_id_conflict_count']=len(id_conflicts)
            summary['duplicate_policy']='Only Garmin IDs with agreeing distance and elapsed duration are merged for aggregate stats; all reports remain visible.' 
            summary['archive_completeness']=archive_completeness(files,batch_root,expected)
            summary['observed_date_gaps']=date_gap_report(unique,args.date_gap_days)
            summary['date_gap_note']='Observed gaps are not proof of missing workouts; planned rest periods are normal.'
            report={"schema_version":"1.0","report_type":"tcx_running_collection",
                    "generator":{"name":"garmin-tcx-running-analyzer","version":VERSION},
                    "source":{"mode":"directory_or_multiple_files","recursive":args.recursive,
                              "source_label":Path(args.inputs[0]).name},
                    "summary":summary,
                    "activities":activities,"errors":errors}
        elif activities:
            report=activities[0]
        else:
            return 1
        outfile.parent.mkdir(parents=True,exist_ok=True)
        outfile.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        print(f"Written {outfile} | workouts={len(activities)} | failed={len(errors)}")
        return 1 if errors else 0
    except (OSError,ValueError,ET.ParseError,json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
