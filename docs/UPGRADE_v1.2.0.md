# Upgrade from v1.1.0 to v1.2.0

The `v1.2.0` update keeps the v1.1.0 JSON `schema_version` (`1.0`) and existing field names. New diagnostics, manual batch overrides and optional expected-file coverage checks are additive.

## Applying the patch to an existing Git clone (Windows PowerShell)

1. Download `TCX_Running_Analyzer_v1.2.0_patch.zip` and keep the original public repository clone.
2. In PowerShell (adjust the ZIP path):

```powershell
cd C:\Projects\tcx-running-analyzer
# Verify you do not have unrelated uncommitted changes before overwriting code.
git status --short
Expand-Archive -LiteralPath 'C:\Downloads\TCX_Running_Analyzer_v1.2.0_patch.zip' -DestinationPath . -Force
py -3 -m unittest discover -s tests -v
git status --short
git add .
git commit -m "Release v1.2.0 analyzer improvements"
git push
```

On Windows, the `Analyze-Tcx.ps1` launcher may be restricted by the local PowerShell execution policy; this is a separate Windows setting. Only run scripts you trust. The test suite works through `py -3` without executing the PowerShell launcher locally; GitHub Actions tests the launcher on Windows on the next push.

The patch **does not replace** `LICENSE`, `.gitignore`, or your repository `.git` history. It includes only additions and modifications compared with the published v1.1.0 source package, including the fixed Windows CI workflow.

## Rebuilding your JSON archive

Re-run the original folder command. One combined JSON is still produced:

```powershell
.\Analyze-Tcx.ps1 -Path 'C:\Projects\Бег\TCX' -Recursive `
    -UtcOffset '+04:00' -Output 'C:\Projects\Бег\JSON\running-activities.json'
```

Optional `-Metadata` supports per-file `run_windows` overrides. Optional `-ExpectedManifest` accepts a JSON or text file listing expected TCX paths and `-DateGapDays` controls observed calendar gap reporting. See the README and [`JSON_FORMAT.md`](JSON_FORMAT.md).

## What changed

- Distinguish actionable warnings from informational diagnostics. Legacy `quality.warnings` remains intact.
- Classify run-detection confidence based on cadence/lap consistency. It is **not** statistical probability.
- Timestamp HR jumps with signed bpm change and phase. No claim that a jump is a sensor artifact.
- Support manually verified run windows for individual files in folder mode.
- Check archive filenames against an optional expected-file manifest and report observed date gaps without inventing missing workouts.

Run `python -m unittest discover -s tests -v` after updating. The final Windows CI result can only be confirmed after pushing to GitHub.
