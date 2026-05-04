"""Shared file parsers for GPX, TCX, and FIT formats.

Each parser extracts all available time-series fields into a pandas DataFrame
with a 'timestamp' column as the common join key.
"""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import gpxpy
    import gpxpy.gpx

    HAS_GPX = True
except ImportError:
    HAS_GPX = False

try:
    import fitdecode

    HAS_FIT = True
except ImportError:
    HAS_FIT = False

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Europe/Zurich")


def _to_local_naive(ts) -> pd.Timestamp | None:
    if ts is None:
        return None
    if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
        ts = ts.astimezone(TIMEZONE).replace(tzinfo=None)
    return ts


def _strip_ns(tag: str) -> str:
    """Remove XML namespace prefix from a tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


# ---------------------------------------------------------------------------
# GPX
# ---------------------------------------------------------------------------

def parse_gpx(gpx_file: Path) -> pd.DataFrame:
    """Parse a GPX file, extracting all trackpoint fields including extensions.

    Returns a DataFrame with one row per trackpoint. Core columns are
    timestamp, latitude, longitude, elevation. Extension fields (heart_rate,
    cadence, temperature, power, speed, etc.) are added when present.
    """
    if not HAS_GPX:
        logger.warning("gpxpy not installed — GPX parsing disabled")
        return pd.DataFrame()

    try:
        with open(gpx_file, "r") as f:
            gpx = gpxpy.parse(f)
    except Exception as e:
        logger.error(f"Error parsing GPX file {gpx_file}: {e}")
        return pd.DataFrame()

    points: list[dict] = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                row: dict = {
                    "timestamp": _to_local_naive(point.time),
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "altitude": point.elevation,
                }
                _extract_gpx_extensions(point, row)
                points.append(row)

    if not points:
        logger.warning(f"No track points found in {gpx_file.name}")
        return pd.DataFrame()

    df = pd.DataFrame(points)
    logger.info(f"Parsed {len(df)} GPS points with {len(df.columns)} columns from {gpx_file.name}")
    return df


_GPX_EXT_NAME_MAP = {
    "hr": "heart_rate",
    "heartrate": "heart_rate",
    "cad": "cadence",
    "runcadence": "cadence",
    "atemp": "temperature",
    "temp": "temperature",
    "speed": "speed",
    "power": "power",
    "distance": "distance",
}


def _normalize_ext_name(raw: str) -> str:
    key = raw.lower().replace(" ", "")
    return _GPX_EXT_NAME_MAP.get(key, key)


def _extract_gpx_extensions(point, row: dict):
    """Walk all extension elements under a GPX trackpoint."""
    for ext in point.extensions:
        _walk_extension_element(ext, row)


def _walk_extension_element(elem, row: dict):
    if len(elem) == 0:
        name = _normalize_ext_name(_strip_ns(elem.tag))
        try:
            row[name] = float(elem.text)
        except (TypeError, ValueError):
            row[name] = elem.text
    else:
        for child in elem:
            _walk_extension_element(child, row)


# ---------------------------------------------------------------------------
# TCX – trackpoint-level time-series
# ---------------------------------------------------------------------------

_TCX_NS = {
    "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ax": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
}


def parse_tcx(tcx_file: Path) -> pd.DataFrame:
    """Parse a TCX file extracting per-trackpoint time-series data.

    Returns a DataFrame with timestamp plus all available numeric fields
    (position, altitude, distance, heart_rate, cadence, speed, power, etc.).
    """
    try:
        tree = ET.parse(tcx_file)
        root = tree.getroot()
    except Exception as e:
        logger.error(f"Error parsing TCX file {tcx_file}: {e}")
        return pd.DataFrame()

    points: list[dict] = []
    for tp in root.iter(f"{{{_TCX_NS['tcx']}}}Trackpoint"):
        row: dict = {}

        time_el = tp.find("tcx:Time", _TCX_NS)
        if time_el is not None and time_el.text:
            ts = pd.to_datetime(time_el.text, utc=True, errors="coerce")
            if ts is not pd.NaT:
                row["timestamp"] = _to_local_naive(ts)

        pos = tp.find("tcx:Position", _TCX_NS)
        if pos is not None:
            lat = pos.findtext("tcx:LatitudeDegrees", None, _TCX_NS)
            lon = pos.findtext("tcx:LongitudeDegrees", None, _TCX_NS)
            if lat is not None:
                row["latitude"] = float(lat)
            if lon is not None:
                row["longitude"] = float(lon)

        _tcx_float(tp, "tcx:AltitudeMeters", "altitude", row)
        _tcx_float(tp, "tcx:DistanceMeters", "distance", row)

        hr_el = tp.find("tcx:HeartRateBpm/tcx:Value", _TCX_NS)
        if hr_el is not None and hr_el.text:
            row["heart_rate"] = float(hr_el.text)

        cad_el = tp.findtext("tcx:Cadence", None, _TCX_NS)
        if cad_el is not None:
            row["cadence"] = float(cad_el)

        _extract_tcx_extensions(tp, row)

        if row:
            points.append(row)

    if not points:
        logger.warning(f"No trackpoints found in {tcx_file.name}")
        return pd.DataFrame()

    df = pd.DataFrame(points)
    logger.info(
        f"Parsed {len(df)} trackpoints with {len(df.columns)} columns from {tcx_file.name}"
    )
    return df


def _tcx_float(parent, xpath: str, col_name: str, row: dict):
    text = parent.findtext(xpath, None, _TCX_NS)
    if text is not None:
        try:
            row[col_name] = float(text)
        except ValueError:
            pass


_TCX_EXT_NAME_MAP = {
    "speed": "speed",
    "runcadence": "run_cadence",
    "watts": "power",
    "avgspeed": "avg_speed",
    "maxbikecadence": "max_bike_cadence",
    "avgrunningcadence": "avg_run_cadence",
    "maxrunningcadence": "max_run_cadence",
    "stepcountactivity": "step_count",
}


def _extract_tcx_extensions(tp, row: dict):
    """Walk all extension elements under a TCX Trackpoint."""
    ext = tp.find("tcx:Extensions", _TCX_NS)
    if ext is None:
        return
    for child in ext.iter():
        if child.text and child.text.strip():
            tag = _strip_ns(child.tag).lower()
            mapped = _TCX_EXT_NAME_MAP.get(tag, tag)
            if mapped in ("extensions", "tpx"):
                continue
            try:
                row[mapped] = float(child.text)
            except ValueError:
                row[mapped] = child.text


# ---------------------------------------------------------------------------
# TCX – lap summaries (kept for watch_processor compatibility)
# ---------------------------------------------------------------------------

def parse_tcx_laps(tcx_file: Path) -> dict:
    """Parse TCX file returning lap-level summary data (legacy interface)."""
    try:
        tree = ET.parse(tcx_file)
        root = tree.getroot()
    except Exception as e:
        logger.error(f"Error parsing TCX file {tcx_file}: {e}")
        return {}

    ns = {"tcx": _TCX_NS["tcx"]}

    activity = root.find(".//tcx:Activity", ns)
    if activity is None:
        logger.warning(f"No activity found in {tcx_file.name}")
        return {}

    activity_type = activity.get("Sport", "Unknown")

    laps = []
    for lap in activity.findall(".//tcx:Lap", ns):
        lap_data = {
            "start_time": lap.get("StartTime"),
            "total_time_seconds": float(lap.findtext("tcx:TotalTimeSeconds", "0", ns)),
            "distance_meters": float(lap.findtext("tcx:DistanceMeters", "0", ns)),
            "calories": int(lap.findtext("tcx:Calories", "0", ns)),
            "avg_hr": int(
                lap.findtext(".//tcx:AverageHeartRateBpm/tcx:Value", "0", ns)
            ),
            "max_hr": int(
                lap.findtext(".//tcx:MaximumHeartRateBpm/tcx:Value", "0", ns)
            ),
        }
        laps.append(lap_data)

    logger.info(f"Parsed TCX file {tcx_file.name}: {activity_type} with {len(laps)} laps")
    return {"activity_type": activity_type, "laps": laps}


# ---------------------------------------------------------------------------
# FIT
# ---------------------------------------------------------------------------

def parse_fit(fit_file: Path) -> pd.DataFrame:
    """Parse a FIT file extracting all fields from 'record' messages.

    Returns a DataFrame with one row per record. Common fields include
    timestamp, heart_rate, cadence, speed, power, position_lat, position_long,
    altitude, distance, temperature, etc. — whatever the device recorded.
    """
    if not HAS_FIT:
        logger.warning("fitdecode not installed — FIT parsing disabled. Install: uv add fitdecode")
        return pd.DataFrame()

    try:
        records: list[dict] = []
        with fitdecode.FitReader(str(fit_file)) as fit:
            for frame in fit:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                if frame.name != "record":
                    continue

                row: dict = {}
                for field in frame.fields:
                    if field.value is None:
                        continue
                    name = field.name
                    value = field.value

                    if name == "timestamp":
                        value = _to_local_naive(value)
                    elif name in ("position_lat", "position_long"):
                        # FIT stores positions in semicircles; convert to degrees
                        value = value * (180.0 / 2**31)

                    row[name] = value
                records.append(row)

        if not records:
            logger.warning(f"No record messages found in {fit_file.name}")
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Normalize column names to match GPX/TCX conventions
        rename = {
            "position_lat": "latitude",
            "position_long": "longitude",
        }
        # Only rename enhanced_* if the raw version doesn't exist;
        # otherwise keep both (raw stays as-is, enhanced keeps its name)
        for raw, enhanced in [("altitude", "enhanced_altitude"), ("speed", "enhanced_speed")]:
            if enhanced in df.columns and raw not in df.columns:
                rename[enhanced] = raw
        df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

        logger.info(
            f"Parsed {len(df)} records with {len(df.columns)} columns from {fit_file.name}"
        )
        return df

    except Exception as e:
        logger.error(f"Error parsing FIT file {fit_file}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

_EXTENSIONS = {".gpx", ".tcx", ".fit"}


def find_participant_files(
    data_dir: Path,
) -> dict[str, list[dict[str, Path | int | str]]]:
    """Discover GPX/TCX/FIT files grouped by participant ID.

    Handles multiple activities per participant (e.g., SM001_1.gpx, SM001_2.fit).

    Returns dict mapping participant IDs to lists of activity file sets:
        {'SM001': [{'gpx': Path, 'fit': Path, 'activity_num': 1, 'file_id': 'SM001'}, ...]}
    """
    data_dir = Path(data_dir)
    all_files = [
        f
        for f in data_dir.iterdir()
        if f.is_file() and f.suffix.lower() in _EXTENSIONS
    ]

    stems: dict[str, dict[str, Path]] = {}
    for f in all_files:
        stem = f.stem
        ext = f.suffix.lower().lstrip(".")
        stems.setdefault(stem, {})[ext] = f

    participants: dict[str, list[dict]] = {}
    for stem, files_by_ext in stems.items():
        match = re.match(r"^([A-Za-z0-9]+?)(?:_(\d+))?$", stem)
        if match:
            pid = match.group(1)
            activity_num = int(match.group(2)) if match.group(2) else 1
        else:
            pid = stem
            activity_num = 1

        entry: dict = {
            "activity_num": activity_num,
            "file_id": stem,
            **files_by_ext,
        }
        participants.setdefault(pid, []).append(entry)

    for pid in participants:
        participants[pid].sort(key=lambda x: x["activity_num"])

    total = sum(len(acts) for acts in participants.values())
    logger.info(f"Found {len(participants)} participants with {total} total activities")
    return participants