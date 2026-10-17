"""Generate fake TCX activities; no sensitive or real athlete data."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import xml.etree.ElementTree as ET

NS="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
EXT="http://www.garmin.com/xmlschemas/ActivityExtension/v2"


def tag(ns,name):
    return f"{{{ns}}}{name}"


def synthetic_tcx(path: Path, *, start: datetime | None = None,
                  pattern: list[tuple[str,int,int,int]] | None = None,
                  include_hr: bool = True):
    """Generate TCX laps with one reading per second and boundary duplicates.

    Pattern tuple: ('run'|'walk', seconds, cadence_spm, hr_bpm).
    """
    if start is None:
        start=datetime(2026,1,1,16,0,0,tzinfo=timezone.utc)
    if pattern is None:
        pattern=[('walk',300,100,95),('run',300,166,122),('walk',60,100,110),
                 ('run',300,168,126),('walk',300,102,96)]
    root=ET.Element(tag(NS,'TrainingCenterDatabase'))
    activities=ET.SubElement(root,tag(NS,'Activities'))
    activity=ET.SubElement(activities,tag(NS,'Activity'),Sport='Running')
    ET.SubElement(activity,tag(NS,'Id')).text=start.isoformat().replace('+00:00','Z')
    elapsed=0
    cumulative=0.0
    for name,seconds,cad,hr in pattern:
        speed=6.0 if name=='run' else 5.0
        lap=ET.SubElement(activity,tag(NS,'Lap'),StartTime=(start+timedelta(seconds=elapsed)).isoformat().replace('+00:00','Z'))
        ET.SubElement(lap,tag(NS,'TotalTimeSeconds')).text=str(seconds)
        ET.SubElement(lap,tag(NS,'DistanceMeters')).text=f'{seconds*speed/3.6:.2f}'
        extent=ET.SubElement(lap,tag(NS,'Extensions'))
        lx=ET.SubElement(extent,tag(EXT,'LX'))
        ET.SubElement(lx,tag(EXT,'AvgRunCadence')).text=str(cad//2)
        track=ET.SubElement(lap,tag(NS,'Track'))
        for i in range(seconds+1):
            tp=ET.SubElement(track,tag(NS,'Trackpoint'))
            ET.SubElement(tp,tag(NS,'Time')).text=(start+timedelta(seconds=elapsed+i)).isoformat().replace('+00:00','Z')
            ET.SubElement(tp,tag(NS,'DistanceMeters')).text=f'{cumulative+i*speed/3.6:.4f}'
            if include_hr:
                hb=ET.SubElement(tp,tag(NS,'HeartRateBpm'))
                ET.SubElement(hb,tag(NS,'Value')).text=str(hr)
            ext=ET.SubElement(tp,tag(NS,'Extensions'))
            tpx=ET.SubElement(ext,tag(EXT,'TPX'))
            ET.SubElement(tpx,tag(EXT,'RunCadence')).text=str(cad//2)
            ET.SubElement(tpx,tag(EXT,'Speed')).text=str(speed/3.6)
        elapsed +=seconds
        cumulative +=seconds*speed/3.6
    path.parent.mkdir(parents=True,exist_ok=True)
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    return path
