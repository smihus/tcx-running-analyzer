"""Outdoor/indoor-neutral measurements, with no raw GPS coordinates in reports.

Derived metrics are estimates based on TCX samples, not proof of physical motion,
GPS accuracy, or the state of a Garmin auto-pause setting.
"""
from __future__ import annotations

from datetime import timedelta
import math
import statistics


def _median(values):
    return statistics.median(values) if values else None


def infer_mode(points, requested="auto", treadmill=False):
    if requested != "auto":
        return requested, "user_override"
    if treadmill:
        return "treadmill", "user_treadmill_parameters"
    gps = sum(p.lat is not None and p.lon is not None for p in points)
    if gps >= 5 and gps >= len(points) * 0.25:
        return "outdoor", "gps_coordinates_present"
    return "unknown", "insufficient_mode_evidence"


def detect_pauses(points, mode):
    """Only strong stationary, long sampling gaps qualify as inferred pauses.

    Sparse GPS samples (e.g. 8–13 s) are normal; gaps without available
    distance readings remain *unobserved*, not confirmed paused time.
    """
    if mode != "outdoor" or len(points) < 3:
        return [], []
    dts = [(b.t - a.t).total_seconds() for a, b in zip(points, points[1:])]
    positive = [d for d in dts if d > 0]
    median = _median(positive) or 1.0
    threshold = max(30.0, median * 3.5)
    pauses, gaps = [], []
    for a, b, dt in zip(points, points[1:], dts):
        if dt < threshold:
            continue
        delta = b.dist - a.dist if a.dist is not None and b.dist is not None else None
        entry = {"start_utc": a.t.isoformat(timespec="seconds"),
                 "end_utc": b.t.isoformat(timespec="seconds"),
                 "duration_s": round(dt, 1),
                 "distance_change_m": round(delta, 1) if delta is not None else None}
        if delta is not None and -2 <= delta <= 3:
            entry["classification"] = "inferred_pause"
            entry["reason"] = "long_sample_gap_with_no_distance_progress"
            pauses.append((a.t, b.t, entry))
        else:
            entry["classification"] = "unobserved_gap"
            entry["reason"] = "large_sample_gap_with_movement_or_unknown_distance"
            gaps.append(entry)
    return pauses, gaps


def split_runs_at_pauses(windows, pauses, first, last):
    """Split running bouts without counting long inferred pauses as running.

    Never extrapolate an outdoor run past last observation. Explicit user
    windows remain user assertions, but pauses are still annotated separately.
    """
    limit = last
    out = []
    for a, b, start_shift, end_shift in windows:
        a, b = max(first, a), min(limit, b)
        if b <= a:
            continue
        cursor = a
        for ps, pe, _ in pauses:
            if pe <= cursor or ps >= b:
                continue
            if ps > cursor:
                out.append((cursor, min(ps, b), start_shift, 0.0))
            cursor = max(cursor, pe)
            if cursor >= b:
                break
        if cursor < b:
            out.append((cursor, b, 0.0 if cursor != a else start_shift, end_shift))
    return [r for r in out if (r[1]-r[0]).total_seconds() > 0]


def classify_activity(points, mode, has_runs):
    cad = [p.cadence for p in points if p.cadence is not None and p.cadence > 0]
    speeds = [p.speed for p in points if p.speed is not None and p.speed > 0]
    mc = _median(cad)
    ms = _median(speeds)
    if has_runs:
        return {"value": "running_or_mixed", "confidence": "heuristic",
                "reason": "sustained_running_segments_detected",
                "median_cadence_spm": round(mc, 1) if mc is not None else None,
                "median_device_speed_mps": round(ms, 2) if ms is not None else None}
    if mode == "outdoor" and mc is not None and 80 <= mc <= 140 and ms is not None and .5 <= ms <= 2.5:
        return {"value": "walking", "confidence": "heuristic",
                "reason": "sustained_low_cadence_and_walking_speed",
                "median_cadence_spm": round(mc, 1), "median_device_speed_mps": round(ms, 2)}
    return {"value": "unknown", "confidence": "insufficient_evidence",
            "reason": "no_reliably_classified_running_or_walking",
            "median_cadence_spm": round(mc, 1) if mc is not None else None,
            "median_device_speed_mps": round(ms, 2) if ms is not None else None}


