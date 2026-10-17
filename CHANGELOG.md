# Changelog

## 1.4.0 — 2026-10-17

- Rename the project and repository to **TCX Running Analyzer** (`tcx-running-analyzer`). Use brand-neutral CLI/module names, JSON schema `2.0` and TCX-specific generic distance fields; no legacy aliases are included. Garmin-defined XML namespaces and running-cadence extensions remain supported.

- Add per-activity `activity_mode` (`auto`, `outdoor`, `treadmill`, `unknown`). GPS presence can suggest outdoor; a user-supplied treadmill setting takes precedence. User confirmation via private metadata is supported.
- Parse TCX GPS position and altitude; calculate outdoor active-time pace/speed, conservative altitude gain/loss, and kilometer/mile distance splits. **Never export raw GPS coordinates**.
- Distinguish elapsed time, TCX lap-timer time, estimated paused time, probable walking and running-moving time. Split outdoor running bouts around inferred stationary gaps and long unobserved periods. Avoid counting per-mile/per-kilometer TCX distance laps as continuous running, which could mask numerous walk breaks.
- Replace indoor 2-second gap warnings with adaptive outdoor sampling diagnostics; classify sustained low-cadence walking, retain uncertain movement, and supply low-confidence speed-only running detection if cadence is absent.
- Report missing HR samples as `HR_DATA_MISSING` instead of unknown sensor; preserve unknown sensor notices when HR exists.
- Deduplicate equivalent TCX exports sharing a TCX activity ID for **aggregate statistics only**; retain all file reports and flag conflicting IDs instead of silently merging them.
- Preserve all v1.3.0 indoor running calculations (some schema field names intentionally change). Add synthetic regression tests and verify all 19 previously analyzed treadmill activities without metric regressions. Real third-party GPS tracks are used for local validation only, never committed as fixtures.
- GPS split active time and inferred pauses are estimates, not confirmed auto-pause events or medically validated motion classification.


## 1.3.0 — 2026-10-17

- Add an opt-in AI-first local workflow: user supplies TCX, agent executes analyzer, asks only relevant questions, stores explicit feedback and rebuilds a cumulative enriched history.
- Add `workflow_cli` ingestion/rebuild and `Running-Workflow.ps1` for Python-free-package-install Windows use. Preserve original TCX, detect basename conflicts and avoid duplicate imports of the same file.
- Add a safe `metadata_cli` patch/upsert preserving previous fields and linking personal notes to the original Garmin activity ID and TCX SHA-256. Reject identity mismatches and invalid updates before file replacement.
- Store personal TCX and JSON under Git-ignored `local-data/` by default. Keep raw measurements and derived merged report separate from user-confirmed metadata.
- Add `maintain-running-metadata` skill and update agent instructions, existing skills, bilingual docs, examples, synthetic tests and Windows CI smoke test.
- Keep the original analyzer CLI and existing JSON fields backward-compatible.

## 1.2.1 — 2026-10-17

- Add `quality.hr_jump_episodes` grouping adjacent, same-direction one-second HR changes; keep `hr_abrupt_jumps` intact. Episodes describe only rapid changes, **not how long HR stays high**.
- Add `quality.unclassified_low_cadence_laps` for manual review when no running segments were found. Never force walking into a running segment.
- Add synthetic regression tests covering grouping and atypical cadence. No personally identifiable TCX files are included.


## 1.2.0 — 2026-10-17

- Keep JSON `schema_version` 1.0 and all v1.1.0 fields, add typed `quality.issues` with `warning`/`info` levels and archive severity summaries.
- Add per-run heuristic detection confidence and supporting evidence; mark manual corrections as `manual_override`.
- Include exact UTC/local timestamp, signed magnitude and workout phase of abrupt one-second HR changes.
- Allow per-file manual `run_windows` in folder-mode metadata, including validation and partial failure handling.
- Add optional `--expected-manifest` (`.json`/`.txt`) and observed date gaps via `--date-gap-days`; do not infer missing sessions from gaps alone.
- Document new fields for AI agents, update examples and synthetic regression tests.
- Fix Windows CI PowerShell launcher call to use `-Output` (one dash).


## 1.1.0 — 2026-10-17

- Public GitHub-ready `src/` Python package, CLI entry point, PowerShell launcher and MIT license.
- Folder and multi-file mode now produce **one collection JSON** with full activity reports plus aggregated summary.
- Optional recursive search, per-file metadata, and synthetic test suite.
- Opt-in AI agent rules and skills in `agent/`.
- Keep stand-alone single-file JSON output compatible with previous 1.0 report format.

## 1.0.0 — 2026-10-17

- Initial Garmin TCX-to-JSON analyzer with cadence/lap run detection, heart rate, cadence, segments and recovery.
