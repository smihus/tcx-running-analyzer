# Outdoor Running and GPS (v1.4.0)

The analyzer accepts TCX exports from supported devices for **treadmill or outdoor running**. Outdoor support does not depend on online services; the Python standard library is enough.

## Input and mode

- `--activity-mode auto` (default): GPS latitude/longitude on at least 5 samples and 25% of trackpoints indicates `outdoor`. A user-provided treadmill distance/speed indicates `treadmill`. Without enough evidence, mode is `unknown`—the TCX `Sport="Running"` attribute alone is not sufficient.
- Override with `--activity-mode outdoor` or `--activity-mode treadmill`; or include `"activity_mode":"outdoor"` in a per-file metadata record. The private AI workflow may save this when the athlete confirms it.
- Treadmill parameters are incompatible with a forced `outdoor` mode. Users must resolve contradictory inputs.
- Individual source records contain `source.activity_mode.value` and `source.activity_mode.provenance`.

## Time and segments

| Field | Meaning |
| --- | --- |
| `total.recorded_duration_s` / `total.elapsed_duration_s` | Wall-clock span of the first to last recorded TCX trackpoint. |
| `total.timer_duration_s` | Sum of all `Lap.TotalTimeSeconds` *if available for every lap*; not independently a guarantee of actual moving time. |
| `total.inferred_paused_duration_s` | Sum of **large sampling gaps with no increase in TCX cumulative distance**, only in outdoor mode. Inference, not proof of auto-pause. |
| `total.running_moving_duration_s` | Time inside recognized running bouts with inferred stationary pauses excluded. Also represented by `total.run_duration_s` in v1.4.0; the old field stays in place. |
| `outdoor.active_estimated_duration_s` | Elapsed duration minus inferred pauses. Includes walking and other activity, so **not equivalent to running duration**. |

Outdoor cadence detection still uses full steps/minute (compatible Garmin `RunCadence × 2`). Long stationary gaps are split out **before measuring each run's duration**, so a runner pausing their watch in the middle does not receive extra continuous-running credit. Distance-lap boundaries (e.g. 1 mile) are not converted to run/walk intervals. When no reliable cadence exists, a conservative speed-based fallback (`>=2.7 m/s`) is allowed and its classification is marked `low` confidence. Slow runners without cadence can remain `unknown`, which is preferable to guessing.

`movement.inferred_activity` is an **evidence-labelled heuristic**: `walking`, `running_or_mixed` or `unknown`. Neither the TCX sport label nor an algorithmic classification establishes a verified activity type. Observed walking gaps and brief transitions may be too short to become standalone running intervals. `movement.segments[]` partitions the outdoor elapsed timeline into `running`, `likely_walking`, `inferred_stationary` and `unknown`; each segment includes start/end timestamps, duration and a reason. `movement.likely_walking_duration_s` and `movement.unknown_duration_s` summarize corresponding durations. An observed high-cadence lap mean never forces the entire distance lap to be counted as running. Therefore long ultramarathons can produce **many more (and shorter) running segments** than v1.3.0: classification is heuristic, and user-verified walk/run breaks are preferable to invented certainty.

## GPS statistics

- `outdoor.gps_points`, `outdoor.gps_available`: evidence of coordinate data, never the coordinates themselves.
- `outdoor.distance_m`, `distance_source=TCX_DistanceMeters`: device cumulative-distance difference, **not an independently computed or corrected GPS geodesic**.
- `outdoor.pace_active_sec_per_km`, `outdoor.speed_active_kmh`: whole-activity distance divided by estimated active time; this covers running and walking and is **not** a pure running pace.
- `outdoor.elevation.gain_m/loss_m`: conservative 3-meter deadband over recorded TCX `AltitudeMeters`, subject to device noise and barometric/GPS errors.
- `outdoor.kilometer_splits[]`, `outdoor.mile_splits[]`: estimated **whole-activity** distance splits, with elapsed and pause-adjusted estimated active seconds. Timestamps between sparse device readings are linearly interpolated. Sections without movement evidence can remain uncertain.
- `outdoor.inferred_pauses[]`: UTC boundary timestamps, length and reason. `outdoor.unobserved_gaps[]` covers unusually large intervals where device distance changes or is unavailable; these are **not assumed paused**.
- `outdoor.gps_coordinates_included` is always `false`. Neither raw positions nor GPX routes leave the parser via JSON.

## Archive duplicate handling

In folder reports, same TCX activity IDs with approximately matching distance (within max of 25m / 0.2%) and elapsed time (within max of 10s / 0.1%), and matching sport, count **once** in summary. Both reports remain under `activities[]`, annotated with `source.identity_status` (`canonical` / `duplicate_export`) and `source.duplicate_of` on the duplicate. Separate variants can differ in timestamps or precision without matching SHA-256. If the same ID has conflicting distance/duration, records are retained and `summary.activity_id_conflicts[]` lists them. No personal TCX is altered or deleted.

`summary.activities_succeeded` is number of successfully parsed **files**, while `summary.unique_activities_counted` is the number counted for aggregate statistics. Read `summary.duplicate_activity_groups[]` before comparing individual `activities[]`.

## Caveats

- Large GPS gaps may represent device recording settings or lost signal, not always pauses. Inferred pauses require both an unusually long gap (at least 30s and 3.5× median sample gap) **and** near-zero TCX distance change. No distance means uncertainty. Unobserved moving/unknown-distance gaps of at least 60 seconds also interrupt confidently classified *running* time, but do **not** contribute to `inferred_paused_duration_s` or automatically reduce estimated whole-activity active time.
- Lap timer data cannot always establish active or moving time if the user paused recording in ways not exposed by TCX. Do not claim that estimated active seconds exactly equal TCX timer seconds.
- A fixed `--tz-offset` does not account for changing local daylight saving time or geography across a mixed outdoor collection. Use UTC for mixed public samples unless dates' real time zones are known.
- The private AI workflow and metadata remain optional; health observations and sensor identity are never inferred from GPS, cadence or HR.
- Don't add personal or third-party GPS tracks to the public Git repository; all tests use synthetic coordinates.

## Example

```powershell
.\Analyze-Tcx.ps1 -Path 'C:\Running\OutdoorSamples' -ActivityMode auto -Output 'C:\Running\OutdoorSummary.json' -UtcOffset '+00:00'
```

```sh
PYTHONPATH=src python -m tcx_running_analyzer ./outdoor --activity-mode auto --output ./outdoor.json
```

View the full JSON schema in [JSON_FORMAT.md](JSON_FORMAT.md).
