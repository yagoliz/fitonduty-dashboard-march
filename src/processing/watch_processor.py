#!/usr/bin/env python3
"""
Process watch data (CSV/GPX/TCX files) for march dashboard

This script processes watch export files (Garmin, Suunto, etc.) containing:
- CSV files: Heart rate, steps, and other sensor data
- GPX files: GPS tracks with position and elevation
- TCX files: Training Center XML with heart rate zones and laps

The data is processed and formatted for ingestion into the march dashboard database.

Usage:
    python process_watch_data.py --data-dir /path/to/watch/data --march-id 1 --output march_data.csv
    python process_watch_data.py --data-dir /path/to/watch/data --march-id 1 --to-database
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Optional imports with fallbacks
try:
    import gpxpy
    import gpxpy.gpx

    HAS_GPX = True
except ImportError:
    HAS_GPX = False
    logging.warning("gpxpy not installed. GPX parsing will be disabled.")

try:
    import xml.etree.ElementTree as ET

    HAS_XML = True
except ImportError:
    HAS_XML = False
    logging.warning("xml.etree not available. TCX parsing will be disabled.")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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
    ):
        self.data_dir = Path(data_dir)
        self.march_id = march_id
        self.march_start_time = march_start_time
        self.march_end_time = march_end_time
        self.start_coords = start_coords  # (lat, lon)
        self.end_coords = end_coords  # (lat, lon)
        self.gps_tolerance_m = gps_tolerance_m
        self.gps_crossing_times = {}  # Will store {participant_id: {'start': datetime, 'end': datetime}}

        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")

    def find_participant_files(self) -> dict[str, list[dict[str, Path]]]:
        """
        Find all participant data files in the data directory

        Handles multiple activities per participant (e.g., SM001_1.CSV, SM001_2.CSV)

        Returns:
            Dict mapping participant IDs to list of activity file sets
            Example: {'SM001': [{'csv': Path(...), 'gpx': Path(...)}, {...}]}
        """
        import re

        participants = {}

        # Find all CSV files
        csv_files = list(self.data_dir.glob("*.CSV")) + list(self.data_dir.glob("*.csv"))

        for csv_file in csv_files:
            # Extract participant ID and activity number from filename
            # Patterns: SM001.CSV, SM001_1.CSV, SM001_2.CSV, etc.
            stem = csv_file.stem

            # Try to match pattern: PARTICIPANT_ACTIVITYNUM or just PARTICIPANT
            match = re.match(r"^([A-Za-z0-9]+)(?:_(\d+))?$", stem)

            if match:
                participant_id = match.group(1)
                activity_num = int(match.group(2)) if match.group(2) else 1
            else:
                # Fallback: use entire stem as participant ID
                participant_id = stem
                activity_num = 1

            if participant_id not in participants:
                participants[participant_id] = []

            # Create activity file set
            activity_files = {
                "csv": csv_file,
                "activity_num": activity_num,
                "file_id": stem,  # Original filename stem for identification
            }

            # Look for corresponding GPX and TCX files
            for ext in ["GPX", "gpx"]:
                gpx_file = csv_file.with_suffix(f".{ext}")
                if gpx_file.exists():
                    activity_files["gpx"] = gpx_file
                    break

            for ext in ["TCX", "tcx"]:
                tcx_file = csv_file.with_suffix(f".{ext}")
                if tcx_file.exists():
                    activity_files["tcx"] = tcx_file
                    break

            participants[participant_id].append(activity_files)

        # Sort activities by activity number for each participant
        for participant_id in participants:
            participants[participant_id].sort(key=lambda x: x["activity_num"])

        total_activities = sum(len(activities) for activities in participants.values())
        logger.info(
            f"Found {len(participants)} participants with {total_activities} total activities"
        )

        return participants

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance in meters between two GPS coordinates using Haversine formula

        Returns:
            Distance in meters
        """
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
        """
        Find the first time GPS track crosses within tolerance of target coordinates

        Args:
            gps_df: GPS track data with 'latitude', 'longitude', 'timestamp' columns
            target_coords: (latitude, longitude) tuple of target point
            tolerance_m: Distance tolerance in meters

        Returns:
            Timestamp when crossing occurred, or None if not found
        """
        if gps_df.empty or target_coords is None:
            return None

        target_lat, target_lon = target_coords

        # Calculate distance from each GPS point to target
        distances = []
        for _, row in gps_df.iterrows():
            dist = self._haversine_distance(row['latitude'], row['longitude'], target_lat, target_lon)
            distances.append(dist)

        gps_df = gps_df.copy()
        gps_df['distance_to_target'] = distances

        # Find first point within tolerance
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
        """
        Find start and end crossing times for a participant's GPS track

        Args:
            participant_id: Participant identifier
            gps_df: GPS track data

        Returns:
            Dictionary with 'start' and 'end' timestamps, or None if not found
        """
        if gps_df.empty:
            logger.warning(f"No GPS data for {participant_id}")
            return None

        if not self.start_coords and not self.end_coords:
            logger.info(f"No GPS trimming coordinates specified")
            return None

        crossing_times = {}

        # Find start crossing
        if self.start_coords:
            start_time = self.find_gps_crossing(gps_df, self.start_coords, self.gps_tolerance_m)
            if start_time:
                crossing_times['start'] = start_time
                logger.info(f"{participant_id}: Start crossing at {start_time}")

        # Find end crossing (search from start crossing onwards if found)
        if self.end_coords:
            search_df = gps_df
            if 'start' in crossing_times:
                # Only search GPS points after start crossing
                search_df = gps_df[gps_df['timestamp'] > crossing_times['start']]

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
        """
        Trim dataframe to GPS crossing time window

        Args:
            df: DataFrame with 'timestamp' column
            crossing_times: Dictionary with 'start' and/or 'end' timestamps
            data_type: Description of data being trimmed (for logging)

        Returns:
            Trimmed dataframe
        """
        if df.empty or not crossing_times:
            return df

        original_len = len(df)

        # Trim by start time
        if 'start' in crossing_times:
            df = df[df['timestamp'] >= crossing_times['start']]

        # Trim by end time
        if 'end' in crossing_times:
            df = df[df['timestamp'] <= crossing_times['end']]

        trimmed_len = len(df)
        if trimmed_len < original_len:
            logger.info(
                f"Trimmed {data_type}: {original_len} -> {trimmed_len} rows "
                f"({original_len - trimmed_len} rows removed)"
            )

        return df

    def parse_csv_file(self, csv_file: Path) -> tuple[pd.DataFrame, dict]:
        """
        Parse CSV file containing heart rate and sensor data

        Different watch manufacturers use different CSV formats. This function
        attempts to handle common formats:
        1. Time-series format: Rows with timestamp, heart rate, steps, etc.
        2. Summary format: Single row with activity summary (Polar/Suunto export)
        3. Combined format: Summary row + time-series data (with dual headers)

        Returns:
            Tuple of (timeseries_df, summary_dict)
        """
        try:
            # First, read just the first few rows to detect format
            first_rows = pd.read_csv(csv_file, nrows=3)

            # Check if this is a summary format CSV (Polar/Suunto style)
            summary_cols = [
                "Name",
                "Sport",
                "Date",
                "Start time",
                "Duration",
                "Average heart rate (bpm)",
                "Average cadence (rpm)",
            ]

            if all(col in first_rows.columns for col in summary_cols[:4]):
                # Detected summary format - check if it's combined or summary-only
                # Check if row 2 (index 1) looks like time-series headers
                if len(first_rows) >= 2:
                    second_row = first_rows.iloc[1]
                    # Common time-series column indicators
                    timeseries_indicators = ["Sample rate", "Time", "HR (bpm)", "Speed (km/h)"]

                    if any(str(val) in timeseries_indicators for val in second_row.values):
                        logger.info(
                            f"Detected combined format CSV (summary + timeseries): {csv_file.name}"
                        )
                        return self._parse_combined_csv(csv_file)

                logger.info(f"Detected summary-only format CSV: {csv_file.name}")
                return self._parse_summary_csv(first_rows, csv_file)

            # Otherwise, try to parse as time-series format
            df = pd.read_csv(csv_file)
            return self._parse_timeseries_csv(df, csv_file)

        except Exception as e:
            logger.error(f"Error parsing CSV file {csv_file}: {e}")
            return pd.DataFrame(), {}

    def _parse_combined_csv(self, csv_file: Path) -> tuple[pd.DataFrame, dict]:
        """
        Parse combined format CSV with both summary and time-series data

        Format:
        Row 1: Summary headers
        Row 2: Summary data
        Row 3: Time-series headers
        Row 4+: Time-series data
        """
        try:
            # Read summary data (first 2 rows)
            summary_df = pd.read_csv(csv_file, nrows=1)

            # Parse summary data
            _, summary_dict = self._parse_summary_csv(summary_df, csv_file)

            # Read time-series data (skip first 2 rows, use row 3 as header)
            timeseries_df = pd.read_csv(csv_file, skiprows=2)

            # Parse time-series data
            timeseries_clean = self._parse_timeseries_data(timeseries_df, csv_file, summary_dict)

            return timeseries_clean, summary_dict

        except Exception as e:
            logger.error(f"Error parsing combined CSV file {csv_file}: {e}")
            return pd.DataFrame(), {}

    def _parse_timeseries_data(
        self, df: pd.DataFrame, csv_file: Path, summary: dict
    ) -> pd.DataFrame:
        """
        Parse time-series data from combined format CSV

        Expected columns: Time, HR (bpm), Speed (km/h), Cadence, etc.
        """
        # Common column name mappings for this format
        column_mapping = {
            "Time": "timestamp",
            "HR (bpm)": "heart_rate",
            "Speed (km/h)": "speed_kmh",
            "Cadence": "cadence",
            "Altitude (m)": "altitude",
            "Distances (m)": "distance_m",
            "Power (W)": "power",
        }

        df_clean = pd.DataFrame()

        # Find and map columns
        for orig_col, new_col in column_mapping.items():
            if orig_col in df.columns:
                if new_col == "timestamp":
                    # Parse time and combine with summary start datetime
                    try:
                        # Time column contains delta time (elapsed time from start)
                        # Format: HH:MM:SS or MM:SS
                        start_datetime = summary.get("start_time")
                        if start_datetime:
                            # Parse delta time as timedelta
                            time_values = pd.to_timedelta(df[orig_col].astype(str), errors="coerce")
                            # Add delta time to start datetime
                            df_clean["timestamp"] = pd.to_datetime(start_datetime) + time_values
                        else:
                            # Fallback: just parse as timedelta
                            df_clean["timestamp"] = pd.to_timedelta(
                                df[orig_col].astype(str), errors="coerce"
                            )
                    except Exception as e:
                        logger.warning(f"Could not parse timestamp from {orig_col}: {e}")
                        continue
                else:
                    df_clean[new_col] = pd.to_numeric(df[orig_col], errors="coerce")

        # Calculate cumulative steps from cadence if available
        if "cadence" in df_clean.columns and "timestamp" in df_clean.columns:
            # Cadence is steps per minute, integrate over time to get total steps
            cadence_data = df_clean["cadence"].fillna(0)
            # Assuming 1-second sampling, steps per second = cadence / 60
            df_clean["steps"] = (cadence_data / 60).cumsum()

        # Remove rows with invalid data
        if "timestamp" in df_clean.columns:
            df_clean = df_clean.dropna(subset=["timestamp"])

        logger.info(f"Parsed {len(df_clean)} time-series records from combined CSV {csv_file.name}")
        return df_clean

    def _parse_summary_csv(self, df: pd.DataFrame, csv_file: Path) -> tuple[pd.DataFrame, dict]:
        """
        Parse summary format CSV (one row per activity)

        Expected columns:
        - Name, Sport, Date, Start time, Duration
        - Average heart rate (bpm), Max heart rate, etc.
        - Average cadence (rpm) - used to estimate steps
        - Total distance (km), Average speed (km/h), etc.
        """
        if len(df) == 0:
            logger.warning(f"Empty CSV file: {csv_file.name}")
            return pd.DataFrame(), {}

        # Take first row (should only be one activity per file)
        row = df.iloc[0]

        # Parse date and time
        try:
            date_str = row.get("Date", "")
            time_str = row.get("Start time", "")
            datetime_str = f"{date_str} {time_str}"
            start_time = pd.to_datetime(datetime_str, format="%d.%m.%Y %H:%M:%S", errors="coerce")

            if pd.isna(start_time):
                # Try alternative formats with dayfirst=True
                start_time = pd.to_datetime(datetime_str, dayfirst=True, errors="coerce")

            if pd.isna(start_time):
                logger.error(f"Could not parse date/time from {csv_file.name}: '{datetime_str}'")
                return pd.DataFrame(), {}

            # Make timezone-naive (remove timezone if present)
            if start_time.tz is not None:
                start_time = start_time.tz_localize(None)

        except Exception as e:
            logger.error(f"Error parsing date/time from {csv_file.name}: {e}")
            return pd.DataFrame(), {}

        # Parse duration (format: HH:MM:SS or HH:MM:SS.mmm)
        duration_str = row.get("Duration", "00:00:00")
        try:
            # Handle different duration formats
            duration_parts = duration_str.split(":")
            hours = int(duration_parts[0])
            minutes = int(duration_parts[1])
            seconds = float(duration_parts[2]) if len(duration_parts) > 2 else 0
            duration_minutes = hours * 60 + minutes + seconds / 60
        except Exception as e:
            logger.warning(f"Could not parse duration '{duration_str}': {e}")
            duration_minutes = 0

        # Extract metrics
        avg_hr = pd.to_numeric(row.get("Average heart rate (bpm)", np.nan), errors="coerce")
        max_hr = pd.to_numeric(row.get("Max heart rate", np.nan), errors="coerce")
        avg_cadence = pd.to_numeric(row.get("Average cadence (rpm)", np.nan), errors="coerce")
        avg_speed = pd.to_numeric(row.get("Average speed (km/h)", np.nan), errors="coerce")
        max_speed = pd.to_numeric(row.get("Max speed (km/h)", np.nan), errors="coerce")
        total_distance = pd.to_numeric(row.get("Total distance (km)", np.nan), errors="coerce")
        calories = pd.to_numeric(row.get("Calories", np.nan), errors="coerce")

        # Estimate steps from cadence
        # Average cadence (rpm) in running context = steps per minute
        # Total steps = average cadence × duration in minutes
        estimated_steps = None
        if not pd.isna(avg_cadence) and duration_minutes > 0:
            estimated_steps = int(avg_cadence * duration_minutes)
            logger.info(
                f"Estimated {estimated_steps} steps from cadence {avg_cadence} rpm over {duration_minutes:.1f} minutes"
            )

        # Create summary dictionary
        summary = {
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "avg_hr": int(avg_hr) if not pd.isna(avg_hr) else None,
            "max_hr": int(max_hr) if not pd.isna(max_hr) else None,
            "avg_cadence": avg_cadence if not pd.isna(avg_cadence) else None,
            "estimated_steps": estimated_steps,
            "avg_speed_kmh": avg_speed if not pd.isna(avg_speed) else None,
            "max_speed_kmh": max_speed if not pd.isna(max_speed) else None,
            "total_distance_km": total_distance if not pd.isna(total_distance) else None,
            "calories": int(calories) if not pd.isna(calories) else None,
            "sport": row.get("Sport", "Unknown"),
            "name": row.get("Name", "Unknown"),
        }

        logger.info(
            f"Parsed summary data from {csv_file.name}: {duration_minutes:.1f} min, "
            f"avg HR {summary['avg_hr']}, {estimated_steps} steps (estimated)"
        )

        # Return empty timeseries (will use GPX if available) and summary
        return pd.DataFrame(), summary

    def _parse_timeseries_csv(self, df: pd.DataFrame, csv_file: Path) -> tuple[pd.DataFrame, dict]:
        """
        Parse time-series format CSV (rows with timestamp and sensor data)
        """
        # Common column name variations
        time_cols = ["Time", "time", "Timestamp", "timestamp", "DateTime", "datetime"]
        hr_cols = ["Heart Rate", "HR", "hr", "HeartRate", "heart_rate", "BPM", "bpm"]
        steps_cols = ["Steps", "steps", "Step Count", "step_count"]

        # Find the actual column names
        time_col = next((col for col in time_cols if col in df.columns), None)
        hr_col = next((col for col in hr_cols if col in df.columns), None)
        steps_col = next((col for col in steps_cols if col in df.columns), None)

        if not time_col:
            logger.warning(
                f"No time column found in {csv_file}. Available columns: {df.columns.tolist()}"
            )
            return pd.DataFrame(), {}

        # Standardize column names
        df_clean = pd.DataFrame()
        df_clean["timestamp"] = pd.to_datetime(df[time_col])

        if hr_col:
            df_clean["heart_rate"] = pd.to_numeric(df[hr_col], errors="coerce")

        if steps_col:
            df_clean["steps"] = pd.to_numeric(df[steps_col], errors="coerce")

        # Remove rows with invalid data
        df_clean = df_clean.dropna(subset=["timestamp"])

        logger.info(f"Parsed {len(df_clean)} time-series records from {csv_file.name}")
        return df_clean, {}

    def parse_gpx_file(self, gpx_file: Path) -> pd.DataFrame:
        """Parse GPX file containing GPS track data"""
        if not HAS_GPX:
            logger.warning("GPX parsing not available. Install gpxpy: pip install gpxpy")
            return pd.DataFrame()

        try:
            with open(gpx_file, "r") as f:
                gpx = gpxpy.parse(f)

            points = []
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        # Convert timestamp to timezone-naive for consistency
                        timestamp = point.time
                        if (
                            timestamp is not None
                            and hasattr(timestamp, "tzinfo")
                            and timestamp.tzinfo is not None
                        ):
                            timestamp = timestamp.replace(tzinfo=None)

                        points.append(
                            {
                                "timestamp": timestamp,
                                "latitude": point.latitude,
                                "longitude": point.longitude,
                                "elevation": point.elevation,
                            }
                        )

            if not points:
                logger.warning(f"No track points found in {gpx_file.name}")
                return pd.DataFrame()

            df = pd.DataFrame(points)
            logger.info(f"Parsed {len(df)} GPS points from {gpx_file.name}")
            return df

        except Exception as e:
            logger.error(f"Error parsing GPX file {gpx_file}: {e}")
            return pd.DataFrame()

    def parse_tcx_file(self, tcx_file: Path) -> dict:
        """Parse TCX file containing training data and heart rate zones"""
        if not HAS_XML:
            logger.warning("TCX parsing not available")
            return {}

        try:
            tree = ET.parse(tcx_file)
            root = tree.getroot()

            # TCX uses namespaces
            namespace = {"tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}

            activity = root.find(".//tcx:Activity", namespace)
            if activity is None:
                logger.warning(f"No activity found in {tcx_file.name}")
                return {}

            # Extract summary data
            activity_type = activity.get("Sport", "Unknown")

            # Extract lap data
            laps = []
            for lap in activity.findall(".//tcx:Lap", namespace):
                lap_data = {
                    "start_time": lap.get("StartTime"),
                    "total_time_seconds": float(
                        lap.findtext("tcx:TotalTimeSeconds", "0", namespace)
                    ),
                    "distance_meters": float(lap.findtext("tcx:DistanceMeters", "0", namespace)),
                    "calories": int(lap.findtext("tcx:Calories", "0", namespace)),
                    "avg_hr": int(
                        lap.findtext(".//tcx:AverageHeartRateBpm/tcx:Value", "0", namespace)
                    ),
                    "max_hr": int(
                        lap.findtext(".//tcx:MaximumHeartRateBpm/tcx:Value", "0", namespace)
                    ),
                }
                laps.append(lap_data)

            logger.info(f"Parsed TCX file {tcx_file.name}: {activity_type} with {len(laps)} laps")
            return {"activity_type": activity_type, "laps": laps}

        except Exception as e:
            logger.error(f"Error parsing TCX file {tcx_file}: {e}")
            return {}

    def calculate_speed_from_gps(self, gps_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate speed from GPS track data"""
        if gps_df.empty or "latitude" not in gps_df.columns:
            return gps_df

        # Calculate distance between consecutive points using Haversine formula
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

        # Calculate distances
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

    def merge_data_sources(
        self, csv_df: pd.DataFrame, gps_df: pd.DataFrame, tcx_data: dict
    ) -> pd.DataFrame:
        """Merge data from CSV, GPX, and TCX sources"""
        if csv_df.empty:
            logger.warning("No CSV data available")
            return pd.DataFrame()

        # Start with CSV data
        merged = csv_df.copy()

        # Merge GPS data if available
        if not gps_df.empty:
            gps_df = self.calculate_speed_from_gps(gps_df)

            # Determine which columns to merge from GPS
            gps_cols_to_merge = ["timestamp"]

            # Only add GPS speed if CSV doesn't already have it
            if "speed_kmh" not in merged.columns:
                gps_cols_to_merge.append("speed_kmh")
            else:
                # Rename GPS speed to avoid conflict
                gps_df = gps_df.rename(columns={"speed_kmh": "gps_speed_kmh"})
                gps_cols_to_merge.append("gps_speed_kmh")

            # Only add cumulative distance if CSV doesn't have it
            if "cumulative_distance_km" not in merged.columns:
                gps_cols_to_merge.append("cumulative_distance_km")

            # Merge on timestamp (nearest match within 5 seconds)
            merged = pd.merge_asof(
                merged.sort_values("timestamp"),
                gps_df[gps_cols_to_merge].sort_values("timestamp"),
                on="timestamp",
                direction="nearest",
                tolerance=pd.Timedelta("5s"),
            )

            # If we renamed GPS speed, optionally use it to fill missing CSV speeds
            if "gps_speed_kmh" in merged.columns:
                if merged["speed_kmh"].isna().any():
                    # Fill missing CSV speeds with GPS speeds
                    merged["speed_kmh"] = merged["speed_kmh"].fillna(merged["gps_speed_kmh"])
                # Drop the temporary GPS speed column
                merged = merged.drop(columns=["gps_speed_kmh"])

        return merged

    def calculate_aggregate_metrics(
        self, timeseries_df: pd.DataFrame, march_duration_minutes: int
    ) -> dict:
        """Calculate aggregate metrics for the march"""
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
        """Calculate heart rate zone distribution"""
        if timeseries_df.empty or "heart_rate" not in timeseries_df.columns:
            return {}

        hr_data = timeseries_df["heart_rate"].dropna()
        total_samples = len(hr_data)

        if total_samples == 0:
            return {}

        # HR zones (using typical zones, adjust as needed)
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

    def process_participant(self, participant_id: str, files: dict[str, Path]) -> dict:
        """Process all data files for a single participant"""
        logger.info(f"Processing participant: {participant_id}")

        # IMPORTANT: Parse GPX file FIRST to get GPS crossing times
        gps_df = pd.DataFrame()
        crossing_times = None
        if "gpx" in files:
            gps_df = self.parse_gpx_file(files["gpx"])

            # Find GPS crossing times if coordinates are specified
            if not gps_df.empty and (self.start_coords or self.end_coords):
                logger.info(f"{participant_id}: Finding GPS crossing times...")
                crossing_times = self.find_gps_crossing_times(participant_id, gps_df)

                if crossing_times:
                    # Store crossing times for this participant
                    self.gps_crossing_times[participant_id] = crossing_times

                    # Trim GPS data using crossing times
                    gps_df = self.trim_data_by_gps_times(gps_df, crossing_times, "GPS data")

        # Parse CSV file (required)
        csv_df, csv_summary = self.parse_csv_file(files["csv"])

        # Trim CSV data using GPS crossing times (if found)
        if not csv_df.empty and crossing_times:
            logger.info(f"{participant_id}: Trimming CSV data using GPS crossing times")
            csv_df = self.trim_data_by_gps_times(csv_df, crossing_times, "CSV data")

        # Parse TCX file (optional)
        tcx_data = {}
        if "tcx" in files:
            tcx_data = self.parse_tcx_file(files["tcx"])

        # Handle combined format (time-series + summary) or time-series only
        if not csv_df.empty:
            logger.info(f"Processing with time-series data for {participant_id}")
            result = self._process_from_timeseries(participant_id, csv_df, gps_df, tcx_data)
            # If we also have summary data, add it to the result
            if csv_summary:
                result["csv_summary"] = csv_summary
            # Add crossing times to result
            if crossing_times:
                result["crossing_times"] = crossing_times
            return result

        # Handle summary-only format
        if csv_summary:
            logger.info(f"Processing with summary data only for {participant_id}")
            result = self._process_from_summary(participant_id, csv_summary, gps_df, tcx_data)
            # Add crossing times to result
            if crossing_times:
                result["crossing_times"] = crossing_times
            return result

        # No valid data
        logger.warning(f"No valid data for participant {participant_id}")
        return {}

    def _process_from_timeseries(
        self, participant_id: str, csv_df: pd.DataFrame, gps_df: pd.DataFrame, tcx_data: dict
    ) -> dict:
        """Process participant data from time-series CSV"""
        # Merge data sources
        merged_df = self.merge_data_sources(csv_df, gps_df, tcx_data)

        # Calculate time from march start
        if self.march_start_time:
            merged_df["timestamp_minutes"] = (
                merged_df["timestamp"] - self.march_start_time
            ).dt.total_seconds() / 60
        else:
            # Use relative time from first data point
            merged_df["timestamp_minutes"] = (
                merged_df["timestamp"] - merged_df["timestamp"].min()
            ).dt.total_seconds() / 60

        # Calculate march duration
        march_duration_minutes = int(merged_df["timestamp_minutes"].max())

        # Remove data with negative time (before march start)
        merged_df = merged_df[merged_df["timestamp_minutes"] >= 0].reset_index(drop=True)

        # Remove the initial cumulative distance offset if present
        if "cumulative_distance_km" in merged_df.columns:
            initial_distance = merged_df["cumulative_distance_km"].min()
            merged_df["cumulative_distance_km"] = (
                merged_df["cumulative_distance_km"] - initial_distance
            )

        # Resample to 1-minute intervals for timeseries data
        timeseries_df = (
            merged_df.set_index("timestamp")
            .resample("1min")
            .agg(
                {
                    "heart_rate": "mean",
                    "steps": "max",
                    "speed_kmh": "mean" if "speed_kmh" in merged_df.columns else lambda x: None,
                    "cumulative_distance_km": "max"
                    if "cumulative_distance_km" in merged_df.columns
                    else lambda x: None,
                    "timestamp_minutes": "mean",
                }
            )
            .reset_index()
        )

        # Calculate cumulative steps if not available
        if "steps" in timeseries_df.columns and timeseries_df["steps"].notna().any():
            if timeseries_df["steps"].isna().any():
                # Fill missing values with interpolation
                timeseries_df["steps"] = timeseries_df["steps"].interpolate(method="linear")

        # Calculate aggregate metrics
        aggregate_metrics = self.calculate_aggregate_metrics(merged_df, march_duration_minutes)

        # Calculate HR zones
        hr_zones = self.calculate_hr_zones(merged_df)

        # Prepare GPS positions data
        gps_positions = None
        if not gps_df.empty:
            gps_positions = gps_df.copy()
            # Calculate time from march start
            if self.march_start_time:
                gps_positions["timestamp_minutes"] = (
                    gps_positions["timestamp"] - self.march_start_time
                ).dt.total_seconds() / 60
            else:
                gps_positions["timestamp_minutes"] = (
                    gps_positions["timestamp"] - gps_positions["timestamp"].min()
                ).dt.total_seconds() / 60

        return {
            "participant_id": participant_id,
            "march_id": self.march_id,
            "timeseries": timeseries_df,
            "aggregate_metrics": aggregate_metrics,
            "hr_zones": hr_zones,
            "gps_positions": gps_positions,
            "tcx_data": tcx_data,
        }

    def _process_from_summary(
        self, participant_id: str, summary: dict, gps_df: pd.DataFrame, tcx_data: dict
    ) -> dict:
        """Process participant data from summary CSV (no time-series data)"""

        # Use summary data for aggregate metrics
        aggregate_metrics = {
            "avg_hr": summary.get("avg_hr"),
            "max_hr": summary.get("max_hr"),
            "total_steps": summary.get("estimated_steps"),
            "march_duration_minutes": int(summary.get("duration_minutes", 0)),
            "avg_pace_kmh": summary.get("avg_speed_kmh"),
            "estimated_distance_km": summary.get("total_distance_km"),
            "calories": summary.get("calories"),
            "data_completeness": 1.0,  # Summary data is always complete
        }

        # Try to generate synthetic time-series from GPX data
        timeseries_df = pd.DataFrame()
        if not gps_df.empty:
            timeseries_df = self._generate_timeseries_from_gps(gps_df, summary)

        # Can't calculate HR zones from summary data alone
        hr_zones = {}

        # Prepare GPS positions data
        gps_positions = None
        if not gps_df.empty:
            gps_df = self.calculate_speed_from_gps(gps_df)
            gps_positions = gps_df.copy()

            # Calculate time from march start
            if self.march_start_time:
                gps_positions["timestamp_minutes"] = (
                    gps_positions["timestamp"] - self.march_start_time
                ).dt.total_seconds() / 60
            else:
                start_time = summary.get("start_time", gps_positions["timestamp"].min())
                gps_positions["timestamp_minutes"] = (
                    gps_positions["timestamp"] - start_time
                ).dt.total_seconds() / 60

        return {
            "participant_id": participant_id,
            "march_id": self.march_id,
            "timeseries": timeseries_df,
            "aggregate_metrics": aggregate_metrics,
            "hr_zones": hr_zones,
            "gps_positions": gps_positions,
            "tcx_data": tcx_data,
            "csv_summary": summary,
        }

    def _generate_timeseries_from_gps(self, gps_df: pd.DataFrame, summary: dict) -> pd.DataFrame:
        """
        Generate synthetic time-series data from GPX and summary data

        This creates a time-series with:
        - Speed from GPS
        - Constant average heart rate (from summary)
        - Linear step estimation (from summary total steps)
        """
        if gps_df.empty:
            return pd.DataFrame()

        # Calculate speed from GPS
        gps_with_speed = self.calculate_speed_from_gps(gps_df)

        # Use march start time or GPS start time
        start_time = summary.get("start_time", gps_with_speed["timestamp"].min())

        # Calculate relative time
        gps_with_speed["timestamp_minutes"] = (
            gps_with_speed["timestamp"] - start_time
        ).dt.total_seconds() / 60

        # Resample to 1-minute intervals
        timeseries_df = (
            gps_with_speed.set_index("timestamp")
            .resample("1min")
            .agg(
                {"speed_kmh": "mean", "cumulative_distance_km": "max", "timestamp_minutes": "mean"}
            )
            .reset_index()
        )

        # Add constant average heart rate from summary
        if summary.get("avg_hr"):
            timeseries_df["heart_rate"] = summary["avg_hr"]

        # Add linearly interpolated steps from summary
        if summary.get("estimated_steps"):
            duration = summary.get("duration_minutes", len(timeseries_df))
            total_steps = summary["estimated_steps"]
            # Linear interpolation of steps over duration
            timeseries_df["steps"] = np.linspace(0, total_steps, len(timeseries_df))

        return timeseries_df

    def process_all_participants(self) -> list[dict]:
        """Process data for all participants and their activities"""
        participant_files = self.find_participant_files()

        results = []
        for participant_id, activities in participant_files.items():
            # If participant has multiple activities, merge them (same march with gaps)
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
                # Single activity - process normally
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
        """
        Process multiple activities for a participant and merge them into one timeline

        Multiple activities represent the same march with gaps (watch stopped/restarted)
        """
        all_csv_dfs = []
        all_gps_dfs = []
        all_summaries = []

        # Parse all activity files
        for activity_files in activities:
            activity_num = activity_files.get("activity_num", 1)
            logger.info(f"  Parsing {participant_id} activity {activity_num}")

            # Parse CSV
            csv_df, csv_summary = self.parse_csv_file(activity_files["csv"])
            if not csv_df.empty:
                all_csv_dfs.append(csv_df)
            if csv_summary:
                all_summaries.append(csv_summary)

            # Parse GPX if available
            if "gpx" in activity_files:
                gps_df = self.parse_gpx_file(activity_files["gpx"])
                if not gps_df.empty:
                    all_gps_dfs.append(gps_df)

        # Merge all CSV dataframes
        merged_csv = (
            pd.concat(all_csv_dfs, ignore_index=True).sort_values("timestamp")
            if all_csv_dfs
            else pd.DataFrame()
        )

        # Merge all GPS dataframes
        merged_gps = (
            pd.concat(all_gps_dfs, ignore_index=True).sort_values("timestamp")
            if all_gps_dfs
            else pd.DataFrame()
        )

        # Use first summary for metadata (or merge summaries if needed)
        merged_summary = all_summaries[0] if all_summaries else {}

        # IMPORTANT: Find GPS crossing times on MERGED GPS data (if coordinates specified)
        crossing_times = None
        if not merged_gps.empty and (self.start_coords or self.end_coords):
            logger.info(f"{participant_id}: Finding GPS crossing times on merged GPS data...")
            crossing_times = self.find_gps_crossing_times(participant_id, merged_gps)

            if crossing_times:
                # Store crossing times for this participant
                self.gps_crossing_times[participant_id] = crossing_times

                # Trim merged GPS data using crossing times
                merged_gps = self.trim_data_by_gps_times(merged_gps, crossing_times, "merged GPS data")

        # Trim merged CSV data using GPS crossing times (if found)
        if not merged_csv.empty and crossing_times:
            logger.info(f"{participant_id}: Trimming merged CSV data using GPS crossing times")
            merged_csv = self.trim_data_by_gps_times(merged_csv, crossing_times, "merged CSV data")

        # Process the merged data
        if not merged_csv.empty:
            logger.info(
                f"Processing merged data for {participant_id}: {len(merged_csv)} time-series records"
            )
            result = self._process_from_timeseries(participant_id, merged_csv, merged_gps, {})
            if merged_summary:
                result["csv_summary"] = merged_summary
            # Add crossing times to result
            if crossing_times:
                result["crossing_times"] = crossing_times
            return result
        elif merged_summary:
            logger.info(f"Processing merged summary for {participant_id}")
            result = self._process_from_summary(participant_id, merged_summary, merged_gps, {})
            # Add crossing times to result
            if crossing_times:
                result["crossing_times"] = crossing_times
            return result
        else:
            logger.warning(f"No valid merged data for {participant_id}")
            return {}

    def save_gps_crossing_times(self, output_dir: Path):
        """
        Save GPS crossing times to JSON file for use by other processing scripts

        This file can be used by the step processing script to trim accelerometer data
        """
        if not self.gps_crossing_times:
            logger.info("No GPS crossing times to save")
            return

        output_dir = Path(output_dir)
        output_file = output_dir / "gps_crossing_times.json"

        # Convert datetime objects to ISO format strings for JSON serialization
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
        """Save processed data to CSV files for database import"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save aggregate metrics
        metrics_data = []
        for result in results:
            if result.get("aggregate_metrics"):
                row = {
                    "march_id": result["march_id"],
                    "user_id": result["participant_id"],  # Will need to map to actual user_id
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
            # Select only relevant columns (include timestamp for easier merging)
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

            # Remove negative timestamps (data before march start)
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
            # Select relevant columns
            columns = [
                "march_id",
                "user_id",
                "timestamp_minutes",
                "latitude",
                "longitude",
                "elevation",
                "speed_kmh",
            ]
            gps_positions_df = gps_positions_df[
                [col for col in columns if col in gps_positions_df.columns]
            ]

            # Remove negative timestamps (data before march start)
            if "timestamp_minutes" in gps_positions_df.columns:
                negative_count = (gps_positions_df["timestamp_minutes"] < 0).sum()
                if negative_count > 0:
                    logger.info(
                        f"Removing {negative_count} GPS rows with negative timestamps (before march start)"
                    )
                    gps_positions_df = gps_positions_df[gps_positions_df["timestamp_minutes"] >= 0]

            # Add bearing calculation if possible
            if "latitude" in gps_positions_df.columns and "longitude" in gps_positions_df.columns:
                # Calculate bearing from consecutive points
                gps_positions_df["bearing"] = None  # Placeholder for now

            gps_file = output_dir / "march_gps_positions.csv"
            gps_positions_df.to_csv(gps_file, index=False)
            logger.info(f"Saved GPS positions to {gps_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Process watch data (CSV/GPX/TCX) for march dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--data-dir", required=True, help="Directory containing watch data files (CSV/GPX/TCX)"
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
        "--gps-tolerance",
        type=float,
        default=50.0,
        help="GPS tolerance in meters for detecting coordinate crossings (default: 50.0)"
    )

    parser.add_argument(
        "--output", default="./data/output", help="Output directory for CSV files (default: ./data/output)"
    )

    args = parser.parse_args()

    # Parse march start time if provided
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

    # Parse GPS coordinates for trimming
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

    try:
        # Create processor
        processor = WatchDataProcessor(
            data_dir=args.data_dir,
            march_id=args.march_id,
            march_start_time=march_start_time,
            march_end_time=march_end_time,
            start_coords=start_coords,
            end_coords=end_coords,
            gps_tolerance_m=args.gps_tolerance,
        )

        # Process all participants
        results = processor.process_all_participants()

        if not results:
            logger.error("No data was successfully processed")
            sys.exit(1)

        # Save results
        processor.save_to_csv(results, args.output)

        # Save GPS crossing times (for use by step processor)
        processor.save_gps_crossing_times(args.output)

        logger.info(f"Processing complete! Output saved to {args.output}")
        logger.info(f"Processed {len(results)} participants")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
