"""Fill non-watch participants by borrowing squad references.

For participants that did not wear a watch, this module:
  * groups participants by squad (from participants_2026.csv)
  * picks one reference participant per squad that has watch data — chosen as
    the one whose GPS crossing duration (end - start) is closest to the squad
    median, to avoid obviously broken traces
  * copies the reference's GPS positions with the non-watch participant's
    user_id
  * reads hr.parquet from the admin station directory, trims to the reference
    window, resamples to 1-minute means and appends to march_timeseries_data.csv
  * appends an entry in gps_crossing_times.json so the downstream step/temp
    processors trim acc/temp parquets to the same window
  * computes health_metrics + hr_zones rows from the borrowed HR data

The script is meant to run *after* process_watch_data.py and *before*
process_step_data.py / process_temp_data.py.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Europe/Zurich")

HR_ZONE_COLUMNS = [
    "very_light_percent",
    "light_percent",
    "moderate_percent",
    "intense_percent",
    "beast_mode_percent",
]


def _load_participants(participants_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(participants_csv)
    required = {"participant_id", "squad"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"participants CSV missing columns: {sorted(missing)}")
    return df


def _pick_reference(
    squad: str,
    candidates: list[str],
    crossing_times: dict[str, dict],
) -> str | None:
    """Pick the watch participant in a squad whose duration is closest to the median.

    Participants without both start and end in gps_crossing_times are ignored.
    Returns None if the squad has no usable watch participants.
    """
    durations: dict[str, float] = {}
    for pid in candidates:
        times = crossing_times.get(pid)
        if not times or "start" not in times or "end" not in times:
            continue
        start = pd.to_datetime(times["start"])
        end = pd.to_datetime(times["end"])
        if pd.isna(start) or pd.isna(end) or end <= start:
            continue
        durations[pid] = (end - start).total_seconds()

    if not durations:
        return None

    if len(durations) <= 2:
        ref = sorted(durations.keys())[0]
        logger.info(
            f"Squad {squad}: only {len(durations)} usable watch participants, picking first -> {ref}"
        )
        return ref

    median_duration = pd.Series(list(durations.values())).median()
    ref = min(durations.items(), key=lambda kv: abs(kv[1] - median_duration))[0]
    logger.info(
        f"Squad {squad}: median duration {median_duration:.0f}s, "
        f"picked reference {ref} ({durations[ref]:.0f}s)"
    )
    return ref


def _load_hr_parquet(
    station_dir: Path, participant_id: str, start: datetime, end: datetime
) -> pd.DataFrame | None:
    """Load hr.parquet for a participant, convert to Europe/Zurich local (naive), trim to window."""
    participant_dir = station_dir / participant_id
    if not participant_dir.is_dir():
        logger.warning(f"{participant_id}: no station directory at {participant_dir}")
        return None

    hr_files = sorted(participant_dir.glob("*/hr.parquet"))
    if not hr_files:
        logger.warning(f"{participant_id}: no hr.parquet under {participant_dir}")
        return None

    frames = []
    for hr_file in hr_files:
        df = pd.read_parquet(hr_file)
        if "BPM" not in df.columns:
            logger.warning(f"{participant_id}: {hr_file} missing BPM column")
            continue
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(TIMEZONE).tz_localize(None)
        frames.append(df[["BPM"]])

    if not frames:
        return None

    df_hr = pd.concat(frames).sort_index()
    df_hr = df_hr[(df_hr.index >= start) & (df_hr.index <= end)]
    if df_hr.empty:
        logger.warning(
            f"{participant_id}: no HR samples inside [{start}, {end}] — "
            f"squad reference window does not overlap the parquet"
        )
        return None
    return df_hr


def _build_timeseries_rows(
    march_id: int,
    user_id: str,
    df_hr: pd.DataFrame,
    reference_start: datetime,
    reference_timeseries: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Resample HR to 1-minute means matching the watch timeseries layout.

    Non-watch participants in a squad walked alongside the reference watch
    participant, so we copy the reference's per-minute speed_kmh and
    cumulative_distance_km (matched on timestamp) instead of assuming a
    constant pace.
    """
    resampled = (
        df_hr.rename(columns={"BPM": "heart_rate"})
        .resample("1min")
        .mean()
        .dropna(subset=["heart_rate"])
        .reset_index()
        .rename(columns={"Time": "timestamp"})
    )
    resampled["timestamp_minutes"] = (
        (resampled["timestamp"] - pd.Timestamp(reference_start)).dt.total_seconds() / 60
    )
    resampled = resampled[resampled["timestamp_minutes"] >= 0]

    if reference_timeseries is not None and not reference_timeseries.empty:
        ref_cols = reference_timeseries[
            ["timestamp", "speed_kmh", "cumulative_distance_km"]
        ].copy()
        ref_cols["timestamp"] = pd.to_datetime(ref_cols["timestamp"])
        resampled = resampled.merge(ref_cols, on="timestamp", how="left")
        speed = resampled["speed_kmh"]
        cumulative_distance = resampled["cumulative_distance_km"]
    else:
        speed = np.nan
        cumulative_distance = np.nan

    out = pd.DataFrame(
        {
            "march_id": march_id,
            "user_id": user_id,
            "timestamp": resampled["timestamp"],
            "timestamp_minutes": resampled["timestamp_minutes"],
            "heart_rate": resampled["heart_rate"],
            "steps": np.nan,
            "speed_kmh": speed,
            "cumulative_distance_km": cumulative_distance,
        }
    )
    return out


