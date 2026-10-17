TCX Running Analyzer — v1.4.1 release of the project rename
Repository: https://github.com/smihus/tcx-running-analyzer

The outdoor-running code was published at v1.4.0 under the former Garmin-branded Python package names.
The next version is v1.4.1; do not move the published v1.4.0 tag (66e7a01).
Version v1.4.1 points to a new commit after the rename commit d38a730.

Change: new module/CLI tcx_running_analyzer and tcx-running-analyzer,
JSON schema 2.0 and generic TCX distance fields. The old names are unsupported.
Personal TCX and running-metadata.json are untouched. Regenerate calculated reports.

See docs/UPGRADE_v1.4.1.md; verify tests and GitHub Actions on the
version-bump commit before running the v1.4.1 publication script.
