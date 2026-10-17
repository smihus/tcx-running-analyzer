# Upgrade to v1.3.0 from v1.2.1 / Обновление с v1.2.1

- Keep the existing Git clone and uncommitted work safe. Run `git status --short` first; don't discard personal changes.
- Extract the supplied **patch** ZIP directly into the repository root, preserving its relative paths. It includes new `AGENTS.md`, `Running-Workflow.ps1`, `metadata_cli.py`, `workflow_cli.py`, a third agent skill, tests, documentation and modified version/config files.
- Run `py -3 -m unittest discover -s tests -v` and `git diff --check`. The analyzer's existing file/folder CLI and JSON fields remain compatible.
- Commit only code/docs. Private workouts/notes belong in a separate folder or the Git-ignored `local-data/` folder; never add them with `git add -f`.
- Push and wait for all GitHub Actions jobs (Linux + Windows/Python matrix). The PowerShell workflow smoke test is new; its Windows operation cannot be confirmed solely by Linux unit tests.
- The GitHub Release for `v1.3.0` is a separate step **after CI succeeds**. Do not rerun a release script hard-coded for an older version.

## Пример Windows (после распаковки патча)

```powershell
cd C:\Projects\garmin-tcx-running-analyzer
py -3 -m unittest discover -s tests -v
git diff --check
git add AGENTS.md Running-Workflow.ps1 .gitignore .github/workflows/tests.yml src/ tests/ agent/ docs/ examples/ README.md README.ru.md CHANGELOG.md pyproject.toml
git diff --cached --stat
git commit -m "Add agent-led TCX history workflow in v1.3.0"
git push origin main
```

`Running-Workflow.ps1` does not require installing the Python package (but does need Python 3.10+). For detailed steps, see [`AGENT_WORKFLOW.ru.md`](AGENT_WORKFLOW.ru.md).
