# Garmin TCX Running Analyzer v1.2.0

**Offline running workout analysis for Garmin TCX → AI-ready JSON**

This release improves diagnostics and historic batch analysis while retaining existing v1.1.0 report fields and JSON schema v1.0.

## What's new

- Clear `warning` vs `info` diagnostics. Missing HR sensor labels no longer count as actionable warnings.
- Per-run heuristic confidence indicators with cadence and lap evidence. Manual interval corrections are explicitly tagged `manual_override`.
- Precise UTC/local timestamp, heart-rate delta and workout phase for abrupt 1-second HR changes.
- Per-file manually verified running intervals via `run_windows` in batch metadata.
- Optional archive completeness verification against JSON/TXT expected-file manifests plus informational calendar date gaps.
- Extended synthetic test suite and refreshed PowerShell/AI-agent documentation.

## Compatibility

- Python 3.10+, Windows and Linux; no external runtime Python libraries.
- One folder still produces **one comprehensive JSON**.
- All existing v1.1.0 output fields and schema version are preserved.
- Existing `--metadata` configurations continue to work.

The source TCX is always read-only. Personal training files are not included in the public package.
