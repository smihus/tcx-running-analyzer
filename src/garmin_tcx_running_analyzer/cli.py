"""Command-line interface: one file -> one JSON; folder -> ONE aggregated JSON."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
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


def read_metadata(path: Path | None) -> dict:
    if path is None:
        return {}
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict) or not isinstance(doc.get("files"), dict):
        raise ValueError('metadata must be a JSON object with a "files" mapping')
    for name, meta in doc["files"].items():
        if not isinstance(name, str) or not isinstance(meta, dict):
            raise ValueError('metadata "files" must map filenames to objects')
        unknown = set(meta) - {"treadmill_km", "run_speed_kmh", "hr_source", "subjective"}
        if unknown:
            raise ValueError(f"unknown metadata properties for {name}: {sorted(unknown)}")
        for key in ("treadmill_km", "run_speed_kmh"):
            if key in meta and (not isinstance(meta[key], (int, float)) or isinstance(meta[key], bool)
                                or not math.isfinite(meta[key]) or meta[key] <= 0):
                raise ValueError(f"{name}.{key} must be a positive number")
        if "hr_source" in meta and meta["hr_source"] not in SENSORS:
            raise ValueError(f"unknown hr_source in metadata for {name}")
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


def batch_summary(activities: list[dict], files_found: int, errors: list[dict]) -> dict:
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
        "files_found":files_found, "activities_succeeded":len(activities), "activities_failed":len(errors),
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
    ap.add_argument("--metadata", type=Path, help="optional JSON file mapping filenames to per-workout overrides and feelings")
    ap.add_argument("--run-cadence-threshold", type=positive_number, default=145, help="cadence threshold, steps/min")
    ap.add_argument("--min-run-seconds", type=positive_number, default=45, help="shorter segments ignored")
    ap.add_argument("--join-gap-seconds", type=nonnegative_number, default=12, help="max seconds to join adjacent run fragments")
    ap.add_argument("--run-windows", help="manual run windows relative to activity start (one file only)")
    args=ap.parse_args(argv)
    try:
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
                report=summarize(f,args.tz_offset,sp,km,sensor,settings,windows)
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
            report={"schema_version":"1.0","report_type":"tcx_running_collection",
                    "generator":{"name":"garmin-tcx-running-analyzer","version":VERSION},
                    "source":{"mode":"directory_or_multiple_files","recursive":args.recursive,
                              "source_label":Path(args.inputs[0]).name},
                    "summary":batch_summary(activities,len(files),errors),
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
