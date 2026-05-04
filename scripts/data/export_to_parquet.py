#!/usr/bin/env python3
"""Export GPX, TCX, and FIT files to per-participant Parquet files.

Scans a directory for activity files, groups them by participant ID,
parses all time-series fields, merges multiple files/formats per
participant on timestamp, and writes one Parquet file per participant.

Usage:
    python scripts/data/export_to_parquet.py --data-dir /path/to/files --output /path/to/output
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd  # noqa: E402

from src.processing.parsers import (  # noqa: E402
    find_participant_files,
    parse_fit,
    parse_gpx,
    parse_tcx,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PARSER_BY_EXT = {
    "gpx": parse_gpx,
    "tcx": parse_tcx,
    "fit": parse_fit,
}


def parse_activity(files: dict) -> pd.DataFrame:
    """Parse all format files for a single activity and merge on timestamp."""
    frames: list[pd.DataFrame] = []

    for ext, parser in PARSER_BY_EXT.items():
        path = files.get(ext)
        if path is None:
            continue
        df = parser(path)
        if df.empty:
            continue
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    if len(frames) == 1:
        return frames[0]

    # Merge all frames on timestamp using merge_asof (nearest within 2s)
    merged = frames[0].sort_values("timestamp").reset_index(drop=True)
    for other in frames[1:]:
        other = other.sort_values("timestamp").reset_index(drop=True)
        overlap_cols = set(merged.columns) & set(other.columns) - {"timestamp"}
        new_cols = [c for c in other.columns if c not in merged.columns]

        # Merge only new (non-overlapping) columns directly
        if new_cols:
            merged = pd.merge_asof(
                merged,
                other[["timestamp"] + new_cols].sort_values("timestamp"),
                on="timestamp",
                direction="nearest",
                tolerance=pd.Timedelta("2s"),
            )

        # Fill gaps in overlapping columns from the secondary source
        for col in overlap_cols:
            if not merged[col].isna().any():
                continue
            fill = pd.merge_asof(
                merged[["timestamp"]].sort_values("timestamp"),
                other[["timestamp", col]].sort_values("timestamp"),
                on="timestamp",
                direction="nearest",
                tolerance=pd.Timedelta("2s"),
            )[col]
            merged[col] = merged[col].fillna(fill)

    # Drop any duplicate columns that slipped through
    merged = merged.loc[:, ~merged.columns.duplicated()]
    return merged


def process_participant(pid: str, activities: list[dict]) -> pd.DataFrame:
    """Parse and concatenate all activities for one participant."""
    frames: list[pd.DataFrame] = []
    for activity_files in activities:
        file_id = activity_files.get("file_id", "?")
        df = parse_activity(activity_files)
        if df.empty:
            logger.warning(f"{pid}: no data from activity {file_id}")
            continue
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    combined.drop_duplicates(subset=["timestamp"], keep="first", inplace=True)
    return combined


def main():
    parser = argparse.ArgumentParser(
        description="Export GPX/TCX/FIT files to per-participant Parquet files",
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing activity files (GPX/TCX/FIT)",
    )
    parser.add_argument(
        "--output",
        default="./data/output/parquet",
        help="Output directory for Parquet files (default: ./data/output/parquet)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    participants = find_participant_files(data_dir)
    if not participants:
        logger.error(f"No activity files found in {data_dir}")
        sys.exit(1)

    success = 0
    for pid, activities in participants.items():
        df = process_participant(pid, activities)
        if df.empty:
            logger.warning(f"{pid}: skipped — no data")
            continue

        out_path = output_dir / f"{pid}.parquet"
        df.to_parquet(out_path, index=False)
        logger.info(f"{pid}: wrote {len(df)} rows x {len(df.columns)} cols → {out_path}")
        success += 1

    logger.info(f"Done — {success}/{len(participants)} participants exported to {output_dir}")


if __name__ == "__main__":
    main()
