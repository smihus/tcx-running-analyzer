# JSON output format (schema v1.0, additive fields in tool v1.2.1)

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
  "generator": {"name": "garmin-tcx-running-analyzer", "version": "1.2.0"},
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

### New v1.2.0 quality fields (backward compatible)

Existing JSON keys including `quality.warnings` and `summary.activities_with_quality_warnings` are retained. New fields are additive; `schema_version` remains `1.0`.

- `quality.issues[]`: objects `{code, severity, description}` where severity is `warning` (something to verify) or `info` (missing context such as unknown HR sensor, or explanation of treadmill-distance provenance). Legacy `quality.warnings[]` remains unchanged for existing consumers, including informational items.
- `quality.warning_count` and `quality.info_count`: separate severity counts.
- `quality.hr_abrupt_jumps[]`: every >=12 bpm change between adjacent one-second HR samples; `time_utc`, `time_local`, signed `delta_bpm`, `absolute_delta_bpm`, `hr_previous_bpm`, `hr_current_bpm`, `phase` (`running`, `pre_run_5min`, `before_running`, `between_runs`, `post_run_5min`, `after_running`, or `unclassified`) and `run_index` (1-based when running). Flags are **not evidence of a sensor error or illness on their own**.
- `runs[].detection`: `{confidence, method, reason, cadence_support_fraction, running_lap_coverage_fraction, boundary_shift_max_abs_s}`. Confidence is **heuristic** (`high`/`medium`/`low`) and is **not a probability**. For explicit overrides, confidence is `manual_override`; it means user-supplied, not verified. `quality.run_detection_confidence` is an aggregate category (`none` for no detected runs).
- `summary.activities_with_actionable_warnings`, `quality_issue_counts_by_severity`, `quality_issue_counts_by_code`, `run_detection_confidence_counts`: quality aggregation excluding informational messages from actionable counts.
- `summary.archive_completeness`: `status` is `not_assessed` without a manifest; with one, `complete` (no missing expected files) or `missing_expected_files`. Includes `expected_count`, `matched_count`, `missing_files`, `unexpected_files` and a note. Even `complete` checks only **filenames**, not successful parsing (check `activities_failed` separately).
- `summary.observed_date_gaps[]`: calendar gaps of at least `--date-gap-days` days between **different recorded workout dates**. Gaps are observations, **not proof of missing training**.

### New v1.2.1 additive diagnostics

- `quality.hr_jump_episodes[]` groups adjacent (exactly consecutive seconds), same-direction threshold-crossing changes within the same workout phase. For each episode, `start_utc`/`start_local` denotes the **sample before** the first jump and `end_utc`/`end_local` denotes the last jumped-to sample; includes `direction`, `hr_start_bpm`, `hr_end_bpm`, `net_delta_bpm`, `duration_s` and `jump_samples`. **These are the seconds during which abrupt changes occurred**, *not* how long the pulse remained high. All original raw events remain in `quality.hr_abrupt_jumps`.
- `quality.hr_jump_episode_count` counts these grouped events. A jump event is a measurement observation and not, by itself, evidence of a sensor fault or medical issue.
- `quality.unclassified_low_cadence_laps[]` lists manual-lap review candidates when no running intervals were found and Garmin lap average cadence is between 110 spm (inclusive) and the configured running threshold (exclusive). These laps are **not** automatically counted as runs. E.g. a March workout with 128 spm and anomalous HR can be walking or mixed; validate from training notes or use manually verified `run_windows` metadata.

### Metadata run windows and completeness manifests

Per-file metadata may include `run_windows`, for example:

```json
{"files":{"unusual.tcx":{"run_windows":[{"start_s":300,"end_s":600}]}}}
```

An equivalent string value `"00:05:00-00:10:00"` is supported. Boundaries are **seconds after the Garmin activity start**, must be sorted and non-overlapping, and must lie within available trackpoints. The override applies only to that file. Metadata is keyed by unique basename in a recursive archive.

An expected-file manifest has the JSON form `{"expected_files":["subfolder/one.tcx","two.tcx"]}`; alternatively use a UTF-8 `.txt` with one relative path per line and `#` comments. Comparison uses paths relative to the first scanned directory. A filename not present in the manifest is shown as `unexpected_files` and is still analyzed.

### Summary interpretation

- `running_hr_avg_bpm_duration_weighted`: mean of **rounded** per-activity running HR averages weighted by running time; descriptive aggregate, **not** clinically meaningful on its own.
- `activities_by_hr_source`: sources **supplied by users**, not auto-detected; do not mix different sensor types without noting this.
- `activities_with_quality_warnings`: legacy count including informational messages; use new `activities_with_actionable_warnings` to see only actual warning-severity items.

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


## v1.3.0 private workflow and optional metadata identity

A recommended agent workflow saves three JSON files under a **private** workspace:

- `running-activities.json` — pure TCX/analyzer measurements (the original collection schema).
- `running-metadata.json` — user-confirmed data (compatible existing `files` mapping).
- `running-history.json` — re-generated collection JSON that merges explicit metadata into the original report format; no independent hand-edited measurement schema is introduced.

Agent-safe upsert may add an optional `identity` alongside supported per-file metadata keys:

```json
{
  "files": {
    "synthetic-example.tcx": {
      "identity": {
        "activity_id": "2026-01-01T16:00:00.000Z",
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
      },
      "hr_source": "polar_h10",
      "subjective": {"foot_pain": false}
    }
  }
}
```

The example identity above is **illustrative, not a real TCX match**; the update helper always copies exact identity fields from an actual analyzer report. During subsequent analyses a mismatch in either `activity_id` or SHA-256 prevents attaching metadata to a different file. Legacy metadata without identity remains accepted. The analyzer does not infer a sensor or symptoms from TCX. Missing `running-metadata.json` is normal before the user supplies any facts.

Commands and error-handling guarantees: [`AGENT_WORKFLOW.md`](AGENT_WORKFLOW.md) and [`AGENT_WORKFLOW.ru.md`](AGENT_WORKFLOW.ru.md).
