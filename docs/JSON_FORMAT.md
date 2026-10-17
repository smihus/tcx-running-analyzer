# JSON output format (schema v2.0, TCX Running Analyzer v1.4.0)

The script does **not** prescribe a specific training program. JSON contains measurements or technical calculations only.

## Single file

One activity JSON has the following top-level fields:

| Field | Content |
| --- | --- |
| `schema_version` | `"2.0"` |
| `generator` | Analyzer/version |
| `source` | Original filename, SHA-256, TCX activity ID, sport, manually declared HR source |
| `datetime` | UTC/local start timestamp and day type |
| `total` | Total recorded/actual running duration, count, running HR, cadence and TCX-reported distance |
| `warmup_last5min_before_running` | Five-minute pre-run HR trend (not guaranteed to be on the treadmill) |
| `runs` | **All** detected run segments, with half averages and five-minute splits |
| `recoveries_between_runs` | HR recovery during walking/rest between runs |
| `cooldown_first5min_after_running` | HR recovery after the last run |
| `lap_metadata` | Original TCX laps and their stats |
| `quality` | Missing readings, boundary flags and warnings |
| `subjective` | `null` placeholders; filled **only** using explicit per-file metadata |
| `interpretation_rules` | Caveats about technical vs. medical interpretation |

Intervals contain seconds, local timestamps, average/max HR (bpm), cadence in **steps/min** and TCX/expected treadmill distances. `runs[].five_minute_splits` includes partial final splits where needed.

## Folder or multiple files: a single JSON

```json
{
  "schema_version": "2.0",
  "report_type": "tcx_running_collection",
  "generator": {"name": "tcx-running-analyzer", "version": "1.4.0"},
  "source": {"mode": "directory_or_multiple_files", "recursive": false, "source_label": "workouts"},
  "summary": {
    "files_found": 2,
    "activities_succeeded": 2,
    "activities_failed": 0,
    "total_running_minutes": 60.0,
    "running_hr_avg_bpm_duration_weighted": 125.4
  },
  "activities": [
    {"schema_version": "2.0", "source": {"filename": "..."}, "total": {}, "runs": []}
  ],
  "errors": []
}
```

The example above illustrates only the shape, not a full output. Each object inside `activities` actually holds the **complete single-file report**. `summary` contains period statistics; activities are sorted by UTC start time. If a file cannot be parsed, the collection includes its filename/error and exits nonzero, but preserves the successfully parsed activities.

### Diagnostic fields introduced in v1.2.0

Diagnostic keys including `quality.warnings` remain available. Brand-neutral distance keys were renamed in the pre-release rebrand; `schema_version` is now `2.0`.

- `quality.issues[]`: objects `{code, severity, description}` where severity is `warning` (something to verify) or `info` (missing context such as unknown HR sensor, or explanation of treadmill-distance provenance). `quality.warnings[]` retains diagnostic messages, including informational items.
- `quality.warning_count` and `quality.info_count`: separate severity counts.
- `quality.hr_abrupt_jumps[]`: every >=12 bpm change between adjacent one-second HR samples; `time_utc`, `time_local`, signed `delta_bpm`, `absolute_delta_bpm`, `hr_previous_bpm`, `hr_current_bpm`, `phase` (`running`, `pre_run_5min`, `before_running`, `between_runs`, `post_run_5min`, `after_running`, or `unclassified`) and `run_index` (1-based when running). Flags are **not evidence of a sensor error or illness on their own**.
- `runs[].detection`: `{confidence, method, reason, cadence_support_fraction, running_lap_coverage_fraction, boundary_shift_max_abs_s}`. Confidence is **heuristic** (`high`/`medium`/`low`) and is **not a probability**. For explicit overrides, confidence is `manual_override`; it means user-supplied, not verified. `quality.run_detection_confidence` is an aggregate category (`none` for no detected runs).
- `summary.activities_with_actionable_warnings`, `quality_issue_counts_by_severity`, `quality_issue_counts_by_code`, `run_detection_confidence_counts`: quality aggregation excluding informational messages from actionable counts.
- `summary.archive_completeness`: `status` is `not_assessed` without a manifest; with one, `complete` (no missing expected files) or `missing_expected_files`. Includes `expected_count`, `matched_count`, `missing_files`, `unexpected_files` and a note. Even `complete` checks only **filenames**, not successful parsing (check `activities_failed` separately).
- `summary.observed_date_gaps[]`: calendar gaps of at least `--date-gap-days` days between **different recorded workout dates**. Gaps are observations, **not proof of missing training**.

### New v1.2.1 additive diagnostics

- `quality.hr_jump_episodes[]` groups adjacent (exactly consecutive seconds), same-direction threshold-crossing changes within the same workout phase. For each episode, `start_utc`/`start_local` denotes the **sample before** the first jump and `end_utc`/`end_local` denotes the last jumped-to sample; includes `direction`, `hr_start_bpm`, `hr_end_bpm`, `net_delta_bpm`, `duration_s` and `jump_samples`. **These are the seconds during which abrupt changes occurred**, *not* how long the pulse remained high. All original raw events remain in `quality.hr_abrupt_jumps`.
- `quality.hr_jump_episode_count` counts these grouped events. A jump event is a measurement observation and not, by itself, evidence of a sensor fault or medical issue.
- `quality.unclassified_low_cadence_laps[]` lists manual-lap review candidates when no running intervals were found and TCX lap average cadence is between 110 spm (inclusive) and the configured running threshold (exclusive). These laps are **not** automatically counted as runs. E.g. a March workout with 128 spm and anomalous HR can be walking or mixed; validate from training notes or use manually verified `run_windows` metadata.

