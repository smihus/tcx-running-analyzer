# Garmin TCX Running Analyzer

**Offline running workout analysis for Garmin TCX files → AI-ready JSON**

[Документация на русском](README.ru.md) · [JSON format](docs/JSON_FORMAT.md) · [Optional AI agent instructions](agent/README.md) · [MIT License](LICENSE)

Garmin TCX Running Analyzer extracts heart-rate, cadence, running intervals, recovery and distance data from exported Garmin TCX workouts. It is a **local, dependency-free Python 3.10+ CLI**. No cloud service, account or Garmin API required.

**Folder mode produces exactly ONE combined JSON with all workouts and an archive summary.** Individual input files are not modified.

## Features

- Automatically detects running bouts: 5×7, 3×10, 2×15, 30-minute continuous runs and other lengths, using cadence and Garmin lap hints.
- Heart-rate averages/peaks, first vs. second half, five-minute splits, last 30 seconds and post-run recovery.
- Cadence in **steps/min** (Garmin RunCadence values doubled for compatible Garmin exports).
- Data-quality indicators and warnings when sensor data is missing or suspicious.
- Optional actual treadmill distance, manually confirmed run speed and per-workout notes.
- File mode: **one TCX → one JSON**. Folder/multiple-file mode: **all TCX → one JSON** containing full individual reports and weighted archive summary.
- Recursive folder scan (`--recursive`), and filenames ending `.tcx` or `.tcx.xml` (case-insensitive).
- Windows PowerShell launcher, installable Python command and optional AI agent skills.
- **Standard library only at runtime**. Unit tests use Python `unittest`.

## Quick start — Windows PowerShell (no installation)

Download/unzip the repository, install Python **3.10+**, open PowerShell in the project root:

```powershell
# One file -> D:\Running\activity.running.json
.\Analyze-Tcx.ps1 -Path 'D:\Running\activity.tcx' -TreadmillKm 3.82 -RunSpeedKmh 6 -UtcOffset '+04:00'

# One folder -> D:\Running\running-activities.json (ONE file, all workouts)
.\Analyze-Tcx.ps1 -Path 'D:\Running' -RunSpeedKmh 6 -UtcOffset '+04:00'

# Include subfolders, specify a destination
.\Analyze-Tcx.ps1 -Path 'D:\Running' -Recursive -Output 'D:\Reports\training-history.json'
```

The launcher finds `py -3` or `python` and launches the source package directly through `PYTHONPATH`, with no `pip install` needed. The script and source TCX files remain unchanged.

## Python CLI

For development or installation in an isolated environment:

```shell
python -m pip install -e .
garmin-tcx-running-analyzer "./activity.tcx" --run-speed-kmh 6.0 --tz-offset +04:00
garmin-tcx-running-analyzer "./workouts" --recursive --output "./history.json"
```

Without installing the package (macOS/Linux/Windows terminal):

```shell
PYTHONPATH=src python -m garmin_tcx_running_analyzer "./workouts" --recursive --output "./history.json"
```

Windows PowerShell users should use `Analyze-Tcx.ps1` above rather than POSIX `PYTHONPATH=...` syntax.

## CLI options

| Option | Purpose |
| --- | --- |
| positional path(s) | File, folder or glob; multiple inputs always write **one** collection JSON |
| `-o, --output PATH.json` | Output **JSON filename**, not a directory |
| `--recursive` | Recurse into nested directories |
| `--tz-offset +04:00` | UTC offset for display; default **+00:00** (UTC) |
| `--run-speed-kmh 6` | **Confirmed** treadmill running speed, used only for expected distance |
| `--treadmill-km 3.82` | **Whole treadmill session** distance; file mode only |
| `--hr-source polar_h10` | Explicit sensor label, never inferred; default `unknown` |
| `--metadata PATH.json` | Per-file treadmill speed/distance, HR source and subjective notes in archive mode |
| `--run-cadence-threshold 145` | Auto-detection cadence threshold, steps/min |
| `--min-run-seconds 45` | Ignore shorter automatic fragments |
| `--join-gap-seconds 12` | Bridge short cadence gaps within a bout |
| `--run-windows '00:05:00-00:35:00'` | Override auto-detection, file mode only; offsets relative to activity start |

### Batch-specific metadata

Unlike a one-file invocation, a folder may contain runs at different treadmill speeds and using different HR sensors. Supply per-workout facts with an optional mapping (see [`examples/metadata.example.json`](examples/metadata.example.json)):

```shell
garmin-tcx-running-analyzer ./workouts --recursive --metadata ./my-metadata.json --output ./history.json
```

The keys are **exact basenames** (`activity.tcx`). If multiple files under subfolders have the same basename and metadata is supplied, the script reports an error instead of misassigning personal data. Do **not** commit personal `my-metadata.json` or workouts to your public fork.

Metadata can also include `subjective` observations. This is explicitly user-entered: the tool **never** derives pain or fatigue from HR/cadence measurements.

## JSON output

- **Single file:** same detailed structure as v1.0, including `total`, `runs`, `recoveries_between_runs`, `cooldown_first5min_after_running`, `lap_metadata`, `quality.warnings` and `subjective`.
- **Folder/multiple files:** `report_type: "tcx_running_collection"`; `summary` is archive statistics, `activities` is a chronological array of **complete individual reports**, `errors` lists failures.
- If any file fails, the combined JSON still contains valid workouts and errors, and process exits nonzero.

See [JSON_FORMAT.md](docs/JSON_FORMAT.md). Synthetic examples are provided in [`examples/`](examples/). **No real personal running activities are included in the repository.**

## Using the report with AI (optional)

An AI assistant can work from the JSON alone for routine analysis and comparisons, without parsing TCX every time. Send the generated JSON and **your own subjective sensations**. If `quality.warnings` indicate uncertain segmentation, inspect the original TCX instead of trusting the report blindly.

Optional prompt rules and skills are stored under [`agent/`](agent/README.md). These files are **not installed, enabled or auto-loaded** during ordinary tool use. The user/agent may copy or explicitly load them if desired.

## Test

```shell
python -m unittest discover -s tests -v
```

Tests use synthetic TCX fixtures, and CI checks Windows and Linux. [`CONTRIBUTING.md`](CONTRIBUTING.md) covers development.

## Limits / privacy

- TCX alone does **not** establish whether HR was recorded by a wrist sensor or a Polar H10.
- Garmin treadmill speed/distance can be miscalibrated; recorded distance is not a ground truth.
- Cadence/lap inference is a **heuristic**. Unusual sessions need verification.
- The `summary` aggregates only training measurements; it cannot establish medical risk or injury status.
- All analysis runs offline; no telemetry, uploads or accounts.

## License

[MIT](LICENSE). Commercial use, modification, copying and redistribution permitted; keep the copyright and license notice in distributed substantial copies. The project is independent and is not affiliated with Garmin.
