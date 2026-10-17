---
name: maintain-running-metadata
description: Safely keep a persistent private running-metadata.json from the athlete's explicit answers, link notes to TCX activity identities, and rebuild the combined running-history.json without changing measured metrics.
---

# Maintain athlete-reported workout metadata

Use for any opted-in TCX ingestion/analysis conversation where the assistant can save files and execute local Python, or when the user asks to record/revise a workout's sensations, sensor or treadmill readings. Read `agent/rules/analysis.md` and `docs/AGENT_WORKFLOW.md` first.

## Preparation and identity

1. Locate the persistent **private** workspace (default `local-data/`, never commit). Read `running-activities.json` and any current `running-metadata.json` (the latter may not exist). Match the exact `source.filename` and `source.activity_id`; cross-check `source.sha256`. Do not assume that a filename alone always means the same workout.
2. Check whether user information is already stored or stated in the conversation. `null` or absent means unknown, **not** “no pain.” Respect previous user declines; avoid redundant questions.
3. For new TCX inputs, invoke the analyzer workflow **before** metadata updates, using the primary `analyze-running-tcx` skill. Do not hand-edit measured values in `running-activities.json` or the merged `running-history.json`.

## Clarify only when useful

Ask selectively about meaningful missing details, such as physical sensations (including pain, foot fatigue, breathing and general effort), actual total distance from the treadmill, actual running speed, or HR sensor **if user knows**. Avoid repetitive multi-question surveys. For unusual run segmentation, ask for explicit run intervals only if available; never infer or “fix” them based only on a questionable cadence trace.

## Safe update

1. Convert only explicit user answers to a temporary **patch JSON object**, e.g. `{"subjective":{"foot_pain":false,"overall_fatigue":"mild"},"treadmill_km":3.82}`. Use existing valid metadata keys (see `examples/user-feedback.patch.example.json`). A vague answer does not license a definitive boolean; unknown values should be omitted, never filled with guessed defaults.
2. If a new answer differs from a previously recorded value, confirm it is a correction before replacing the old value. Other entries and other `subjective` subkeys must remain untouched.
3. Call on Windows from the repo root:
   ```powershell
   .\Running-Workflow.ps1 -Record -Workspace '.\local-data' -File 'activity_123.tcx' -Patch '.\local-data\pending-confirmed.json'
   ```
   Or cross-platform after installation:
   ```shell
   python -m tcx_running_analyzer.metadata_cli --report ./local-data/running-activities.json --metadata ./local-data/running-metadata.json --file activity_123.tcx --patch ./pending-confirmed.json
   python -m tcx_running_analyzer.workflow_cli rebuild --workspace ./local-data
   ```
4. Verify that `running-history.json` shows exactly the confirmed values for the matching workout and retains historical metadata. Explicitly report a blocked identity mismatch; never override or rename a conflicting file silently. Delete only the temporary patch file if no longer needed; preserve persistent metadata.
5. If user supplies no new information, **do not create empty or invented metadata**. Continue analyzing objective measurements.

## Failure behavior

If the environment cannot run Python, access the files, or persist changes, do not claim to have updated the user's computer. Provide the user the patch/updated metadata file or the exact commands. Do not upload personal TCX/JSON/notes to public repos or remote endpoints.

## Recording outdoor mode (v1.4.0)

When the training location/mode matters and remains uncertain, ask whether the activity was on a treadmill or outdoors. Only on explicit confirmation record `{"activity_mode":"outdoor"}` or `{"activity_mode":"treadmill"}` using the existing metadata upsert and rebuild workflow. Do not infer user feelings, weather, or a real-world GPS route. A sparse trace without cadence is not evidence of walking.
