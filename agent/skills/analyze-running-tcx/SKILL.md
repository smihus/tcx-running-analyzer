---
name: analyze-running-tcx
description: Interpret a single Garmin TCX Running Analyzer JSON report, focusing on running HR, cadence, recovery, run boundaries and user-reported sensations.
---

# Analyze one running workout JSON

Use when the user provides an individual JSON from `garmin-tcx-running-analyzer` and wants a running report, not for a whole archive.

## Procedure

1. Read `agent/rules/analysis.md` (in this repository) and apply it.
2. Validate `schema_version`, `source`, `total`, `runs`, `quality`. If `report_type == tcx_running_collection`, use the archive skill instead.
3. Check new `quality.issues` (`warning` vs `info`), `quality.hr_abrupt_jumps`, and `runs[].detection`; if absent, fall back to `quality.warnings`. `manual_override` means supplied boundaries, not independently high confidence. Check `quality.run_detection`. If segment boundaries are uncertain, say so; do not silently infer precise intervals.
4. Describe running structure using `total.run_count`, `total.run_duration_s` and every `runs[].duration_s`.
5. Report **running-only** average/max HR and cadence. Describe trends using individual run halves, `five_minute_splits`, last-30-second HR, and actual recovery period where present.
6. If available, compare `runs[].distance_garmin_m` with `runs[].treadmill_expected_running_m` **only when confirmed running speed was entered**. Never assume `total.treadmill_distance_m` equals running-only distance.
7. Include self-reported `subjective` metadata only if non-null; otherwise ask one optional question about symptoms/effort when it matters.
8. Provide a short, conservative interpretation, flag uncertainty, and avoid medical diagnosis.

## Output

Write a concise analysis in the user's language, then (if requested) update a separate running journal/manifest. Do not dump raw JSON; the tool already generated it.

- In v1.2.1+ `quality.hr_jump_episodes` groups adjacent abrupt HR changes; `hr_abrupt_jumps` preserves raw events. Neither is a diagnosis or automatic proof of artifact. `quality.unclassified_low_cadence_laps` is a manual-review hint, **not** a confirmed running block.