def _build_health_metrics_row(
    march_id: int,
    user_id: str,
    df_hr: pd.DataFrame,
    reference_pace_kmh: float | None = None,
    reference_distance_km: float | None = None,
) -> dict:
    hr = df_hr["BPM"].dropna()
    duration_minutes = int(
        round((df_hr.index.max() - df_hr.index.min()).total_seconds() / 60)
    )
    return {
        "march_id": march_id,
        "user_id": user_id,
        "avg_hr": round(float(hr.mean()), 1) if not hr.empty else None,
        "max_hr": int(hr.max()) if not hr.empty else None,
        "total_steps": np.nan,
        "march_duration_minutes": duration_minutes,
        "avg_pace_kmh": (
            round(float(reference_pace_kmh), 2)
            if reference_pace_kmh is not None and not pd.isna(reference_pace_kmh)
            else np.nan
        ),
        "estimated_distance_km": (
            round(float(reference_distance_km), 2)
            if reference_distance_km is not None and not pd.isna(reference_distance_km)
            else np.nan
        ),
        "data_completeness": round(float(hr.notna().sum()) / max(len(df_hr), 1), 3),
    }


def _build_hr_zones_row(march_id: int, user_id: str, df_hr: pd.DataFrame) -> dict:
    hr = df_hr["BPM"].dropna()
    total = len(hr)
    if total == 0:
        zones = {col: 0.0 for col in HR_ZONE_COLUMNS}
    else:
        zones = {
            "very_light_percent": round(float((hr < 100).sum()) / total * 100, 2),
            "light_percent": round(
                float(((hr >= 100) & (hr < 120)).sum()) / total * 100, 2
            ),
            "moderate_percent": round(
                float(((hr >= 120) & (hr < 140)).sum()) / total * 100, 2
            ),
            "intense_percent": round(
                float(((hr >= 140) & (hr < 160)).sum()) / total * 100, 2
            ),
            "beast_mode_percent": round(float((hr >= 160).sum()) / total * 100, 2),
        }
    return {"march_id": march_id, "user_id": user_id, **zones}


def _copy_gps_for_user(
    gps_df: pd.DataFrame, reference_id: str, target_id: str
) -> pd.DataFrame:
    ref_rows = gps_df[gps_df["user_id"] == reference_id].copy()
    if ref_rows.empty:
        return ref_rows
    ref_rows["user_id"] = target_id
    return ref_rows


