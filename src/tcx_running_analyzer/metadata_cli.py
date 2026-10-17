"""Safe, idempotent user-metadata updates based on an analyzer report.

Usage: python -m tcx_running_analyzer.metadata_cli --report RAW_JSON
       --metadata METADATA_JSON --file TCX_BASENAME --patch PATCH_JSON

PATCH_JSON contains only fields explicitly confirmed by a user. Never infer
missing fields or overwrite other activity records.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import sys

from .cli import read_metadata, metadata_windows, SENSORS

FIELDS = {"treadmill_km", "run_speed_kmh", "hr_source", "subjective", "run_windows", "activity_mode"}
SUBJECTIVE = {"foot_pain", "foot_fatigue", "heel_pain", "calf_fatigue", "back_pain", "overall_fatigue", "notes"}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def report_activity(report: dict, filename: str) -> dict:
    if isinstance(report.get("activities"), list):
        records = report["activities"]
    elif isinstance(report.get("source"), dict):
        records = [report]
    else:
        raise ValueError("input must be an individual or collection analyzer report")
    records = [a for a in records if isinstance(a, dict) and a.get("source", {}).get("filename") == filename]
    if len(records) != 1:
        raise ValueError(f"expected exactly one report matching {filename!r}, found {len(records)}")
    source = records[0]["source"]
    if not source.get("sha256") or not source.get("activity_id"):
        raise ValueError("report is missing activity identity (source.sha256 and source.activity_id)")
    return records[0]


def validate_patch(patch: dict):
    if not patch or set(patch) - FIELDS:
        raise ValueError(f"patch must contain only these fields: {sorted(FIELDS)}")
    for key in ("treadmill_km", "run_speed_kmh"):
        if key in patch:
            import math
            x = patch[key]
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0:
                raise ValueError(f"{key} must be a positive finite number")
    if "activity_mode" in patch and patch["activity_mode"] not in ("auto", "treadmill", "outdoor", "unknown"):
        raise ValueError('activity_mode must be auto, treadmill, outdoor, or unknown')
    if "hr_source" in patch and patch["hr_source"] not in SENSORS:
        raise ValueError(f"hr_source must be one of {SENSORS}")
    if "run_windows" in patch:
        metadata_windows(patch["run_windows"])
    if "subjective" in patch:
        subj = patch["subjective"]
        if not isinstance(subj, dict) or not subj or set(subj) - SUBJECTIVE:
            raise ValueError(f"subjective must contain only known, nonempty fields: {sorted(SUBJECTIVE)}")
        for key, val in subj.items():
            if val is None or not isinstance(val, (str, bool)) or (isinstance(val, str) and not val.strip()):
                raise ValueError(f"subjective.{key} must be an explicit boolean or nonempty string")


def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".metadata-", suffix=".tmp", delete=False) as file:
            tmp = Path(file.name)
            json.dump(data, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        read_metadata(tmp)  # All-or-nothing validation before replacing the live file.
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def upsert(metadata_file: Path, report_file: Path, filename: str, patch_file: Path) -> bool:
    """Upsert explicitly supplied values; false if nothing changed.

    `identity` binds filename to the actual TCX activity and TCX checksum.
    A new/different TCX reusing the same basename can never silently inherit
    another workout's personal notes.
    """
    record = report_activity(load_json(report_file), filename)
    identity = {"activity_id": record["source"]["activity_id"],
                "sha256": record["source"]["sha256"]}
    patch = load_json(patch_file)
    validate_patch(patch)
    if metadata_file.exists():
        document = load_json(metadata_file)
        read_metadata(metadata_file)  # Validate all existing entries before any write.
    else:
        document = {"files": {}}
    files = document["files"]
    previous = files.get(filename, {})
    if previous.get("identity") and previous["identity"] != identity:
        raise ValueError(f"identity conflict for {filename}; refusing to attach notes to a different workout")
    updated = dict(previous)
    updated["identity"] = identity
    for key, value in patch.items():
        if key == "subjective":
            updated[key] = {**updated.get(key, {}), **value}
        else:
            updated[key] = value
    files[filename] = updated
    if files.get(filename) == previous:
        return False
    # Validate the complete document in a temporary file before atomic replacement.
    atomic_json(metadata_file, document)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Merge explicit user feedback into persistent running-metadata.json")
    ap.add_argument("--report", type=Path, required=True, help="raw analyzer JSON identifying the TCX")
    ap.add_argument("--metadata", type=Path, required=True, help="cumulative local metadata JSON")
    ap.add_argument("--file", required=True, help="exact TCX basename in report (not a path)")
    ap.add_argument("--patch", type=Path, required=True, help="JSON of confirmed values to merge")
    args = ap.parse_args(argv)
    try:
        changed = upsert(args.metadata, args.report, args.file, args.patch)
        print(f"Metadata {'updated' if changed else 'unchanged'}: {args.metadata} | {args.file}")
        return 0
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
