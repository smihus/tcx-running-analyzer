---
name: compare-running-history
description: Compare a combined archive JSON from Garmin TCX Running Analyzer across many running workouts and identify supported changes in training structure, heart rate, cadence and recovery.
---

# Analyze a folder's combined workout JSON

Use when `report_type == "tcx_running_collection"` or the user asks to analyze their training history from one combined JSON.

## Procedure

1. Read `agent/rules/analysis.md` and follow its provenance/safety guidance.
2. Check `summary.files_found`, `summary.activities_succeeded`, `summary.activities_failed` and `errors` before drawing conclusions about the archive's completeness.
3. Read **every** `activities[]` in chronological order. Confirm changes in training structure from `total.run_count`, `total.run_duration_s`, `longest_continuous_run_s` and the per-run arrays.
4. Compare running-only average/max HR and cadence by session; consider matching duration, interval pattern and sensor labels. Don't turn a single unusual HR result into a general causal statement.
5. Examine five-minute split progression and post-run recovery for sessions where relevant. Do not infer fitness from Garmin-reported treadmill distance alone.
6. Attribute foot pain, exhaustion, breathing symptoms or recovery only to explicit user-provided subjective notes or messages. `null` remains unknown.
7. In a written summary, separate measurable long-term changes from tentative hypotheses and data-quality limitations.
8. If requested to update a journal/manifest, append/modify the latest entry while preserving historical facts, and offer the result as a separate file.

## Output

Summarize major progression milestones, recent comparable sessions, recovery patterns, exceptions, and a conservative next-step recommendation. For detailed verification cite relevant `source.filename` values inside the combined JSON; include a caveat if `errors` is nonempty.