def elevation_summary(points):
    """GPS altitude changes after conservative 3m deadband, no false precision."""
    alt = [p.alt for p in points if p.alt is not None and math.isfinite(p.alt)]
    if len(alt) < 3:
        return {"gain_m": None, "loss_m": None, "sample_count": len(alt),
                "method": "3m_deadband_on_recorded_altitude"}
    last = alt[0]
    up = down = 0.0
    for value in alt[1:]:
        change = value - last
        if abs(change) >= 3:
            if change > 0: up += change
            else: down -= change
            last = value
    return {"gain_m": round(up, 1), "loss_m": round(down, 1),
            "sample_count": len(alt), "method": "3m_deadband_on_recorded_altitude"}


def distance_splits(points, pauses, unit_m=1000):
    """Full-distance splits using cumulative Garmin distance (not spherical GPS path).

    Interpolates between valid monotonic distance trackpoints. Split clock time
    is adjusted for *inferred* stopped-timer gaps, while elapsed is preserved.
    """
    track = [(p.t,p.dist) for p in points if p.dist is not None]
    if len(track) < 2 or track[-1][1] <= track[0][1]:
        return []
    start_t, start_d = track[0]
    end_d = track[-1][1]
    marker = start_d + unit_m
    last_t = start_t
    results = []
    def pause_intersection(a,b):
        return sum(max(0.0,(min(b,pe)-max(a,ps)).total_seconds())
                   for ps,pe,_ in pauses if ps < b and pe > a)
    for (ta, da), (tb, db) in zip(track, track[1:]):
        if db < da:
            continue  # reset/nonmonotonic device distance: no spurious split
        while db >= marker and db > da:
            frac = (marker-da)/(db-da)
            at = ta + (tb-ta)*frac
            elapsed = (at-last_t).total_seconds()
            active = max(0, elapsed-pause_intersection(last_t,at))
            results.append({"index":len(results)+1, "distance_m": round(unit_m,1),
                            "end_utc":at.isoformat(timespec="seconds"),
                            "elapsed_s":round(elapsed,1), "active_estimated_s":round(active,1),
                            "pace_active_sec_per_km":round(active/(unit_m/1000),1) if active else None})
            marker += unit_m
            last_t = at
    return results


def outdoor_metrics(points, mode, pauses, gaps, elapsed_s, running_moving_s):
    gps = sum(p.lat is not None and p.lon is not None for p in points)
    dist = [p.dist for p in points if p.dist is not None]
    distance = max(0, dist[-1]-dist[0]) if len(dist) >= 2 else None
    paused = sum((pe-ps).total_seconds() for ps,pe,_ in pauses)
    active = max(0.0, elapsed_s-paused)
    out = {"mode": mode,
           "gps_points": gps,
           "gps_available": gps >= 5,
           "distance_source":"Garmin_DistanceMeters" if distance is not None else "unknown",
           "elapsed_duration_s":round(elapsed_s,1),
           "active_estimated_duration_s":round(active,1),
           "inferred_paused_duration_s":round(paused,1),
           "running_moving_duration_s":round(running_moving_s,1),
           "distance_m":round(distance,1) if distance is not None else None,
           "pace_active_sec_per_km":round(active/(distance/1000),1) if distance and active else None,
           "speed_active_kmh":round((distance/1000)/(active/3600),2) if distance and active else None,
           "elevation":elevation_summary(points),
           "inferred_pauses":[e for _,_,e in pauses],
           "unobserved_gaps":gaps,
           "gps_coordinates_included":False,
           "note":"GPS position is only used to detect availability. No raw coordinates are exported."}
    if mode == "outdoor":
        out["kilometer_splits"] = distance_splits(points,pauses,1000)
        out["mile_splits"] = distance_splits(points,pauses,1609.344)
    else:
        out["kilometer_splits"] = []
        out["mile_splits"] = []
    return out


