# Upgrade to TCX Running Analyzer v1.4.1

This is the project-rename release. The preceding published `v1.4.0` tag (`66e7a01`) contains outdoor-running support under the previous Garmin-branded Python names and JSON schema `1.0`. The `v1.4.1` tag must point to a **new commit**, after the rename commit (`d38a730`) and version update. Never move or delete the published `v1.4.0` tag.

## Changed public interfaces (intentionally breaking)

| v1.4.0 | v1.4.1 |
|---|---|
| `garmin-tcx-running-analyzer` (Python distribution and CLI) | `tcx-running-analyzer` |
| `garmin_tcx_running_analyzer` (Python module) | `tcx_running_analyzer` |
| `garmin_distance_m` | `tcx_distance_m` |
| `distance_garmin_m` | `distance_tcx_m` |
| `garmin_distance_error_pct` | `tcx_distance_error_pct` |
| JSON schema `1.0` | JSON schema `2.0` |

Device-defined XML namespaces, Garmin cadence extensions and other TCX vendor-specific metadata are **not** renamed. PowerShell filenames `Analyze-Tcx.ps1` and `Running-Workflow.ps1` remain unchanged, but call the new package.

## Upgrade steps

1. Preserve or commit any current changes before upgrading.
2. Install the new project: `py -3.13 -m pip install -e .`; if desired, uninstall the old distribution with `py -3.13 -m pip uninstall garmin-tcx-running-analyzer` (requires pip installed).
3. Check `py -3.13 -m tcx_running_analyzer --help` and `py -3.13 -m unittest discover -s tests -v`.
4. Regenerate computed `running-activities.json`, single-activity reports, and `running-history.json` from original TCX sources; outputs based on the old JSON schema do not automatically migrate. **Do not discard** user-verified `running-metadata.json` or raw TCX.
5. Commit the version change to `main`, push and wait for GitHub Actions success for that exact commit. Only then create and publish **v1.4.1**.

No behavioral changes to run/walk/GPS analysis are introduced by this release; distance keys and schema version are intentionally different. Do not commit private GPS traces or workout metadata into the public repository.
