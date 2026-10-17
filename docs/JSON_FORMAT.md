# JSON output format (schema v1.0)

The script does **not** prescribe a specific training program. JSON contains measurements or technical calculations only.

## Single file

One activity JSON has the following top-level fields:

| Field | Content |
| --- | --- |
| `schema_version` | `"1.0"` |
| `generator` | Analyzer/version |
| `source` | Original filename, SHA-256, Garmin activity ID, sport, manually declared HR source |
| `datetime` | UTC/local start timestamp and day type |
| `total` | Total recorded/actual running duration, count, running HR, cadence and Garmin distance |
| `warmup_last5min_before_running` | Five-minute pre-run HR trend (not guaranteed to be on the treadmill) |
| `runs` | **All** detected run segments, with half averages and five-minute splits |
| `recoveries_between_runs` | HR recovery during walking/rest between runs |
| `cooldown_first5min_after_running` | HR recovery after the last run |
| `lap_metadata` | Original Garmin laps and their stats |
| `quality` | Missing readings, boundary flags and warnings |
| `subjective` | `null` placeholders; filled **only** using explicit per-file metadata |
| `interpretation_rules` | Caveats about technical vs. medical interpretation |

Intervals contain seconds, local timestamps, average/max HR (bpm), cadence in **steps/min** and Garmin/expected treadmill distances. `runs[].five_minute_splits` includes partial final splits where needed.

## Folder or multiple files: a single JSON

```json
{
  "schema_version": "1.0",
  "report_type": "tcx_running_collection",
  "generator": {"name": "garmin-tcx-running-analyzer", "version": "1.1.0"},
  "source": {"mode": "directory_or_multiple_files", "recursive": false, "source_label": "workouts"},
  "summary": {
    "files_found": 2,
    "activities_succeeded": 2,
    "activities_failed": 0,
    "total_running_minutes": 60.0,
    "running_hr_avg_bpm_duration_weighted": 125.4
  },
  "activities": [
    {"schema_version": "1.0", "source": {"filename": "..."}, "total": {}, "runs": []}
  ],
  "errors": []
}
```

The example above illustrates only the shape, not a full output. Each object inside `activities` actually holds the **complete single-file report**. `summary` contains period statistics; activities are sorted by UTC start time. If a file cannot be parsed, the collection includes its filename/error and exits nonzero, but preserves the successfully parsed activities.

### Summary interpretation

- `running_hr_avg_bpm_duration_weighted`: mean of **rounded** per-activity running HR averages weighted by running time; descriptive aggregate, **not** clinically meaningful on its own.
- `activities_by_hr_source`: sources **supplied by users**, not auto-detected; do not mix different sensor types without noting this.
- `activities_with_quality_warnings`: includes informational distance/sensor warnings. Read each `quality.warnings` item.

## Missing and uncertain data

- `null` means not available: it does *not* mean zero.
- Garmin indoor speed/distance is an estimate and can change after watch calibration.
- `--run-speed-kmh` is a user-supplied constant for expected running distance, **not inferred**.
- `--treadmill-km` is the actual **whole treadmill workout** distance, *not* the running-only distance.
- Run interval boundaries use cadence + Garmin laps; verify manually for unusual workouts.
- TCX generally does not reveal whether the HR source was Polar H10 or wrist optical.
- Never infer pain/fatigue from trackpoints or a normal-looking HR trace.

## Compatibility

Single-file JSON preserves the original v1.0 keys. Collection JSON is a new container format in v1.1. New fields may be added in later backwards-compatible minor releases.
