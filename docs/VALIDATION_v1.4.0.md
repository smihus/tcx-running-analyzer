# v1.4.0 validation record (2026-10-17)

This development snapshot was validated **locally in Linux/Python**, not yet by GitHub Actions or Windows PowerShell. Do not describe the public CI as green until the user's GitHub workflow completes.

1. `python -m unittest discover -s tests -v`: **44 passed** (synthetic fixtures only, no real coordinates).
2. Wheel built with `python -m pip wheel . --no-deps --no-build-isolation`: `garmin_tcx_running_analyzer-1.4.0-py3-none-any.whl` created successfully.
3. **19 privately supplied treadmill TCX**: all 19 parsed; v1.4.0 vs v1.2.1 JSON comparison showed **0 differences** in previously verified per-activity running duration, running intervals/boundaries, mean/max running HR, cadence, and longest uninterrupted segment. Archive running time remains **488.84 minutes**. Private TCX and regression JSON **are not bundled**.
4. Three third-party public TCX supplied separately for local testing:
   - `activity_10101108916.tcx`: 0 running segments; outdoor low-cadence walking classification; no false `RUN_SEGMENTS_NOT_FOUND` warning.
   - `activity_19650143389.tcx`: 4 stationary sparse-recording gaps total **806 s**; `run_duration_s` changes from v1.3.0 **7605.1 s** to **4538 s (75.6 min)** in 43 cadence-supported fragments. About **2500 s** of low-cadence movement are labelled *likely walking*, 13 s are unknown. Garmin elapsed 7857 s and Lap timer ~7048 s are independently reported. The algorithm no longer forces mile-wide `Lap` intervals to be all running.
   - `new_river_50k.tcx`: v1.3.0 reported 6 long runs and ~334 min; v1.4.0 detects **29** cadence-supported fragments, **18863 s (314.4 min)** of running, **1565 s** of likely walking and **110 s** unknown. Mile-based Garmin laps are not running intervals. `HR_DATA_MISSING` replaces misleading unknown-sensor warning.
5. Historical **10-file v1.3.0 outdoor JSON** (not raw 10-file reprocessing) used to validate deduplication: 10 parsed exports, **9** aggregate-counted sessions, repeated Garmin marathon counted once, corrected historical total **1025.29 minutes**. The remaining seven public raw TCX files have **not** been rerun locally in v1.4.0 at this time.
6. Raw GPS latitude/longitude are never serialized to the generated JSON; test fixtures use fabricated positions, not private routes. All source TCX remain read-only.

Remaining acceptance gate: run the full 10-file outdoor directory and the new PowerShell launcher on Windows; review any warnings and confirm six GitHub Actions matrix jobs before tagging a release. GPS-derived split times/elevation are estimates, not lab-validated ground truth.