def fill_non_watch(
    output_dir: Path,
    station_dir: Path,
    participants_csv: Path,
    march_id: int,
) -> None:
    output_dir = Path(output_dir)
    station_dir = Path(station_dir)

    timeseries_path = output_dir / "march_timeseries_data.csv"
    gps_path = output_dir / "march_gps_positions.csv"
    health_path = output_dir / "march_health_metrics.csv"
    zones_path = output_dir / "march_hr_zones.csv"
    crossings_path = output_dir / "gps_crossing_times.json"

    for path in (timeseries_path, gps_path, health_path, zones_path, crossings_path):
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    participants = _load_participants(participants_csv)
    with open(crossings_path, "r") as f:
        crossing_times = json.load(f)

    df_timeseries = pd.read_csv(timeseries_path)
    df_timeseries["timestamp"] = pd.to_datetime(df_timeseries["timestamp"])
    df_gps = pd.read_csv(gps_path)
    df_health = pd.read_csv(health_path)
    df_zones = pd.read_csv(zones_path)

    watch_ids = set(df_timeseries["user_id"].unique())
    logger.info(
        f"Found {len(watch_ids)} watch participants, "
        f"{len(participants) - len(watch_ids)} without watch data"
    )

    new_ts_frames: list[pd.DataFrame] = []
    new_gps_frames: list[pd.DataFrame] = []
    new_health_rows: list[dict] = []
    new_zones_rows: list[dict] = []
    added_crossings: dict[str, dict] = {}

    squads = participants.groupby("squad")
    for squad, squad_df in squads:
        squad_ids = squad_df["participant_id"].tolist()
        squad_watch = [pid for pid in squad_ids if pid in watch_ids]
        squad_missing = [pid for pid in squad_ids if pid not in watch_ids]

        if not squad_missing:
            continue

        reference = _pick_reference(squad, squad_watch, crossing_times)
        if reference is None:
            logger.warning(
                f"Squad {squad}: no watch data available — skipping "
                f"{len(squad_missing)} participants. This should not happen."
            )
            continue

        ref_times = crossing_times[reference]
        ref_start = pd.to_datetime(ref_times["start"]).to_pydatetime()
        ref_end = pd.to_datetime(ref_times["end"]).to_pydatetime()

        ref_timeseries = df_timeseries[df_timeseries["user_id"] == reference]
        ref_health = df_health[df_health["user_id"] == reference]
        ref_pace = (
            float(ref_health["avg_pace_kmh"].iloc[0])
            if not ref_health.empty and "avg_pace_kmh" in ref_health.columns
            else None
        )
        ref_distance = (
            float(ref_health["estimated_distance_km"].iloc[0])
            if not ref_health.empty and "estimated_distance_km" in ref_health.columns
            else None
        )
        logger.info(
            f"Squad {squad}: filling {len(squad_missing)} non-watch participants from {reference} "
            f"(reference pace={ref_pace:.2f} km/h, distance={ref_distance:.2f} km)"
            if ref_pace is not None and not pd.isna(ref_pace)
            else f"Squad {squad}: filling {len(squad_missing)} non-watch participants from {reference}"
        )

        for target_id in squad_missing:
            df_hr = _load_hr_parquet(station_dir, target_id, ref_start, ref_end)
            if df_hr is None or df_hr.empty:
                logger.warning(f"{target_id}: no usable HR data, skipping")
                continue

            ts_rows = _build_timeseries_rows(
                march_id,
                target_id,
                df_hr,
                ref_start,
                reference_timeseries=ref_timeseries,
            )
            if ts_rows.empty:
                logger.warning(f"{target_id}: HR produced zero timeseries rows")
                continue
            new_ts_frames.append(ts_rows)

            gps_rows = _copy_gps_for_user(df_gps, reference, target_id)
            if not gps_rows.empty:
                new_gps_frames.append(gps_rows)

            new_health_rows.append(
                _build_health_metrics_row(
                    march_id,
                    target_id,
                    df_hr,
                    reference_pace_kmh=ref_pace,
                    reference_distance_km=ref_distance,
                )
            )
            new_zones_rows.append(_build_hr_zones_row(march_id, target_id, df_hr))

            added_crossings[target_id] = {
                "start": ref_times["start"],
                "end": ref_times["end"],
            }

    if not new_ts_frames:
        logger.info("No non-watch participants filled — outputs unchanged")
        return

    logger.info(f"Filled {len(new_ts_frames)} non-watch participants")

    df_timeseries_out = pd.concat([df_timeseries, *new_ts_frames], ignore_index=True)
    df_timeseries_out = df_timeseries_out.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    df_timeseries_out.to_csv(timeseries_path, index=False)
    logger.info(f"Updated {timeseries_path} ({len(df_timeseries_out)} rows)")

    if new_gps_frames:
        df_gps_out = pd.concat([df_gps, *new_gps_frames], ignore_index=True)
        df_gps_out.to_csv(gps_path, index=False)
        logger.info(f"Updated {gps_path} ({len(df_gps_out)} rows)")

    if new_health_rows:
        df_health_out = pd.concat(
            [df_health, pd.DataFrame(new_health_rows)], ignore_index=True
        )
        df_health_out.to_csv(health_path, index=False)
        logger.info(f"Updated {health_path} ({len(df_health_out)} rows)")

    if new_zones_rows:
        df_zones_out = pd.concat(
            [df_zones, pd.DataFrame(new_zones_rows)], ignore_index=True
        )
        df_zones_out.to_csv(zones_path, index=False)
        logger.info(f"Updated {zones_path} ({len(df_zones_out)} rows)")

    crossing_times.update(added_crossings)
    with open(crossings_path, "w") as f:
        json.dump(crossing_times, f, indent=2)
    logger.info(
        f"Updated {crossings_path} (+{len(added_crossings)} entries, "
        f"{len(crossing_times)} total)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fill non-watch participants by borrowing squad references. "
            "Run after process_watch_data.py and before process_step_data.py / process_temp_data.py."
        )
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Watch processor output directory (contains march_timeseries_data.csv etc.)",
    )
    parser.add_argument(
        "--station-dir",
        required=True,
        help="Admin station root containing SM0XX/<date>/hr.parquet files",
    )
    parser.add_argument(
        "--participants-csv",
        required=True,
        help="CSV with participant_id, group, squad, number columns",
    )
    parser.add_argument("--march-id", type=int, required=True, help="March event ID")

    args = parser.parse_args()

    try:
        fill_non_watch(
            output_dir=Path(args.output_dir),
            station_dir=Path(args.station_dir),
            participants_csv=Path(args.participants_csv),
            march_id=args.march_id,
        )
    except Exception as exc:
        logger.error(f"Fatal error: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()