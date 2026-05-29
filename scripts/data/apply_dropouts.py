#!/usr/bin/env python3
"""
Apply dropout filtering to march data files.

Reads a dropouts CSV specifying when participants retired, and removes all data
recorded after their dropout time from the GPS, temperature, and timeseries files.

The dropouts CSV must have columns: Participant, Date, Time, Reason
Date format: DD.MM.YYYY, Time format: HH:MM:SS

Usage:
    python scripts/data/apply_dropouts.py \
        --dropouts dropouts.csv \
        --data-dir .output/

    # Dry run to see what would be removed:
    python scripts/data/apply_dropouts.py \
        --dropouts dropouts.csv \
        --data-dir .output/ \
        --dry-run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

TIMESERIES_FILE = "march_timeseries_data.csv"
TEMP_FILE = "march_temp_data.csv"
GPS_FILE = "march_gps_positions.csv"
DROPOUTS_JSON = "march_dropouts.json"


def load_dropouts(dropouts_path: Path) -> pd.DataFrame:
    df = pd.read_csv(dropouts_path)
    df["dropout_datetime"] = pd.to_datetime(
        df["Date"] + " " + df["Time"], format="%d.%m.%Y %H:%M:%S"
    )
    logger.info("Loaded %d dropouts from %s", len(df), dropouts_path)
    return df


def build_cutoff_map(dropouts: pd.DataFrame) -> dict[str, pd.Timestamp]:
    return {
        row["Participant"]: row["dropout_datetime"]
        for _, row in dropouts.iterrows()
    }


def compute_timestamp_minutes_cutoffs(
    cutoff_map: dict[str, pd.Timestamp],
    timeseries: pd.DataFrame,
) -> dict[str, float]:
    """Derive timestamp_minutes cutoffs for GPS data using timeseries reference points."""
    minutes_cutoffs = {}
    for participant, dropout_dt in cutoff_map.items():
        participant_ts = timeseries[timeseries["user_id"] == participant]
        if participant_ts.empty:
            logger.warning(
                "Participant %s not found in timeseries, skipping GPS cutoff",
                participant,
            )
            continue
        first = participant_ts.iloc[0]
        ref_time = pd.to_datetime(first["timestamp"])
        ref_minutes = first["timestamp_minutes"]
        delta_minutes = (dropout_dt - ref_time).total_seconds() / 60.0
        minutes_cutoffs[participant] = ref_minutes + delta_minutes
    return minutes_cutoffs


def filter_by_timestamp(
    df: pd.DataFrame,
    cutoff_map: dict[str, pd.Timestamp],
    filename: str,
) -> pd.DataFrame:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    mask = pd.Series(False, index=df.index)
    for participant, cutoff in cutoff_map.items():
        participant_mask = (df["user_id"] == participant) & (df["timestamp"] > cutoff)
        removed = participant_mask.sum()
        if removed > 0:
            logger.info(
                "  %s: removing %d rows after %s from %s",
                participant,
                removed,
                cutoff,
                filename,
            )
        mask |= participant_mask
    result = df[~mask]
    logger.info(
        "%s: %d -> %d rows (%d removed)",
        filename,
        len(df),
        len(result),
        mask.sum(),
    )
    return result


def filter_gps_by_minutes(
    df: pd.DataFrame,
    minutes_cutoffs: dict[str, float],
) -> pd.DataFrame:
    mask = pd.Series(False, index=df.index)
    for participant, cutoff_min in minutes_cutoffs.items():
        participant_mask = (df["user_id"] == participant) & (
            df["timestamp_minutes"] > cutoff_min
        )
        removed = participant_mask.sum()
        if removed > 0:
            logger.info(
                "  %s: removing %d GPS rows after minute %.1f",
                participant,
                removed,
                cutoff_min,
            )
        mask |= participant_mask
    result = df[~mask]
    logger.info(
        "%s: %d -> %d rows (%d removed)",
        GPS_FILE,
        len(df),
        len(result),
        mask.sum(),
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Apply dropout filtering to march data files",
    )
    parser.add_argument(
        "--dropouts",
        type=Path,
        required=True,
        help="Path to dropouts CSV file",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Directory containing the merged march data files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without modifying files",
    )
    args = parser.parse_args()

    if not args.dropouts.exists():
        logger.error("Dropouts file not found: %s", args.dropouts)
        sys.exit(1)

    dropouts = load_dropouts(args.dropouts)
    cutoff_map = build_cutoff_map(dropouts)

    timeseries_path = args.data_dir / TIMESERIES_FILE
    temp_path = args.data_dir / TEMP_FILE
    gps_path = args.data_dir / GPS_FILE

    for path in [timeseries_path, temp_path, gps_path]:
        if not path.exists():
            logger.error("Data file not found: %s", path)
            sys.exit(1)

    timeseries = pd.read_csv(timeseries_path)
    temp_data = pd.read_csv(temp_path)
    gps_data = pd.read_csv(gps_path)

    logger.info("Applying dropout cutoffs for %d participants...", len(cutoff_map))

    timeseries_filtered = filter_by_timestamp(timeseries, cutoff_map, TIMESERIES_FILE)
    temp_filtered = filter_by_timestamp(temp_data, cutoff_map, TEMP_FILE)

    minutes_cutoffs = compute_timestamp_minutes_cutoffs(cutoff_map, timeseries)
    gps_filtered = filter_gps_by_minutes(gps_data, minutes_cutoffs)

    dropout_info = [
        {
            "participant": row["Participant"],
            "dropout_time": row["dropout_datetime"].isoformat(),
            "reason": row["Reason"],
        }
        for _, row in dropouts.iterrows()
    ]

    if args.dry_run:
        logger.info("Dry run complete. No files modified.")
        return

    timeseries_filtered.to_csv(timeseries_path, index=False)
    temp_filtered.to_csv(temp_path, index=False)
    gps_filtered.to_csv(gps_path, index=False)

    dropouts_json_path = args.data_dir / DROPOUTS_JSON
    with open(dropouts_json_path, "w") as f:
        json.dump(dropout_info, f, indent=2)
    logger.info("Wrote dropout metadata to %s", dropouts_json_path)

    logger.info("Dropout filtering applied successfully.")


if __name__ == "__main__":
    main()
