# Rules: interpreting Garmin TCX Running Analyzer results

**Scope:** AI analysis of human running workout JSON from this repository. These are analysis rules, **not** commands to modify the analyzer code.

## Data/provenance

- Distinguish **measured by Garmin/HR sensor**, **user-entered**, **derived** and **unknown**.
- Garmin TCX `RunCadence` is doubled to display steps/minute for compatible Garmin exports; never double an already converted JSON value.
- On treadmills, Garmin indoor speed and distance are estimates. A user-confirmed treadmill reading supersedes Garmin distance where the measurements refer to the same window. `treadmill_distance_m` is the **entire** treadmill session, not the run-only distance.
- `--run-speed-kmh` is manually supplied. Never infer confirmed treadmill speed from Garmin TCX speed.
- `source.hr_sensor.value` originates from user CLI/metadata (or is `unknown`); TCX alone does not verify a chest-strap connection.
- A `null` field means unavailable. It never implies zero or absence of a symptom. Missing `subjective` observations require user input.
- Do not conflate whole-activity average HR and running-only average HR. Use `total.run_hr_avg_bpm` and `total.run_hr_max_bpm` for running comparisons.
- Report start times according to `datetime.start_local` and the configured fixed `tz-offset`; no assumption about real geographic location or daylight savings.

## Quality and comparison

- Start with `quality.issues`: handle `warning` severity separately from `info`; `HR_SOURCE_UNKNOWN` is informational, not an error. Continue supporting legacy `quality.warnings` for pre-v1.2.0 reports. Evaluate `quality.run_detection`, `runs[].detection` and `lap_metadata` for inconsistent boundaries. `confidence` is a heuristic label, not probability; `manual_override` is a user assertion, not verified truth. On suspicious data, request the TCX or a corrected manual run window.
- `five_minute_splits` are **inside each run**, not cumulative across separate bouts unless deliberately aligned.
- Compare equivalent workloads where possible: running duration/pace, intervals/rests, time of day, HR sensor, training context. Higher HR one day does not establish a trend or time-of-day effect.
- Read `quality.hr_abrupt_jumps` (if present): report exact time, signed bpm change, and workout phase; don't assume artifact or diagnose illness. If these fields are absent, use older `quality.warnings` cautiously.
- Never infer missing archive workouts from `summary.observed_date_gaps`; verify `summary.archive_completeness.missing_files` only when an expected manifest was supplied. That check does not prove every file parsed successfully.
- Avoid comparing an optical reading's isolated spike with a chest-strap trace as if identical measurement quality. Abrupt HR jumps are flags, not confirmed artifacts.
- For collection reports, sort by `datetime.start_utc` (already sorted), read **all** `activities`, and describe session-to-session patterns. `summary` duration-weighted numbers are descriptive and can be skewed by mixed dates and protocols.
- If collection `errors` is nonempty, explicitly note incomplete coverage; do not claim every workout was analyzed.

## Health and safety

- Do not diagnose cardiac conditions, foot injuries, asthma exacerbations, or imply that stable HR eliminates risk.
- Do not set or validate an individual medical HR ceiling without appropriate clinical information. User-selected HR rules are personal training preferences, not medical thresholds.
- Give priority to pain, symptoms and recovery over training targets. If pain recurs or worsens, suggest reducing/stopping aggravating exercise and considering qualified medical/physio advice.
- Do not invent pain, soreness, fatigue, recovery status, exercise distance or treadmill setting.
- Avoid pretending a workout's changes were caused by time of day, hydration, caffeine or sleep when such context was not supplied.

## User-facing structure

1. State workout structure (intervals, duration) and any uncertainty.
2. Summarize running HR, peak, cadence, temporal changes and recovery.
3. Compare with comparable previous workouts when provided.
4. Integrate *explicit* subjective feedback without confusing it with measured data.
5. Suggest conservative next steps and note unresolved limitations.

When asked to maintain a log/manifest, update the existing file without rewriting history or replacing the owner's observations with inferred ones.

- In v1.2.1+ `quality.hr_jump_episodes` groups adjacent abrupt HR changes; `hr_abrupt_jumps` preserves raw events. Neither is a diagnosis or automatic proof of artifact. `quality.unclassified_low_cadence_laps` is a manual-review hint, **not** a confirmed running block.
