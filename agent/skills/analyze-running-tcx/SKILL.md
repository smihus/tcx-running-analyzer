---
name: analyze-running-tcx
description: Receive one or more TCX files, execute Garmin TCX Running Analyzer, inspect diagnostic JSON, clarify athlete-reported context, and hand off to persistent metadata/history skills.
---

# Ingest TCX and analyze a workout

**Primary input is TCX**, not pre-generated JSON. Also accept existing analyzer JSON when the user explicitly supplies only a report. Follow `agent/AGENTS.md`, `agent/rules/analysis.md`, `docs/AGENT_WORKFLOW.md`, and `agent/skills/maintain-running-metadata/SKILL.md`.

## Procedure

1. If the user gave one or several `.tcx` / `.tcx.xml` files and local tools are available, ingest them into the private workspace (default `local-data/`) and run the analyzer automatically:
   ```powershell
   .\Running-Workflow.ps1 -Ingest -Workspace '.\local-data' -UtcOffset '+04:00' -Paths 'D:\Incoming\example.tcx'
   ```
   The offset shown is **only an example**: obtain the actual offset from the user or saved workspace settings, and never infer location or timezone from a file. For cross-platform use, invoke `python -m garmin_tcx_running_analyzer.workflow_cli ingest --workspace ... --tz-offset ... <tcx>`. For existing workspaces omit `-UtcOffset` to reuse saved settings. If the user has provided files but the current chat lacks execution/storage access, explain the limitation and offer executable commands or a generated result file; never claim automatic ingestion.
2. Read generated `running-activities.json`. Identify the user's new workout(s) by filename **and** Garmin activity ID and SHA-256 (not simply by the latest date). Check `summary.activities_failed`, `errors`, `quality.issues` (`warning` vs `info`), `runs[].detection` and `quality.hr_jump_episodes`. Suspicious or ambiguous run segmentation remains explicitly uncertain until manually verified.
3. Describe the workout: running interval count/duration, running-only average/max HR, cadence, five-minute progression and recovery. Garmin treadmill distance is an estimate, not user-confirmed distance. Do not conflate `total.hr_avg_bpm` with `total.run_hr_avg_bpm`.
4. Load matching prior user notes from `running-metadata.json` and conversation if available. Hand off to `maintain-running-metadata` skill to ask a small number of **important, unanswered** questions about feelings or treadmill/sensor context. Do not demand every optional value or assume an absent symptom is false.
5. Once the user confirms any new facts, the metadata skill writes them safely and rebuilds `running-history.json`. Use the **enriched** history to present current analysis and, when useful, comparisons via `compare-running-history`. If no facts are reported, leave metadata as-is and proceed with objective analysis.

## Output

Provide a concise assessment in the user's language. Clearly distinguish Garmin/sensor data from user statements and uncertain inferences. Notes are private. Do not dump raw JSON. Honor a request for a written training manifest separately from structured metadata.

## Outdoor interpretation (v1.4.0)

Read `source.activity_mode`, `movement.inferred_activity`, `outdoor` and the pause-aware time fields before describing a GPS-based run. Describe running cadence and HR only when measurements exist. Use GPS distance/splits for whole-activity pace, not to claim exact running-only pace. Kilometer/mile lap distance should not be confused with run/walk changes. If `activity_mode=unknown` and the distinction matters, ask for user confirmation through `maintain-running-metadata`; otherwise leave it unknown. Never print GPS coordinates. When reporting history, heed canonical/duplicate status.
