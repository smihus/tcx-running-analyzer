#!/usr/bin/env python3
"""Convert Garmin TCX running activities into compact, auditable JSON reports.

Python 3.10+, standard library only. Original TCX is never modified.
For indoor activities, Garmin speed/distance must not be assumed accurate.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

VERSION = "1.3.0"
NS = {
    "t": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "e": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
}


def number(value):
    if value is None:
        return None
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def rounded(value, digits=1):
    return round(value, digits) if value is not None and math.isfinite(value) else None


def mean(values):
    values = [x for x in values if x is not None and math.isfinite(x)]
    return statistics.fmean(values) if values else None


def maximum(values):
    values = [x for x in values if x is not None and math.isfinite(x)]
    return max(values) if values else None


def parse_dt(s):
    if not s:
        return None
    x = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if x.tzinfo is None:
        x = x.replace(tzinfo=timezone.utc)
    return x.astimezone(timezone.utc)


def parse_tz(s):
    s = s.strip()
    if len(s) != 6 or s[0] not in "+-" or s[3] != ":" or not (s[1:3] + s[4:]).isdigit():
        raise argparse.ArgumentTypeError("timezone offset must be +04:00 or -05:30")
    sign = 1 if s[0] == "+" else -1
    hh, mm = int(s[1:3]), int(s[4:])
    if hh > 14 or mm >= 60 or (hh == 14 and mm > 0):
        raise argparse.ArgumentTypeError("invalid timezone offset")
    return timezone(sign * timedelta(hours=hh, minutes=mm))


def iso(t, tz):
    return t.astimezone(tz).isoformat(timespec="seconds") if t else None


@dataclass
class Point:
    t: datetime
    hr: float | None
    cadence: float | None
    dist: float | None
    speed: float | None
    power: float | None


def load_tcx(file: Path):
    try:
        root = ET.parse(file).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Invalid TCX XML: {exc}") from exc
    a = root.find(".//t:Activity", NS)
    if a is None:
        raise ValueError("No TCX Activity found")
    activity_id = a.findtext("t:Id", default="", namespaces=NS)
    if not activity_id:
        raise ValueError("TCX activity has no Id")
    all_points = {}
    laps = []
    duplicates = 0
    for ix, l in enumerate(a.findall("t:Lap", NS), 1):
        start = parse_dt(l.attrib.get("StartTime"))
        dur = number(l.findtext("t:TotalTimeSeconds", namespaces=NS))
        ldist = number(l.findtext("t:DistanceMeters", namespaces=NS))
        lap_hr = number(l.findtext("t:AverageHeartRateBpm/t:Value", namespaces=NS))
        lap_max = number(l.findtext("t:MaximumHeartRateBpm/t:Value", namespaces=NS))
        lap_cad = number(l.findtext("t:Extensions/e:LX/e:AvgRunCadence", namespaces=NS))
        laps.append({"number": ix, "start": start, "seconds": dur, "garmin_m": ldist,
                     "avg_hr_reported": lap_hr, "max_hr_reported": lap_max,
                     "avg_run_cadence_raw": lap_cad})
        for tp in l.findall("t:Track/t:Trackpoint", NS):
            t = parse_dt(tp.findtext("t:Time", namespaces=NS))
            if t is None:
                continue
            hr = number(tp.findtext("t:HeartRateBpm/t:Value", namespaces=NS))
            raw = number(tp.findtext("t:Extensions/e:TPX/e:RunCadence", namespaces=NS))
            # Garmin RunningCadence is usually one-foot steps/min, doubled for total SPM.
            cad = 2 * raw if raw is not None else None
            dist = number(tp.findtext("t:DistanceMeters", namespaces=NS))
            speed = number(tp.findtext("t:Extensions/e:TPX/e:Speed", namespaces=NS))
            power = number(tp.findtext("t:Extensions/e:TPX/e:Watts", namespaces=NS))
            if t in all_points:
                duplicates += 1
                # Keep the last reading; Lap boundaries frequently repeat a timestamp.
            all_points[t] = Point(t, hr, cad, dist, speed, power)
    points = sorted(all_points.values(), key=lambda x: x.t)
    if not points:
        raise ValueError("No dated trackpoints in TCX")
    return activity_id, a.attrib.get("Sport"), points, laps, duplicates


def series_stats(points):
    hrs = [p.hr for p in points]
    cds = [p.cadence for p in points if p.cadence is not None and p.cadence > 0]
    dist = [p.dist for p in points if p.dist is not None]
    return {
        "hr_avg_bpm": rounded(mean(hrs)), "hr_max_bpm": rounded(maximum(hrs), 0),
        "cadence_avg_spm": rounded(mean(cds)),
        "distance_garmin_m": rounded(dist[-1] - dist[0], 1) if len(dist) >= 2 else None,
        "hr_last30s_avg_bpm": rounded(mean(hrs[-30:])) if hrs else None,
    }


def median_filter_flags(points, cadence_threshold=145, window=9):
    half = window // 2
    c = [p.cadence or 0 for p in points]
    out = []
    for i in range(len(points)):
        # median filter on cadence, no dependence on inaccurate Garmin speed
        vals = c[max(0, i-half):min(len(c), i+half+1)]
        out.append(statistics.median(vals) >= cadence_threshold)
    return out


def detect_runs(points, laps, threshold=145, min_seconds=45, join_gap=12):
    flags = median_filter_flags(points, threshold)
    # TCX manual laps with sustained running cadence are strong structural hints.
    # Avoid marking lengthy mixed laps as full runs: classify those from trackpoints.
    for lap in laps:
        duration, cad, start = lap["seconds"], lap["avg_run_cadence_raw"], lap["start"]
        if start is None or duration is None or cad is None:
            continue
        if 45 <= duration <= 1800 and cad * 2 >= threshold and cad * 2 <= 210:
            end = start + timedelta(seconds=duration)
            for i, p in enumerate(points):
                if start <= p.t < end:
                    flags[i] = True
    # Join short gaps caused by cadence transitions (including manual lap boundaries).
    runs=[]
    start=None
    for i,flag in enumerate(flags):
        if flag and start is None: start=i
        if start is not None and (not flag or i == len(flags)-1):
            end=i-1 if not flag else i
            runs.append([start,end])
            start=None
    merged=[]
    for a,b in runs:
        if merged and (points[a].t - points[merged[-1][1]].t).total_seconds() - 1 <= join_gap:
            merged[-1][1] = b
        else: merged.append([a,b])
    valid=[]
    for a,b in merged:
        dur = (points[b].t - points[a].t).total_seconds() + 1
        if dur >= min_seconds:
            valid.append((a,b))
    # Ignore short pre-workout cadence noise if genuine hand-marked run laps exist.
    # Garmin may briefly report 150+ cadence while walking around the gym.
    strong = [l for l in laps if l["start"] is not None and l["seconds"] is not None
              and l["avg_run_cadence_raw"] is not None
              and l["avg_run_cadence_raw"]*2 >= threshold
              and l["seconds"] >= min_seconds]
    if strong:
        earliest=min(l["start"] for l in strong)
        valid=[(a,b) for a,b in valid if points[b].t >= earliest-timedelta(seconds=10)]
    return valid


def align_run_windows(points, run_indices, laps):
    """Snap cadence-detected runs to Garmin's manual-lap timings when consistent.

    Manual laps are trusted for full running blocks. If a running block continues
    within a mixed lap, minute rounding is only done when within 20 seconds of
    the measured end; otherwise raw trackpoint boundaries are retained.
    """
    anchors=[]
    for l in laps:
        c, duration, start = l["avg_run_cadence_raw"], l["seconds"], l["start"]
        if start is not None and duration is not None and c is not None and c*2 >= 145 and duration >= 45:
            anchors.extend([start,start+timedelta(seconds=duration)])
    out=[]
    for a,b in run_indices:
        start=points[a].t
        end=points[b].t+timedelta(seconds=1)
        initial_start, initial_end=start,end
        def nearby(t, candidates, tolerance_s):
            if not candidates: return None
            closest=min(candidates,key=lambda x:abs((x-t).total_seconds()))
            return closest if abs((closest-t).total_seconds())<=tolerance_s else None
        new_start=nearby(start,anchors,25)
        if new_start: start=new_start
        new_end=nearby(end,anchors,25)
        if new_end: end=new_end
        else:
            # Garmin running cadence can linger briefly after treadmill stops.
            actual=(end-start).total_seconds()
            rounded_minutes=round(actual/60)*60
            if rounded_minutes>=45 and abs(actual-rounded_minutes)<=20:
                end=start+timedelta(seconds=rounded_minutes)
        if end<=start:
            start,end=initial_start,initial_end
        out.append((start,end,rounded((start-initial_start).total_seconds(),1),
                    rounded((end-initial_end).total_seconds(),1)))
    # If close adjacent run windows are now overlapping, merge the contiguous run.
    merged=[]
    for row in out:
        if merged and row[0] <= merged[-1][1]:
            prev=merged[-1]
            merged[-1]=(prev[0],max(prev[1],row[1]),prev[2],row[3])
        else:
            merged.append(row)
    return merged


def period(points, a, b):
    # [a,b) windows prevent double counting boundaries across segments.
    return [p for p in points if a <= p.t < b]


def exact_distance(points, a, b):
    # Use interpolated cumulative Garmin distance when available at boundaries.
    xs = [p for p in points if p.dist is not None]
    if len(xs) < 2 or a >= b:
        return None
    def val(t):
        if t <= xs[0].t: return xs[0].dist
        if t >= xs[-1].t: return xs[-1].dist
        lo, hi = 0, len(xs)-1
        while hi-lo>1:
            mid=(lo+hi)//2
            if xs[mid].t < t: lo=mid
            else: hi=mid
        v0,v1=xs[lo],xs[hi]
        secs=(v1.t-v0.t).total_seconds()
        frac=(t-v0.t).total_seconds()/secs if secs else 0
        return v0.dist + frac*(v1.dist-v0.dist)
    return max(0, val(b)-val(a))


def profile(points, a, b, tz, speed_kmh=None):
    ps=period(points,a,b)
    length=(b-a).total_seconds()
    if length <= 0 or not ps: return None
    result={"start_local":iso(a,tz),"end_local":iso(b,tz),"duration_s":rounded(length,1)}
    result.update(series_stats(ps))
    result["distance_garmin_m"] = rounded(exact_distance(points,a,b),1)
    result["hr_first30s_avg_bpm"] = rounded(mean([x.hr for x in period(points,a,min(a+timedelta(seconds=30),b))]))
    half=a+(b-a)/2
    result["hr_first_half_avg_bpm"] = rounded(mean([x.hr for x in period(points,a,half)]))
    result["hr_second_half_avg_bpm"] = rounded(mean([x.hr for x in period(points,half,b)]))
    result["cadence_first_half_spm"] = rounded(mean([x.cadence for x in period(points,a,half) if x.cadence and x.cadence>0]))
    result["cadence_second_half_spm"] = rounded(mean([x.cadence for x in period(points,half,b) if x.cadence and x.cadence>0]))
    result["hr_last30s_avg_bpm"] = rounded(mean([x.hr for x in period(points,max(a,b-timedelta(seconds=30)),b)]))
    result["five_minute_splits"] = []
    n=math.ceil(length/300)
    for i in range(n):
        x=a+timedelta(seconds=i*300)
        y=min(x+timedelta(seconds=300),b)
        s=period(points,x,y)
        if not s: continue
        result["five_minute_splits"].append({
            "from_min":rounded(i*5,1),"to_min":rounded((y-a).total_seconds()/60,1),
            "hr_avg_bpm":rounded(mean([p.hr for p in s])),
            "hr_max_bpm":rounded(maximum([p.hr for p in s]),0),
            "cadence_spm":rounded(mean([p.cadence for p in s if p.cadence and p.cadence>0]))
        })
    if speed_kmh is not None:
        expect=length * speed_kmh / 3.6
        result["treadmill_expected_running_m"] = rounded(expect,1)
        dg=exact_distance(points,a,b)
        result["garmin_distance_error_pct"] = rounded((dg/expect-1)*100,2) if dg is not None and expect>0 else None
    return result


def recovery(points, a, b, tz, kind):
    ps=period(points,a,b)
    if len(ps)<2: return None
    h=[p.hr for p in ps]
    nonempty=[v for v in h if v is not None]
    if not nonempty: return None
    return {
        "kind":kind, "start_local":iso(a,tz), "duration_s":rounded((b-a).total_seconds(),1),
        "start_hr_bpm":rounded(nonempty[0],0),
        "end_hr_bpm":rounded(nonempty[-1],0),
        "hr_drop_bpm":rounded(nonempty[0]-nonempty[-1],1),
        "hr_avg_bpm":rounded(mean(h)),
        "minute_avg_hr_bpm": [rounded(mean([p.hr for p in period(points,a+timedelta(seconds=60*i),min(b,a+timedelta(seconds=60*(i+1))))]))
                              for i in range(math.ceil((b-a).total_seconds()/60))]
    }



def run_detection_evidence(points, laps, start, end, method, start_shift=0, end_shift=0, threshold=145):
    """Heuristic quality indicators, NOT statistical/medical confidence."""
    ps = period(points, start, end)
    valid = [p for p in ps if p.cadence is not None]
    cadence_fraction = (sum(p.cadence >= threshold for p in valid) / len(valid)) if valid else None
    span = (end - start).total_seconds()
    overlap = 0.0
    for lap in laps:
        st, seconds, raw = lap['start'], lap['seconds'], lap['avg_run_cadence_raw']
        if st is None or seconds is None or raw is None or raw * 2 < threshold:
            continue
        overlap += max(0.0, (min(end, st + timedelta(seconds=seconds)) - max(start, st)).total_seconds())
    lap_coverage = min(1., overlap / span) if span > 0 else 0.
    if method == 'manual_windows':
        confidence = 'manual_override'
        reason = 'User-provided interval boundaries; accuracy not independently verified'
    elif cadence_fraction is None:
        confidence = 'low'
        reason = 'No cadence samples support classification'
    elif cadence_fraction >= .85 and lap_coverage >= .8 and max(abs(start_shift), abs(end_shift)) <= 15:
        confidence = 'high'
        reason = 'Sustained running cadence with consistent Garmin lap boundaries'
    elif cadence_fraction >= .7:
        confidence = 'medium'
        reason = 'Mostly supported by cadence, but lap evidence or transitions are weaker'
    else:
        confidence = 'low'
        reason = 'Weak cadence agreement with classified running window'
    return {
        'confidence': confidence,
        'method': method,
        'reason': reason,
        'cadence_support_fraction': rounded(cadence_fraction, 3),
        'running_lap_coverage_fraction': rounded(lap_coverage, 3),
        'boundary_shift_max_abs_s': rounded(max(abs(start_shift), abs(end_shift)), 1),
    }


def hr_jump_events(points, windows, tz, threshold=12):
    """List abrupt 1-second changes with the observed phase; do not infer sensor artifact."""
    if windows:
        first_run, last_run = windows[0][0], windows[-1][1]
    else:
        first_run = last_run = None
    events = []
    for previous, current in zip(points, points[1:]):
        if previous.hr is None or current.hr is None or (current.t - previous.t).total_seconds() != 1:
            continue
        change = current.hr - previous.hr
        if abs(change) < threshold:
            continue
        if first_run is None:
            phase = 'unclassified'
            run_index = None
        else:
            run_index = next((i for i, (a, b, _, _) in enumerate(windows, 1) if a <= current.t < b), None)
            if run_index is not None:
                phase = 'running'
            elif current.t < first_run:
                phase = 'pre_run_5min' if current.t >= first_run - timedelta(minutes=5) else 'before_running'
            elif current.t >= last_run:
                phase = 'post_run_5min' if current.t < last_run + timedelta(minutes=5) else 'after_running'
            else:
                phase = 'between_runs'
        events.append({
            'time_utc': iso(current.t, timezone.utc), 'time_local': iso(current.t, tz),
            'phase': phase, 'run_index': run_index,
            'hr_previous_bpm': rounded(previous.hr, 0),
            'hr_current_bpm': rounded(current.hr, 0),
            'delta_bpm': rounded(change, 0), 'absolute_delta_bpm': rounded(abs(change), 0),
            'sample_interval_s': 1,
        })
    return events


def group_hr_jump_episodes(events):
    """Group adjacent same-direction >=12-bpm changes into one episode.

    Preserve `hr_abrupt_jumps` unchanged for backwards compatibility. Grouping
    represents consecutive *measurement changes*, NOT the duration of raised HR.
    Distinct phases, gaps or opposite directions always start a new episode.
    """
    grouped = []
    for event in events:
        t = parse_dt(event['time_utc'])
        sign = 1 if event['delta_bpm'] > 0 else -1
        if (grouped
            and grouped[-1]['phase'] == event['phase']
            and grouped[-1]['run_index'] == event['run_index']
            and grouped[-1]['direction'] == ('rise' if sign > 0 else 'fall')
            and (t - parse_dt(grouped[-1]['end_utc'])).total_seconds() == 1):
            g = grouped[-1]
            g['end_utc'] = event['time_utc']
            g['end_local'] = event['time_local']
            g['hr_end_bpm'] = event['hr_current_bpm']
            g['net_delta_bpm'] = rounded(g['hr_end_bpm'] - g['hr_start_bpm'], 0)
            g['jump_samples'] += 1
            g['duration_s'] += 1
        else:
            start = t - timedelta(seconds=1)
            local_t = datetime.fromisoformat(event['time_local'])
            grouped.append({
                'start_utc': iso(start, timezone.utc),
                'end_utc': event['time_utc'],
                'start_local': iso(local_t - timedelta(seconds=1), local_t.tzinfo),
                'end_local': event['time_local'],
                'phase': event['phase'],
                'run_index': event['run_index'],
                'direction': 'rise' if sign > 0 else 'fall',
                'hr_start_bpm': event['hr_previous_bpm'],
                'hr_end_bpm': event['hr_current_bpm'],
                'net_delta_bpm': event['delta_bpm'],
                'duration_s': 1,
                'jump_samples': 1,
            })
    return grouped


def ambiguous_low_cadence_laps(laps, tz, cadence_threshold, min_seconds):
    """Surface review candidates, never silently classify low cadence as running."""
    result = []
    for lap in laps:
        raw = lap['avg_run_cadence_raw']
        duration = lap['seconds']
        if (lap['start'] is not None and raw is not None and duration is not None
            and duration >= min_seconds and 110 <= raw * 2 < cadence_threshold):
            result.append({
                'lap_number': lap['number'],
                'start_local': iso(lap['start'], tz),
                'duration_s': rounded(duration, 1),
                'avg_cadence_spm': rounded(raw * 2),
                'note': 'Below detection threshold; may be walking, running or mixed. Verify manually.',
            })
    return result


ISSUE_DESCRIPTIONS = {
    'RUN_SEGMENTS_NOT_FOUND': ('warning', 'No running bouts detected; check cadence and lap structure.'),
    'TRACKPOINT_GAPS': ('warning', 'Trackpoints contain gaps longer than two seconds.'),
    'HR_ABRUPT_JUMP': ('warning', 'One-second heart-rate change warrants inspection, not automatic artifact classification.'),
    'LAP_DISTANCE_MISMATCH': ('warning', 'Sum of lap distances differs from cumulative recorded distance.'),
    'LAP_DURATION_MISSING': ('warning', 'Lap duration is missing.'),
    'HR_SOURCE_UNKNOWN': ('info', 'TCX does not establish wrist vs chest HR sensor.'),
    'TREADMILL_DISTANCE': ('info', 'User-provided treadmill distance describes the whole treadmill session.'),
}


def issues_from_warnings(warnings):
    result=[]
    for message in warnings:
        code = message.split(':', 1)[0]
        severity, description = ISSUE_DESCRIPTIONS.get(code, ('warning','Unclassified diagnostic'))
        result.append({'code':code, 'severity':severity, 'description':description})
    return result


def summarize(file, tz, speed_kmh, treadmill_km, hr_source, settings, manual_windows=None):
    activity_id,sport,points,laps,dups=load_tcx(file)
    first,last=points[0].t,points[-1].t
    if manual_windows is not None:
        starts=[]
        for a,b in manual_windows:
            ta, tb = first+timedelta(seconds=a), first+timedelta(seconds=b)
            if ta < first or tb > last+timedelta(seconds=1) or tb <= ta:
                raise ValueError(f'run window {a}-{b}s lies outside available TCX trackpoints')
            starts.append((ta,tb,0.0,0.0))
    else:
        raw_runs=detect_runs(points,laps,**settings)
        starts=align_run_windows(points,raw_runs,laps)
    run_profiles=[]
    run_method = 'manual_windows' if manual_windows is not None else 'auto_cadence_plus_manual_laps'
    for ta,tb,start_shift,end_shift in starts:
        p=profile(points,ta,tb,tz,speed_kmh)
        if p is None:
            raise ValueError('run window contains no TCX samples')
        p["boundary_adjustment_s"]={"start":start_shift,"end":end_shift}
        p['detection'] = run_detection_evidence(
            points,laps,ta,tb,run_method,start_shift,end_shift,threshold=settings['threshold'])
        run_profiles.append(p)
    run_seconds=sum(x["duration_s"] for x in run_profiles)
    run_hr=[]; run_cad=[]
    for ta,tb,_,_ in starts:
        curr=period(points,ta,tb)
        run_hr += [p.hr for p in curr if p.hr is not None]
        run_cad += [p.cadence for p in curr if p.cadence is not None and p.cadence>0]
    recoveries=[]
    for (a1,b1,_,_),(a2,b2,_,_) in zip(starts,starts[1:]):
        rr=recovery(points,b1,a2,tz,"between_runs")
        if rr:recoveries.append(rr)
    if starts:
        begin=starts[0][0]
        finish=starts[-1][1]
        warm=recovery(points,max(first,begin-timedelta(minutes=5)),begin,tz,"pre_run_5min")
        cool=recovery(points,finish,min(last+timedelta(seconds=1),finish+timedelta(minutes=5)),tz,"post_run_5min")
    else:
        warm=cool=None
    distpoints=[p.dist for p in points if p.dist is not None]
    sum_laps=sum(l["garmin_m"] for l in laps if l["garmin_m"] is not None)
    total_garmin=distpoints[-1]-distpoints[0] if len(distpoints)>=2 else sum_laps
    dts=[(b.t-a.t).total_seconds() for a,b in zip(points,points[1:])]
    hdiffs=[abs(b.hr-a.hr) for a,b in zip(points,points[1:]) if a.hr is not None and b.hr is not None and (b.t-a.t).total_seconds()==1]
    missing_hr=sum(p.hr is None for p in points)
    maxdelta=max(hdiffs) if hdiffs else None
    jump_events=hr_jump_events(points,starts,tz)
    jump_episodes=group_hr_jump_episodes(jump_events)
    ambiguous_laps=ambiguous_low_cadence_laps(laps,tz,settings['threshold'],settings['min_seconds']) if not starts else []
    warnings=[]
    if not starts:
        warnings.append("RUN_SEGMENTS_NOT_FOUND: verify cadence data and manual laps")
    if jump_events:
        warnings.append("HR_ABRUPT_JUMP: review HR trace; this is not proof of a sensor artifact")
    if any(dt>2 for dt in dts):
        warnings.append("TRACKPOINT_GAPS: one or more gaps exceed 2 seconds")
    if treadmill_km is not None:
        warnings.append("TREADMILL_DISTANCE: entered for whole treadmill session; TCX may include non-treadmill walking")
    if len(distpoints)>=2 and abs(total_garmin - sum_laps)>5:
        warnings.append("LAP_DISTANCE_MISMATCH: sum of Lap distances differs from cumulative trackpoint total")
    if hr_source == "unknown":
        warnings.append("HR_SOURCE_UNKNOWN: TCX does not identify whether Polar H10 was connected")
    if len(laps)>1 and any(l["seconds"] is None for l in laps):
        warnings.append("LAP_DURATION_MISSING")
    issues=issues_from_warnings(warnings)
    confidences=[r['detection']['confidence'] for r in run_profiles]
    if not confidences:
        overall_confidence='none'
    elif 'low' in confidences:
        overall_confidence='low'
    elif 'medium' in confidences:
        overall_confidence='medium'
    elif 'manual_override' in confidences:
        overall_confidence='manual_override'
    else:
        overall_confidence='high'
    source_bytes=file.read_bytes()
    out={
        "schema_version":"1.0", "generator":{"name":"run_tcx_analyzer","version":VERSION},
        "source":{"filename":file.name,"sha256":sha256(source_bytes).hexdigest(),
                  "activity_id":activity_id,"sport":sport,
                  "hr_sensor":{"value":hr_source,"provenance":"manual_parameter" if hr_source != "unknown" else "not_present_in_tcx"}},
        "datetime":{"start_utc":iso(first,timezone.utc),"start_local":iso(first,tz),
                    "local_day_type":"weekend" if first.astimezone(tz).weekday()>=5 else "weekday",
                    "utc_offset":first.astimezone(tz).strftime("%z"),
                    "timezone_note":"fixed offset supplied by user; TCX times are UTC"},
        "total":{"recorded_duration_s":rounded((last-first).total_seconds(),1),
                 "garmin_distance_m":rounded(total_garmin,1),
                 "treadmill_distance_m":rounded(treadmill_km*1000,1) if treadmill_km is not None else None,
                 "hr_avg_bpm":rounded(mean([p.hr for p in points])),
                 "hr_max_bpm":rounded(maximum([p.hr for p in points]),0),
                 "run_duration_s":rounded(run_seconds,1),"run_count":len(run_profiles),
                 "run_hr_avg_bpm":rounded(mean(run_hr)),
                 "run_hr_max_bpm":rounded(maximum(run_hr),0),
                 "run_cadence_avg_spm":rounded(mean(run_cad)),
                 "longest_continuous_run_s":rounded(max((p["duration_s"] for p in run_profiles),default=0),1)},
        "warmup_last5min_before_running":warm,
        "runs":run_profiles,
        "recoveries_between_runs":recoveries,
        "cooldown_first5min_after_running":cool,
        "lap_metadata": [{"number":l["number"],"start_local":iso(l["start"],tz),
                          "duration_s":rounded(l["seconds"],1),"garmin_distance_m":rounded(l["garmin_m"],1),
                          "reported_hr_avg_bpm":l["avg_hr_reported"],"reported_hr_max_bpm":l["max_hr_reported"],
                          "reported_cadence_spm":rounded(2*l["avg_run_cadence_raw"],1) if l["avg_run_cadence_raw"] is not None else None} for l in laps],
        "quality":{"trackpoints_unique":len(points),"duplicate_boundary_timestamps":dups,
                   "missing_hr_points":missing_hr,
                   "median_sample_gap_s":rounded(statistics.median(dts),1) if dts else None,
                   "max_sample_gap_s":rounded(max(dts),1) if dts else None,
                   "max_1s_hr_change_bpm":rounded(maxdelta,0),
                   "run_detection":run_method,
                   "run_detection_confidence":overall_confidence,
                   "confidence_note":"Heuristic evidence only, not a probability or guarantee of correct segmentation.",
                   "cadence_threshold_spm":settings["threshold"],
                   "lap_distance_sum_m":rounded(sum_laps,1),
                   "hr_abrupt_jumps":jump_events,
                   "hr_jump_episodes":jump_episodes,
                   "hr_jump_episode_count":len(jump_episodes),
                   "unclassified_low_cadence_laps":ambiguous_laps,
                   "warnings":warnings,
                   "issues":issues,
                   "warning_count":sum(i['severity']=='warning' for i in issues),
                   "info_count":sum(i['severity']=='info' for i in issues)},
        "subjective":{"foot_pain":None,"foot_fatigue":None,"heel_pain":None,
                      "calf_fatigue":None,"back_pain":None,"overall_fatigue":None,
                      "notes":None,"provenance":"not_available_in_tcx"},
        "interpretation_rules":[
            "This is a technical summary, not a medical assessment.",
            "Garmin indoor distance/speed are estimates; treadmill reading overrides Garmin distance.",
            "Do not infer injury, feelings or chest-strap connection from TCX alone.",
            "Check detected run boundaries and heuristic confidence against manual laps for unfamiliar workouts.",
            "Info-level diagnostic records are missing context, not necessarily quality defects.",
            "Compare HR across workouts with the same HR sensor and similar running conditions."
        ]
    }
    return out