### Metadata run windows and completeness manifests

Per-file metadata may include `run_windows`, for example:

```json
{"files":{"unusual.tcx":{"run_windows":[{"start_s":300,"end_s":600}]}}}
```

An equivalent string value `"00:05:00-00:10:00"` is supported. Boundaries are **seconds after the TCX activity start**, must be sorted and non-overlapping, and must lie within available trackpoints. The override applies only to that file. Metadata is keyed by unique basename in a recursive archive.

An expected-file manifest has the JSON form `{"expected_files":["subfolder/one.tcx","two.tcx"]}`; alternatively use a UTF-8 `.txt` with one relative path per line and `#` comments. Comparison uses paths relative to the first scanned directory. A filename not present in the manifest is shown as `unexpected_files` and is still analyzed.

### Summary interpretation

- `running_hr_avg_bpm_duration_weighted`: mean of **rounded** per-activity running HR averages weighted by running time; descriptive aggregate, **not** clinically meaningful on its own.
- `activities_by_hr_source`: sources **supplied by users**, not auto-detected; do not mix different sensor types without noting this.
- `activities_with_quality_warnings`: legacy count including informational messages; use new `activities_with_actionable_warnings` to see only actual warning-severity items.

## Missing and uncertain data

- `null` means not available: it does *not* mean zero.
- Indoor TCX speed/distance is an estimate and can change after watch calibration.
- `--run-speed-kmh` is a user-supplied constant for expected running distance, **not inferred**.
- `--treadmill-km` is the actual **whole treadmill workout** distance, *not* the running-only distance.
- Run interval boundaries use cadence + TCX laps; verify manually for unusual workouts.
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

The example identity above is **illustrative, not a real TCX match**; the update helper always copies exact identity fields from an actual analyzer report. During subsequent analyses a mismatch in either `activity_id` or SHA-256 prevents attaching metadata to a different file. Previously available metadata without identity remains accepted. The analyzer does not infer a sensor or symptoms from TCX. Missing `running-metadata.json` is normal before the user supplies any facts.

Commands and error-handling guarantees: [`AGENT_WORKFLOW.md`](AGENT_WORKFLOW.md) and [`AGENT_WORKFLOW.ru.md`](AGENT_WORKFLOW.ru.md).


## v1.4.0 — outdoor GPS, pause-aware duration and duplicate-aware collections

Other previously available metrics remain; new v1.4.0 per-activity fields:

- `source.activity_mode = {value, provenance}`: `outdoor`, `treadmill`, `unknown`, based on GPS, explicit user settings, or unknown. The original TCX `source.sport` remains separate.
- `movement.inferred_activity = {value, confidence, reason, median_cadence_spm, median_device_speed_mps}`; `movement.segments[]` partitions running / likely walking / inferred stationary / unknown periods, with corresponding total walking/unknown duration fields; values `walking`, `running_or_mixed`, `unknown` are **heuristic**, not ground truth.
- `total.elapsed_duration_s` / `recorded_duration_s`: elapsed first-to-last trackpoint time; `total.timer_duration_s`: summed TCX lap timer where complete; `total.timer_duration_provenance` identifies the source; `total.inferred_paused_duration_s` and `total.running_moving_duration_s` describe inferred outdoor no-motion gaps and running windows after these gaps are excluded. Outdoor legacy `total.run_duration_s` is now pause-adjusted.
- `outdoor.mode`, `gps_points`, `gps_available`, `distance_source`, `distance_m`, `pace_active_sec_per_km`, `speed_active_kmh`, `elapsed_duration_s`, `active_estimated_duration_s`, `inferred_paused_duration_s`, `running_moving_duration_s`, `elevation`, `inferred_pauses[]`, `unobserved_gaps[]`, `kilometer_splits[]` and `mile_splits[]`. Split pace is whole-activity pace (including walking). GPS positions are **not** stored in JSON.
- `quality.sampling_gap_policy` indicates outdoor adaptive vs legacy indoor threshold; `HR_DATA_MISSING` (info) means no HR, `HR_SOURCE_UNKNOWN` (info) means HR exists but sensor identity is unknown, `INFERRED_PAUSE` (info) and `UNOBSERVED_GAP` (warning) describe distinct sparse-recording cases.

Collection additions:

- `source.identity_status` per file: `unique`, `canonical`, `duplicate_export`, or `id_conflict`; duplicates include `source.duplicate_of`.
- `summary.unique_activities_counted`, `summary.duplicate_activity_groups[]`, `summary.duplicate_exports_excluded`, `summary.activity_id_conflicts[]`, `summary.activity_id_conflict_count`.
- `summary.activities_succeeded` still counts parsed **files**; weighted aggregates now use only unique/canonical activities (including all unresolved conflicts, which are explicitly flagged). Each duplicate report remains in `activities[]`.

These GPS and pause inferences cannot replace physical ground truth; read [Outdoor Running and GPS](OUTDOOR_RUNNING.md) before using them for individual training decisions.
