#!/usr/bin/env python3
"""
Process watch data (GPX/TCX/FIT files) for march dashboard

This script processes watch export files (Garmin, Suunto, etc.) containing:
- GPX files: GPS tracks with position, elevation, and extensions (HR, cadence, temp)
- TCX files: Training Center XML with trackpoint-level time-series data
- FIT files: Garmin binary format with record-level data

The data is processed and formatted for ingestion into the march dashboard database.

Usage:
    python process_watch_data.py --data-dir /path/to/watch/data --march-id 1 --output march_data.csv
    python process_watch_data.py --data-dir /path/to/watch/data --march-id 1 --to-database
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.processing.parsers import (
    find_participant_files as _find_participant_files,
)
from src.processing.parsers import (
    parse_gpx,
    parse_tcx,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Europe/Zurich")


class WatchDataProcessor:
    """Processor for watch export data files"""

    def __init__(
        self,
        data_dir: Path,
        march_id: int,
        march_start_time: Optional[datetime] = None,
        march_end_time: Optional[datetime] = None,
        start_coords: Optional[tuple[float, float]] = None,
        end_coords: Optional[tuple[float, float]] = None,
        gps_tolerance_m: float = 50.0,
        gps_aggregation_interval_s: int = 5,
        min_gps_crossing_delay_s: int = 1800,
    ):
        self.data_dir = Path(data_dir)
        self.march_id = march_id
        self.march_start_time = march_start_time
        self.march_end_time = march_end_time
        self.start_coords = start_coords  # (lat, lon)
        self.end_coords = end_coords  # (lat, lon)
        self.gps_tolerance_m = gps_tolerance_m
        self.gps_crossing_times = {}  # Will store {participant_id: {'start': datetime, 'end': datetime}}
        self.gps_aggregation_interval_s = gps_aggregation_interval_s
        self.min_gps_crossing_delay_s = min_gps_crossing_delay_s

        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")

    def find_participant_files(self) -> dict[str, list[dict[str, Path]]]:
        """
        Find all participant data files in the data directory.

        Handles multiple activities per participant (e.g., SM001_1.gpx, SM001_2.tcx)

        Returns:
            Dict mapping participant IDs to list of activity file sets
            Example: {'SM001': [{'gpx': Path(...), 'tcx': Path(...)}, {...}]}
        """
        return _find_participant_files(self.data_dir)

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in meters between two GPS coordinates using Haversine formula."""
        R = 6371000  # Earth radius in meters

        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)

        a = (
            np.sin(dlat / 2) ** 2
            + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
        )
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        return R * c

    def find_gps_crossing(
        self, gps_df: pd.DataFrame, target_coords: tuple[float, float], tolerance_m: float
    ) -> Optional[datetime]:
        """Find the first time GPS track crosses within tolerance of target coordinates."""
        if gps_df.empty or target_coords is None:
            return None

        target_lat, target_lon = target_coords

        distances = []
        for _, row in gps_df.iterrows():
            dist = self._haversine_distance(row['latitude'], row['longitude'], target_lat, target_lon)
            distances.append(dist)

        gps_df = gps_df.copy()
        gps_df['distance_to_target'] = distances

        within_tolerance = gps_df[gps_df['distance_to_target'] <= tolerance_m]

        if not within_tolerance.empty:
            crossing_time = within_tolerance.iloc[0]['timestamp']
            crossing_dist = within_tolerance.iloc[0]['distance_to_target']
            logger.info(
                f"Found GPS crossing at {crossing_time} (distance: {crossing_dist:.1f}m from target)"
            )
            return crossing_time
        else:
            min_dist = gps_df['distance_to_target'].min()
            logger.warning(
                f"No GPS crossing found within {tolerance_m}m tolerance. "
                f"Closest approach: {min_dist:.1f}m"
            )
            return None

    def find_gps_crossing_times(
        self, participant_id: str, gps_df: pd.DataFrame
    ) -> Optional[dict[str, datetime]]:
        """Find start and end crossing times for a participant's GPS track."""
        if gps_df.empty:
            logger.warning(f"No GPS data for {participant_id}")
            return None

        if not self.start_coords and not self.end_coords:
            logger.info("No GPS trimming coordinates specified")
            return None

        crossing_times = {}

        if self.start_coords:
            start_time = self.find_gps_crossing(gps_df, self.start_coords, self.gps_tolerance_m)
            if start_time:
                crossing_times['start'] = start_time
                logger.info(f"{participant_id}: Start crossing at {start_time}")

        if self.end_coords:
            search_df = gps_df
            if 'start' in crossing_times:
                earliest_end = crossing_times['start'] + timedelta(seconds=self.min_gps_crossing_delay_s)
                search_df = gps_df[gps_df['timestamp'] >= earliest_end]
                if search_df.empty:
                    logger.warning(
                        f"{participant_id}: No GPS data found after minimum crossing delay "
                        f"({self.min_gps_crossing_delay_s}s after start). "
                        f"Consider reducing --min-gps-crossing-delay."
                    )

            end_time = self.find_gps_crossing(search_df, self.end_coords, self.gps_tolerance_m)
            if end_time:
                crossing_times['end'] = end_time
                logger.info(f"{participant_id}: End crossing at {end_time}")

        if not crossing_times:
            logger.warning(f"{participant_id}: No GPS crossings found")
            return None

        return crossing_times

    def trim_data_by_gps_times(
        self, df: pd.DataFrame, crossing_times: Optional[dict[str, datetime]], data_type: str = "data"
    ) -> pd.DataFrame:
        """Trim dataframe to GPS crossing time window."""
        if df.empty or not crossing_times:
            return df

        original_len = len(df)

        if 'start' in crossing_times:
            df = df[df['timestamp'] >= crossing_times['start']]

        if 'end' in crossing_times:
            df = df[df['timestamp'] <= crossing_times['end']]

        trimmed_len = len(df)
        if trimmed_len < original_len:
            logger.info(
                f"Trimmed {data_type}: {original_len} -> {trimmed_len} rows "
                f"({original_len - trimmed_len} rows removed)"
            )

        return df

    def parse_gpx_file(self, gpx_file: Path) -> pd.DataFrame:
        """Parse GPX file with all extensions (HR, cadence, temperature, etc.)."""
        return parse_gpx(gpx_file)

    def parse_tcx_file(self, tcx_file: Path) -> pd.DataFrame:
        """Parse TCX file extracting per-trackpoint time-series data."""
        return parse_tcx(tcx_file)

    def calculate_speed_from_gps(self, gps_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate speed from GPS track data."""
        if gps_df.empty or "latitude" not in gps_df.columns:
            return gps_df

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Earth radius in km
            dlat = np.radians(lat2 - lat1)
            dlon = np.radians(lon2 - lon1)
            a = (
                np.sin(dlat / 2) ** 2
                + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
            )
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
            return R * c

        gps_df = gps_df.sort_values("timestamp").reset_index(drop=True)

        distances = []
        speeds = []

        for i in range(len(gps_df)):
            if i == 0:
                distances.append(0)
                speeds.append(0)
            else:
                dist = haversine(
                    gps_df.loc[i - 1, "latitude"],
                    gps_df.loc[i - 1, "longitude"],
                    gps_df.loc[i, "latitude"],
                    gps_df.loc[i, "longitude"],
                )
                time_diff = (
                    gps_df.loc[i, "timestamp"] - gps_df.loc[i - 1, "timestamp"]
                ).total_seconds() / 3600
                distances.append(dist)
                speeds.append(dist / time_diff if time_diff > 0 else 0)

        gps_df["distance_km"] = distances
        gps_df["cumulative_distance_km"] = np.cumsum(distances)
        gps_df["speed_kmh"] = speeds

        # Smooth speed data (remove outliers)
        gps_df["speed_kmh"] = gps_df["speed_kmh"].clip(0, 15)  # Max 15 km/h for marching

        return gps_df

    def _merge_timeseries(self, *frames: pd.DataFrame) -> pd.DataFrame:
        """Merge multiple time-series DataFrames on timestamp (nearest within 2s)."""
        non_empty = [df for df in frames if not df.empty]
        if not non_empty:
            return pd.DataFrame()
        if len(non_empty) == 1:
            return non_empty[0].copy()

        merged = non_empty[0].sort_values("timestamp").reset_index(drop=True)
        for other in non_empty[1:]:
            other = other.sort_values("timestamp").reset_index(drop=True)
            overlap_cols = set(merged.columns) & set(other.columns) - {"timestamp"}
            new_cols = [c for c in other.columns if c not in merged.columns]

            if new_cols:
                merged = pd.merge_asof(
                    merged,
                    other[["timestamp"] + new_cols].sort_values("timestamp"),
                    on="timestamp",
                    direction="nearest",
                    tolerance=pd.Timedelta("2s"),
                )

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

        return merged

    def calculate_aggregate_metrics(
        self, timeseries_df: pd.DataFrame, march_duration_minutes: int
    ) -> dict:
        """Calculate aggregate metrics for the march."""
        if timeseries_df.empty:
            return {}

        metrics = {
            "avg_hr": int(timeseries_df["heart_rate"].mean())
            if "heart_rate" in timeseries_df.columns
            else None,
            "max_hr": int(timeseries_df["heart_rate"].max())
            if "heart_rate" in timeseries_df.columns
            else None,
            "total_steps": int(timeseries_df["steps"].max())
            if "steps" in timeseries_df.columns
            else None,
            "march_duration_minutes": march_duration_minutes,
            "data_completeness": round(
                len(timeseries_df) / (march_duration_minutes * 60), 2
            ),  # Assuming 1 sample per second
        }

        if "speed_kmh" in timeseries_df.columns:
            metrics["avg_pace_kmh"] = round(timeseries_df["speed_kmh"].mean(), 2)
            metrics["estimated_distance_km"] = (
                round(timeseries_df["cumulative_distance_km"].max(), 2)
                if "cumulative_distance_km" in timeseries_df.columns
                else None
            )

        return metrics

    def calculate_hr_zones(self, timeseries_df: pd.DataFrame) -> dict:
        """Calculate heart rate zone distribution."""
        if timeseries_df.empty or "heart_rate" not in timeseries_df.columns:
            return {}

        hr_data = timeseries_df["heart_rate"].dropna()
        total_samples = len(hr_data)

        if total_samples == 0:
            return {}

        zones = {
            "very_light_percent": round((hr_data < 100).sum() / total_samples * 100, 2),
            "light_percent": round(
                ((hr_data >= 100) & (hr_data < 120)).sum() / total_samples * 100, 2
            ),
            "moderate_percent": round(
                ((hr_data >= 120) & (hr_data < 140)).sum() / total_samples * 100, 2
            ),
            "intense_percent": round(
                ((hr_data >= 140) & (hr_data < 160)).sum() / total_samples * 100, 2
            ),
            "beast_mode_percent": round((hr_data >= 160).sum() / total_samples * 100, 2),
        }

        return zones

    def _prepare_timeseries(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """Enrich merged timeseries with speed and steps derived from available data."""
        if merged_df.empty:
            return merged_df

        merged_df = merged_df.sort_values("timestamp").reset_index(drop=True)

        # Calculate speed from GPS if not already present
        if "speed_kmh" not in merged_df.columns and "latitude" in merged_df.columns:
            merged_df = self.calculate_speed_from_gps(merged_df)
        elif "speed" in merged_df.columns and "speed_kmh" not in merged_df.columns:
            # TCX speed is in m/s, convert to km/h
            merged_df["speed_kmh"] = merged_df["speed"] * 3.6
        elif "speed_kmh" not in merged_df.columns:
            # If we have lat/lon, calculate speed
            if "latitude" in merged_df.columns:
                merged_df = self.calculate_speed_from_gps(merged_df)

        # Calculate cumulative distance from GPS if not already present
        if "cumulative_distance_km" not in merged_df.columns and "latitude" in merged_df.columns:
            if "distance_km" not in merged_df.columns:
                merged_df = self.calculate_speed_from_gps(merged_df)
        elif "cumulative_distance_km" not in merged_df.columns and "distance" in merged_df.columns:
            # TCX distance is cumulative in meters
            merged_df["cumulative_distance_km"] = merged_df["distance"] / 1000.0

        # Calculate cumulative steps from cadence if no steps column
        if "steps" not in merged_df.columns and "cadence" in merged_df.columns:
            cadence_data = merged_df["cadence"].fillna(0)
            # Cadence is steps per minute; assuming ~1s sampling → steps per second = cadence / 60
            merged_df["steps"] = (cadence_data / 60).cumsum()

        return merged_df

    def process_participant(self, participant_id: str, files: dict[str, Path]) -> dict:
        """Process all data files for a single participant."""
        logger.info(f"Processing participant: {participant_id}")

        # Parse all available file types
        gpx_df = pd.DataFrame()
        tcx_df = pd.DataFrame()

        if "gpx" in files:
            gpx_df = self.parse_gpx_file(files["gpx"])
        if "tcx" in files:
            tcx_df = self.parse_tcx_file(files["tcx"])

        # Merge all sources into one timeseries
        merged_df = self._merge_timeseries(gpx_df, tcx_df)

        if merged_df.empty:
            logger.warning(f"No valid data for participant {participant_id}")
            return {}

        # Extract GPS subset for crossing detection (need lat/lon)
        gps_df = pd.DataFrame()
        if "latitude" in merged_df.columns:
            gps_cols = ["timestamp", "latitude", "longitude"]
            if "altitude" in merged_df.columns:
                gps_cols.append("altitude")
            gps_df = merged_df[gps_cols].dropna(subset=["latitude", "longitude"]).copy()

        # Find GPS crossing times
        crossing_times = None
        if not gps_df.empty and (self.start_coords or self.end_coords):
            logger.info(f"{participant_id}: Finding GPS crossing times...")
            crossing_times = self.find_gps_crossing_times(participant_id, gps_df)
            if crossing_times:
                self.gps_crossing_times[participant_id] = crossing_times
                merged_df = self.trim_data_by_gps_times(merged_df, crossing_times, "timeseries data")
                gps_df = self.trim_data_by_gps_times(gps_df, crossing_times, "GPS data")

        # Enrich with speed/steps
        merged_df = self._prepare_timeseries(merged_df)

        result = self._process_from_timeseries(participant_id, merged_df, gps_df)
        if crossing_times:
            result["crossing_times"] = crossing_times
        return result

    def _aggregate_gps_positions(self, gps_positions: pd.DataFrame) -> pd.DataFrame:
        """Aggregate GPS positions to specified intervals."""
        gps_positions = (
            gps_positions.set_index("timestamp")
            .resample(f"{self.gps_aggregation_interval_s}s")
            .agg(
                {
                    "timestamp_minutes": "min",
                    "latitude": "mean",
                    "longitude": "mean",
                    "altitude": "mean",
                }
            )
            .reset_index()
        )

        gps_positions = gps_positions.ffill().bfill()

        return gps_positions

    def _process_from_timeseries(
        self, participant_id: str, merged_df: pd.DataFrame, gps_df: pd.DataFrame
    ) -> dict:
        """Process participant data from a merged timeseries DataFrame."""
        # Calculate time from march start
        if self.march_start_time:
            merged_df["timestamp_minutes"] = (
                merged_df["timestamp"] - self.march_start_time
            ).dt.total_seconds() / 60
        else:
            merged_df["timestamp_minutes"] = (
                merged_df["timestamp"] - merged_df["timestamp"].min()
            ).dt.total_seconds() / 60

        march_duration_minutes = int(merged_df["timestamp_minutes"].max())

        # Remove data with negative time (before march start)
        merged_df = merged_df[merged_df["timestamp_minutes"] >= 0].reset_index(drop=True)

        # Remove the initial cumulative distance offset if present
        if "cumulative_distance_km" in merged_df.columns:
            initial_distance = merged_df["cumulative_distance_km"].min()
            merged_df["cumulative_distance_km"] = (
                merged_df["cumulative_distance_km"] - initial_distance
            )

        # Build resample aggregation dict from available columns
        agg_dict = {"timestamp_minutes": "mean"}
        if "heart_rate" in merged_df.columns:
            agg_dict["heart_rate"] = "mean"
        if "steps" in merged_df.columns:
            agg_dict["steps"] = "max"
        if "speed_kmh" in merged_df.columns:
            agg_dict["speed_kmh"] = "mean"
        if "cumulative_distance_km" in merged_df.columns:
            agg_dict["cumulative_distance_km"] = "max"

        # Resample to 1-minute intervals
        timeseries_df = (
            merged_df.set_index("timestamp")
            .resample("1min")
            .agg(agg_dict)
            .reset_index()
        )

        # Interpolate missing step values
        if "steps" in timeseries_df.columns and timeseries_df["steps"].notna().any():
            if timeseries_df["steps"].isna().any():
                timeseries_df["steps"] = timeseries_df["steps"].interpolate(method="linear")

        # Calculate aggregate metrics
        aggregate_metrics = self.calculate_aggregate_metrics(merged_df, march_duration_minutes)

        # Calculate HR zones
        hr_zones = self.calculate_hr_zones(merged_df)

        # Prepare GPS positions data
        gps_positions = None
        if not gps_df.empty:
            gps_positions = gps_df.copy()
            if self.march_start_time:
                gps_positions["timestamp_minutes"] = (
                    gps_positions["timestamp"] - self.march_start_time
                ).dt.total_seconds() / 60
            else:
                gps_positions["timestamp_minutes"] = (
                    gps_positions["timestamp"] - gps_positions["timestamp"].min()
                ).dt.total_seconds() / 60

            gps_positions = self._aggregate_gps_positions(gps_positions)

        return {
            "participant_id": participant_id,
            "march_id": self.march_id,
            "timeseries": timeseries_df,
            "aggregate_metrics": aggregate_metrics,
            "hr_zones": hr_zones,
            "gps_positions": gps_positions,
        }

    def process_all_participants(self) -> list[dict]:
        """Process data for all participants and their activities."""
        participant_files = self.find_participant_files()

        results = []
        for participant_id, activities in participant_files.items():
            if len(activities) > 1:
                logger.info(
                    f"Processing {participant_id} - Merging {len(activities)} activities into one"
                )
                try:
                    result = self.process_participant_multiple_activities(
                        participant_id, activities
                    )
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {participant_id} multiple activities: {e}")
            else:
                activity_files = activities[0]
                logger.info(f"Processing {participant_id} - Single activity")

                try:
                    result = self.process_participant(participant_id, activity_files)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {participant_id}: {e}")

        logger.info(f"Successfully processed {len(results)} participants")
        return results

    def process_participant_multiple_activities(
        self, participant_id: str, activities: list[dict]
    ) -> dict:
        """Process multiple activities for a participant and merge them into one timeline."""
        all_gpx_dfs = []
        all_tcx_dfs = []

        for activity_files in activities:
            activity_num = activity_files.get("activity_num", 1)
            logger.info(f"  Parsing {participant_id} activity {activity_num}")

            if "gpx" in activity_files:
                gpx_df = self.parse_gpx_file(activity_files["gpx"])
                if not gpx_df.empty:
                    all_gpx_dfs.append(gpx_df)

            if "tcx" in activity_files:
                tcx_df = self.parse_tcx_file(activity_files["tcx"])
                if not tcx_df.empty:
                    all_tcx_dfs.append(tcx_df)

        # Concatenate all frames per format, then merge formats
        merged_gpx = (
            pd.concat(all_gpx_dfs, ignore_index=True).sort_values("timestamp")
            if all_gpx_dfs
            else pd.DataFrame()
        )
        merged_tcx = (
            pd.concat(all_tcx_dfs, ignore_index=True).sort_values("timestamp")
            if all_tcx_dfs
            else pd.DataFrame()
        )

        merged_df = self._merge_timeseries(merged_gpx, merged_tcx)

        if merged_df.empty:
            logger.warning(f"No valid merged data for {participant_id}")
            return {}

        # Extract GPS subset
        gps_df = pd.DataFrame()
        if "latitude" in merged_df.columns:
            gps_cols = ["timestamp", "latitude", "longitude"]
            if "altitude" in merged_df.columns:
                gps_cols.append("altitude")
            gps_df = merged_df[gps_cols].dropna(subset=["latitude", "longitude"]).copy()

        # Find GPS crossing times on merged data
        crossing_times = None
        if not gps_df.empty and (self.start_coords or self.end_coords):
            logger.info(f"{participant_id}: Finding GPS crossing times on merged GPS data...")
            crossing_times = self.find_gps_crossing_times(participant_id, gps_df)
            if crossing_times:
                self.gps_crossing_times[participant_id] = crossing_times
                merged_df = self.trim_data_by_gps_times(
                    merged_df, crossing_times, "merged timeseries data"
                )
                gps_df = self.trim_data_by_gps_times(gps_df, crossing_times, "merged GPS data")

        # Enrich with speed/steps
        merged_df = self._prepare_timeseries(merged_df)

        result = self._process_from_timeseries(participant_id, merged_df, gps_df)
        if crossing_times:
            result["crossing_times"] = crossing_times
        return result

    def save_gps_crossing_times(self, output_dir: Path):
        """Save GPS crossing times to JSON file for use by other processing scripts."""
        if not self.gps_crossing_times:
            logger.info("No GPS crossing times to save")
            return

        output_dir = Path(output_dir)
        output_file = output_dir / "gps_crossing_times.json"

        crossing_times_serializable = {}
        for participant_id, times in self.gps_crossing_times.items():
            crossing_times_serializable[participant_id] = {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in times.items()
            }

        with open(output_file, 'w') as f:
            json.dump(crossing_times_serializable, f, indent=2)

        logger.info(f"Saved GPS crossing times for {len(self.gps_crossing_times)} participants to {output_file}")

    def save_to_csv(self, results: list[dict], output_dir: Path):
        """Save processed data to CSV files for database import."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save aggregate metrics
        metrics_data = []
        for result in results:
            if result.get("aggregate_metrics"):
                row = {
                    "march_id": result["march_id"],
                    "user_id": result["participant_id"],
                    **result["aggregate_metrics"],
                }
                metrics_data.append(row)

        if metrics_data:
            metrics_df = pd.DataFrame(metrics_data)
            metrics_file = output_dir / "march_health_metrics.csv"
            metrics_df.to_csv(metrics_file, index=False)
            logger.info(f"Saved aggregate metrics to {metrics_file}")

        # Save HR zones
        zones_data = []
        for result in results:
            if result.get("hr_zones"):
                row = {
                    "march_id": result["march_id"],
                    "user_id": result["participant_id"],
                    **result["hr_zones"],
                }
                zones_data.append(row)

        if zones_data:
            zones_df = pd.DataFrame(zones_data)
            zones_file = output_dir / "march_hr_zones.csv"
            zones_df.to_csv(zones_file, index=False)
            logger.info(f"Saved HR zones to {zones_file}")

        # Save timeseries data
        all_timeseries = []
        for result in results:
            if "timeseries" in result and not result["timeseries"].empty:
                ts_df = result["timeseries"].copy()
                ts_df["march_id"] = result["march_id"]
                ts_df["user_id"] = result["participant_id"]
                all_timeseries.append(ts_df)

        if all_timeseries:
            timeseries_df = pd.concat(all_timeseries, ignore_index=True)
            columns = [
                "march_id",
                "user_id",
                "timestamp",
                "timestamp_minutes",
                "heart_rate",
                "steps",
                "speed_kmh",
                "cumulative_distance_km",
            ]
            timeseries_df = timeseries_df[[col for col in columns if col in timeseries_df.columns]]

            if "timestamp_minutes" in timeseries_df.columns:
                negative_count = (timeseries_df["timestamp_minutes"] < 0).sum()
                if negative_count > 0:
                    logger.info(
                        f"Removing {negative_count} rows with negative timestamps (before march start)"
                    )
                    timeseries_df = timeseries_df[timeseries_df["timestamp_minutes"] >= 0]

            timeseries_file = output_dir / "march_timeseries_data.csv"
            timeseries_df.to_csv(timeseries_file, index=False)
            logger.info(f"Saved timeseries data to {timeseries_file}")

        # Save GPS positions
        all_gps = []
        for result in results:
            if result.get("gps_positions") is not None and not result["gps_positions"].empty:
                gps_df = result["gps_positions"].copy()
                gps_df["march_id"] = result["march_id"]
                gps_df["user_id"] = result["participant_id"]
                all_gps.append(gps_df)

        if all_gps:
            gps_positions_df = pd.concat(all_gps, ignore_index=True)
            columns = [
                "march_id",
                "user_id",
                "timestamp_minutes",
                "latitude",
                "longitude",
                "altitude",
                "speed_kmh",
            ]
            gps_positions_df = gps_positions_df[
                [col for col in columns if col in gps_positions_df.columns]
            ]

            # Rename altitude to elevation
            gps_positions_df.rename(columns={"altitude": "elevation"}, inplace=True)

            if "timestamp_minutes" in gps_positions_df.columns:
                negative_count = (gps_positions_df["timestamp_minutes"] < 0).sum()
                if negative_count > 0:
                    logger.info(
                        f"Removing {negative_count} GPS rows with negative timestamps (before march start)"
                    )
                    gps_positions_df = gps_positions_df[gps_positions_df["timestamp_minutes"] >= 0]

            if "latitude" in gps_positions_df.columns and "longitude" in gps_positions_df.columns:
                gps_positions_df["bearing"] = None  # Placeholder for now

            gps_file = output_dir / "march_gps_positions.csv"
            gps_positions_df.to_csv(gps_file, index=False)
            logger.info(f"Saved GPS positions to {gps_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Process watch data (GPX/TCX/FIT) for march dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--data-dir", required=True, help="Directory containing watch data files (GPX/TCX/FIT)"
    )

    parser.add_argument("--march-id", type=int, required=True, help="March event ID")

    parser.add_argument(
        "--march-start-time", help="March start time (ISO format: YYYY-MM-DDTHH:MM:SS)"
    )

    parser.add_argument("--march-end-time", help="March end time (ISO format: YYYY-MM-DDTHH:MM:SS)")

    parser.add_argument(
        "--start-lat", type=float, help="Start point latitude for GPS trimming"
    )

    parser.add_argument(
        "--start-lon", type=float, help="Start point longitude for GPS trimming"
    )

    parser.add_argument(
        "--end-lat", type=float, help="End point latitude for GPS trimming"
    )

    parser.add_argument(
        "--end-lon", type=float, help="End point longitude for GPS trimming"
    )

    parser.add_argument(
        "--gps-aggregation-interval",
        type=int,
        default=60,
        help="GPS aggregation interval in seconds (default: 60)",
    )

    parser.add_argument(
        "--gps-tolerance",
        type=float,
        default=50.0,
        help="GPS tolerance in meters for detecting coordinate crossings (default: 50.0)"
    )

    parser.add_argument(
        "--min-gps-crossing-delay",
        type=int,
        default=1800,
        help="Minimum time in seconds between start and end GPS crossings (default: 1800 = 30 min)"
    )

    parser.add_argument(
        "--output", default="./data/output", help="Output directory for CSV files (default: ./data/output)"
    )

    args = parser.parse_args()

    march_start_time = None
    if args.march_start_time:
        try:
            march_start_time = datetime.fromisoformat(args.march_start_time)
        except ValueError:
            logger.error(f"Invalid march start time format: {args.march_start_time}")
            sys.exit(1)

    march_end_time = None
    if args.march_end_time:
        try:
            march_end_time = datetime.fromisoformat(args.march_end_time)
        except ValueError:
            logger.error(f"Invalid march end time format: {args.march_end_time}")
            sys.exit(1)

    start_coords = None
    if args.start_lat is not None and args.start_lon is not None:
        start_coords = (args.start_lat, args.start_lon)
        logger.info(f"GPS start trimming point: {args.start_lat}, {args.start_lon}")

    end_coords = None
    if args.end_lat is not None and args.end_lon is not None:
        end_coords = (args.end_lat, args.end_lon)
        logger.info(f"GPS end trimming point: {args.end_lat}, {args.end_lon}")

    if start_coords or end_coords:
        logger.info(f"GPS trimming tolerance: {args.gps_tolerance}m")
        logger.info(f"Minimum GPS crossing delay: {args.min_gps_crossing_delay}s")

    logger.info(f"GPS aggregation interval: {args.gps_aggregation_interval}s")

    try:
        processor = WatchDataProcessor(
            data_dir=args.data_dir,
            march_id=args.march_id,
            march_start_time=march_start_time,
            march_end_time=march_end_time,
            start_coords=start_coords,
            end_coords=end_coords,
            gps_tolerance_m=args.gps_tolerance,
            gps_aggregation_interval_s=args.gps_aggregation_interval,
            min_gps_crossing_delay_s=args.min_gps_crossing_delay,
        )

        results = processor.process_all_participants()

        if not results:
            logger.error("No data was successfully processed")
            sys.exit(1)

        processor.save_to_csv(results, args.output)
        processor.save_gps_crossing_times(args.output)

        logger.info(f"Processing complete! Output saved to {args.output}")
        logger.info(f"Processed {len(results)} participants")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
