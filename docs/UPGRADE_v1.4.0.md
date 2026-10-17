# Upgrading v1.3.0 → v1.4.0

1. Make sure previous changes have been committed or backed up. Unpack the v1.4.0 **patch** into your existing repository, preserving other files.
2. Run `py -3 -m unittest discover -s tests -v` and `git diff --check`.
3. Check the changes, then commit and push to GitHub. Wait for all GitHub Actions jobs to succeed before creating a **separate** release tag `v1.4.0`.
4. You do **not** need to move the user’s `local-data/` folder or re-enter private metadata. The agent-led history flow still works. To add explicit outdoor mode to a single workout, use the normal verified metadata update workflow with `{ "activity_mode": "outdoor" }`.
5. v1.4.0 introduces a brand-neutral API and schema_version `2.0`: the distribution/CLI/module and the generic TCX distance fields are renamed. No compatibility shims are shipped. **Outdoor calculated values intentionally change:** large stationary sampling gaps no longer increase running duration, and aggregate batch statistics exclude equivalent duplicate TCX activities. Preserve prior v1.3.0 JSON if historical bit-for-bit comparison is required.
6. Reading raw third-party outdoor TCX is a local validation activity, not permission to commit or redistribute the full trace.

Regression tests run with synthetic coordinates. CI on Windows and Linux still requires verification after push. The provided patch does **not** publish a GitHub Release automatically.

## Repository rename and schema migration

The canonical repository is `https://github.com/smihus/tcx-running-analyzer`. Install the `tcx-running-analyzer` distribution and use `tcx-running-analyzer` or `python -m tcx_running_analyzer`; the former Garmin-named package/CLI is intentionally unsupported. Remove the old installation with `python -m pip uninstall garmin-tcx-running-analyzer` if present. Regenerate `running-activities.json` and `running-history.json` from original TCX; they are calculated outputs. Keep your private `running-metadata.json` (the activity identity and verified user notes do not change).

Renamed JSON keys: `garmin_distance_m` → `tcx_distance_m`, `distance_garmin_m` → `distance_tcx_m`, `garmin_distance_error_pct` → `tcx_distance_error_pct`. `outdoor.distance_source` is `TCX_DistanceMeters`; timer provenance is `sum_tcx_lap_total_time`. The TCX schema namespace URLs containing `garmin.com` are vendor-owned and must remain unchanged.
