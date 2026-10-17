---
name: compare-running-history
description: Compare a persistently rebuilt running-history.json combining measured TCX metrics with separately confirmed user feelings and treadmill/sensor facts.
---

# Compare running history

Use for an archive JSON or multi-workout trend analysis. Primary input is **`running-history.json`**, regenerated from TCX and `running-metadata.json`. If only a collection report is supplied, still analyze it but don't imply subjective fields were filled by the athlete.

## Procedure

1. Read `agent/rules/analysis.md`, `agent/AGENTS.md`, and the workflow document. Check `summary.files_found`, `activities_succeeded`, `activities_failed`, `errors`, and optional manifest coverage. Gaps between observed dates are not evidence of missing training.
2. Read all `activities[]` in date order; identify records by `source.activity_id`, `source.sha256` and filename. Do not count repeated uploads of the same TCX twice. Compare run duration/intervals, running-only HR, cadence and post-run recovery across similar workouts.
3. Review quality diagnostics (`quality.issues`, HR anomaly episodes, manual run boundaries and heuristic detection confidence). Don't equate the full activity HR maximum with the running-only maximum.
4. Integrate `subjective` only when its values are explicitly present, and explain that treadmill speed/distance and source HR sensor are **user-supplied** when known. Unknown sensor or feelings are not evidence of no symptoms.
5. If previous reports lack metadata but the user shares a newly confirmed fact, invoke the `maintain-running-metadata` skill to update only that workout, rebuild history, and then reassess comparisons. Never hand-edit measured fields.
6. Summarize supported progression milestones and caveats; avoid diagnosing illness or asserting physiological causes from a single anomaly. Offer conservative next steps where requested.

## Output

Concise in the user's language, with changes grounded in named dates and recorded values. If the user keeps a separate Markdown training manifest, preserve its prior history and update it only when asked. Do not publish private TCX, JSON or athlete notes.

## Outdoor comparisons (v1.4.0)

First drop `source.identity_status=duplicate_export` from trend calculations; inspect `summary.activity_id_conflicts` before trusting totals. Separate treadmill-confirmed speed and outdoor device-distance/active-pace estimates; consider elevation and walk breaks, and never infer improvement from comparing unlike running surfaces or a paused GPS activity with a continuous treadmill workout. Inspect `movement.inferred_activity` and `total.running_moving_duration_s`; the `timer_duration_s` is not necessarily identical to actual moving time. See `docs/OUTDOOR_RUNNING.md`.
