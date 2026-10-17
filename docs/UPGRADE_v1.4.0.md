# Upgrading v1.3.0 → v1.4.0

1. Make sure previous changes have been committed or backed up. Unpack the v1.4.0 **patch** into your existing repository, preserving other files.
2. Run `py -3 -m unittest discover -s tests -v` and `git diff --check`.
3. Check the changes, then commit and push to GitHub. Wait for all GitHub Actions jobs to succeed before creating a **separate** release tag `v1.4.0`.
4. You do **not** need to move the user’s `local-data/` folder or re-enter private metadata. The agent-led history flow still works. To add explicit outdoor mode to a single workout, use the normal verified metadata update workflow with `{ "activity_mode": "outdoor" }`.
5. v1.4.0 adds fields while preserving the `schema_version: "1.0"` and previous field names. **Outdoor calculated values intentionally change:** large stationary sampling gaps no longer increase running duration, and aggregate batch statistics exclude equivalent duplicate Garmin activities. Preserve prior v1.3.0 JSON if historical bit-for-bit comparison is required.
6. Reading raw third-party outdoor TCX is a local validation activity, not permission to commit or redistribute the full trace.

Regression tests run with synthetic coordinates. CI on Windows and Linux still requires verification after push. The provided patch does **not** publish a GitHub Release automatically.
