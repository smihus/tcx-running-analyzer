TCX Running Analyzer v1.4.0 — complete vendor-neutral rename
Repository: https://github.com/smihus/tcx-running-analyzer

IMPORTANT: Old package/CLI/JSON field aliases are NOT supported.

To apply in an existing git clone:
  1. Ensure working tree is backed up or clean: git status --short
  2. Extract TCX_Running_Analyzer_v1.4.0_Rebrand_Patch.zip into the repository root.
  3. Stage deletion of former tracked Python package: git rm -r src/garmin_tcx_running_analyzer
     (If your local Git does not track that path, remove it manually only after checking contents.)
  4. Uninstall the obsolete package if you installed it: py -3 -m pip uninstall garmin-tcx-running-analyzer
  5. Install the renamed project: py -3 -m pip install -e .
  6. Run: py -3 -m unittest discover -s tests -v
  7. Run: tcx-running-analyzer --help
  8. Run: py -3 -m tcx_running_analyzer --help
  9. Inspect and commit: git add -A; git diff --cached --stat; git commit -m "Rename project to TCX Running Analyzer"; git push origin main
 10. Verify GitHub Actions for the new commit. Use the BRAND-NEW release kit before publishing v1.4.0; the previous one contains the outdated repository identity.

Computed reports created by older versions use schema 1.0 and must be regenerated from original TCX.
Keep personal running-metadata.json and TCX in local-data; never commit personal datasets.
Historical release notes can mention Garmin because that was the name at the time.
See docs/REBRANDING.md and docs/UPGRADE_v1.4.0.md.
