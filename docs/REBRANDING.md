# TCX Running Analyzer — repository rename

The canonical repository URL is https://github.com/smihus/tcx-running-analyzer.

## Final project identity

- Distribution on Python packaging tools: `tcx-running-analyzer`
- Import and `python -m` package: `tcx_running_analyzer`
- Installed command: `tcx-running-analyzer`
- Windows entry points: `Analyze-Tcx.ps1`, `Running-Workflow.ps1` (unchanged because they were already vendor-neutral)
- JSON schema: `2.0`; `tcx_distance_m`, `distance_tcx_m`, `tcx_distance_error_pct`; `TCX_DistanceMeters`, `sum_tcx_lap_total_time`
- GitHub: `smihus/tcx-running-analyzer`

Garmin-specific TCX XML namespace URIs and device-specific `RunCadence` parsing **are not renamed**. They reflect real format/vendor definitions, not project identity. The tool is not associated with any sports-watch manufacturer.

## Apply to a Git clone currently at v1.4.0

1. Verify `git status` and protect your own changes.
2. Extract the rename patch at the repository root.
3. Delete the previous tracked package folder: `src/garmin_tcx_running_analyzer` (not your `local-data` folder).
4. Remove the old editable distribution with `py -3 -m pip uninstall garmin-tcx-running-analyzer` if it is installed.
5. Run `py -3 -m pip install -e .` and `py -3 -m unittest discover -s tests -v`.
6. Run `tcx-running-analyzer --help`, `py -3 -m tcx_running_analyzer --help`, plus both Windows launchers.
7. Stage tracked changes with `git add -u`, then stage only new project files with `git add src/tcx_running_analyzer tests/test_branding.py docs/REBRANDING.md README_RENAME.txt`. Review `git diff --cached --stat`, commit, and push. Avoid staging unrelated untracked release scripts or personal files. Verify CI before publishing a `v1.4.0` tag.

The old package, command, and JSON schema are intentionally **not** supported. To migrate reports, regenerate `running-activities.json` and `running-history.json` from original TCX. Keep private `running-metadata.json` (activity IDs and user-confirmed facts are unaffected).

Keep prior GitHub releases under their original name as historical artifacts. Rebranding a repository does not require deleting old releases or tags. Do not replace an already-published tag without explicitly planning a new version.
