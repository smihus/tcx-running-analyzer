# Changelog

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