def detect_speed_runs(points, min_seconds=45, threshold_mps=2.7):
    """Conservative outdoor fallback only when cadence is largely unavailable.

    Device-recorded Speed is preferred. No speed means 'unknown', not walking.
    This deliberately misses slow jogging rather than claiming that walking
    or uncertain intervals are running. The calling report marks low confidence.
    """
    usable = sum(p.cadence is not None and p.cadence > 0 for p in points)
    if usable >= max(5, len(points)*.2):
        return []
    flags = [p.speed is not None and p.speed >= threshold_mps for p in points]
    spans = []
    start = None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        if start is not None and (not flag or i == len(points)-1):
            end = i-1 if not flag else i
            if (points[end].t-points[start].t).total_seconds() >= min_seconds:
                spans.append((start,end))
            start = None
    return spans


def movement_timeline(points, windows, pauses, unobserved_gaps, tz):
    """Partition outdoor elapsed time into evidence-labelled movement phases.

    'likely_walking' requires independent cadence and speed/distance support.
    Unknown gaps remain unknown; a TCX is not a precise activity classifier.
    """
    if len(points) < 2:
        return []
    first, last = points[0].t, points[-1].t
    uncertain = [(datetime_from_iso(g['start_utc']),datetime_from_iso(g['end_utc']))
                 for g in unobserved_gaps if g['duration_s'] >= 60]
    windows = [(max(first,a),min(last,b)) for a,b,*_ in windows]
    bounds = {first,last}
    for a,b in windows:
        bounds.update((a,b))
    for a,b,_ in pauses:
        bounds.update((a,b))
    for a,b in uncertain:
        bounds.update((a,b))
    ordered = sorted(x for x in bounds if first <= x <= last)
    out = []
    for a,b in zip(ordered,ordered[1:]):
        duration = (b-a).total_seconds()
        if duration <= 0:
            continue
        if any(a>=ps and b<=pe for ps,pe,_ in pauses):
            label, reason = 'inferred_stationary', 'no_distance_progress_during_long_gap'
        elif any(a>=gs and b<=ge for gs,ge in uncertain):
            label, reason = 'unknown', 'large_unobserved_moving_or_unknown_gap'
        elif any(a>=rs and b<=re for rs,re in windows):
            label, reason = 'running', 'cadence_or_confirmed_window'
        else:
            subset = [p for p in points if a<=p.t<b]
            cadence = _median([p.cadence for p in subset if p.cadence is not None and p.cadence>0])
            track = [p for p in points if a<=p.t<=b and p.dist is not None]
            v = max(0,track[-1].dist-track[0].dist)/duration if len(track)>1 else None
            if cadence is not None and 85<=cadence<=140 and v is not None and .3<=v<=2.6:
                label, reason = 'likely_walking','low_cadence_and_device_distance_progress'
            else:
                label, reason = 'unknown','insufficient_motion_evidence'
        entry = {'start_utc':a.isoformat(timespec='seconds'),
                 'end_utc':b.isoformat(timespec='seconds'),
                 'start_local':a.astimezone(tz).isoformat(timespec='seconds'),
                 'end_local':b.astimezone(tz).isoformat(timespec='seconds'),
                 'duration_s':round(duration,1), 'kind':label,'reason':reason}
        if out and out[-1]['kind']==label and out[-1]['reason']==reason and out[-1]['end_utc']==entry['start_utc']:
            prev=out[-1]
            prev['end_utc']=entry['end_utc']; prev['end_local']=entry['end_local']
            prev['duration_s']=round(prev['duration_s']+entry['duration_s'],1)
        else:
            out.append(entry)
    return out


def datetime_from_iso(value):
    from datetime import datetime
    return datetime.fromisoformat(value)
