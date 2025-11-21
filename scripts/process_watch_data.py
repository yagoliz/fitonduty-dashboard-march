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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WatchDataProcessor:
    """Processor for watch export data files"""

    def __init__(self, data_dir: Path, march_id: int, march_start_time: Optional[datetime] = None):
        self.data_dir = Path(data_dir)
        self.march_id = march_id
        self.march_start_time = march_start_time

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
            match = re.match(r'^([A-Za-z0-9]+)(?:_(\d+))?$', stem)

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
                'csv': csv_file,
                'activity_num': activity_num,
                'file_id': stem  # Original filename stem for identification
            }

            # Look for corresponding GPX and TCX files
            for ext in ['GPX', 'gpx']:
                gpx_file = csv_file.with_suffix(f'.{ext}')
                if gpx_file.exists():
                    activity_files['gpx'] = gpx_file
                    break

            for ext in ['TCX', 'tcx']:
                tcx_file = csv_file.with_suffix(f'.{ext}')
                if tcx_file.exists():
                    activity_files['tcx'] = tcx_file
                    break

            participants[participant_id].append(activity_files)

        # Sort activities by activity number for each participant
        for participant_id in participants:
            participants[participant_id].sort(key=lambda x: x['activity_num'])

        total_activities = sum(len(activities) for activities in participants.values())
        logger.info(f"Found {len(participants)} participants with {total_activities} total activities")

        return participants

    def parse_csv_file(self, csv_file: Path) -> tuple[pd.DataFrame, dict]:
        """
        Parse CSV file containing heart rate and sensor data

        Different watch manufacturers use different CSV formats. This function
        attempts to handle common formats:
        1. Time-series format: Rows with timestamp, heart rate, steps, etc.
        2. Summary format: Single row with activity summary (Polar/Suunto export)

        Returns:
            Tuple of (timeseries_df, summary_dict)
        """
        try:
            # Try to read the CSV file
            df = pd.read_csv(csv_file)

            # Check if this is a summary format CSV (Polar/Suunto style)
            summary_cols = ['Name', 'Sport', 'Date', 'Start time', 'Duration',
                          'Average heart rate (bpm)', 'Average cadence (rpm)']

            if all(col in df.columns for col in summary_cols[:4]):
                logger.info(f"Detected summary format CSV: {csv_file.name}")
                return self._parse_summary_csv(df, csv_file)

            # Otherwise, try to parse as time-series format
            return self._parse_timeseries_csv(df, csv_file)

        except Exception as e:
            logger.error(f"Error parsing CSV file {csv_file}: {e}")
            return pd.DataFrame(), {}

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
            date_str = row.get('Date', '')
            time_str = row.get('Start time', '')
            datetime_str = f"{date_str} {time_str}"
            start_time = pd.to_datetime(datetime_str, format='%d.%m.%Y %H:%M:%S', errors='coerce')

            if pd.isna(start_time):
                # Try alternative formats with dayfirst=True
                start_time = pd.to_datetime(datetime_str, dayfirst=True, errors='coerce')

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
        duration_str = row.get('Duration', '00:00:00')
        try:
            # Handle different duration formats
            duration_parts = duration_str.split(':')
            hours = int(duration_parts[0])
            minutes = int(duration_parts[1])
            seconds = float(duration_parts[2]) if len(duration_parts) > 2 else 0
            duration_minutes = hours * 60 + minutes + seconds / 60
        except Exception as e:
            logger.warning(f"Could not parse duration '{duration_str}': {e}")
            duration_minutes = 0

        # Extract metrics
        avg_hr = pd.to_numeric(row.get('Average heart rate (bpm)', np.nan), errors='coerce')
        max_hr = pd.to_numeric(row.get('Max heart rate', np.nan), errors='coerce')
        avg_cadence = pd.to_numeric(row.get('Average cadence (rpm)', np.nan), errors='coerce')
        avg_speed = pd.to_numeric(row.get('Average speed (km/h)', np.nan), errors='coerce')
        max_speed = pd.to_numeric(row.get('Max speed (km/h)', np.nan), errors='coerce')
        total_distance = pd.to_numeric(row.get('Total distance (km)', np.nan), errors='coerce')
        calories = pd.to_numeric(row.get('Calories', np.nan), errors='coerce')

        # Estimate steps from cadence
        # Average cadence (rpm) in running context = steps per minute
        # Total steps = average cadence × duration in minutes
        estimated_steps = None
        if not pd.isna(avg_cadence) and duration_minutes > 0:
            estimated_steps = int(avg_cadence * duration_minutes)
            logger.info(f"Estimated {estimated_steps} steps from cadence {avg_cadence} rpm over {duration_minutes:.1f} minutes")

        # Create summary dictionary
        summary = {
            'start_time': start_time,
            'duration_minutes': duration_minutes,
            'avg_hr': int(avg_hr) if not pd.isna(avg_hr) else None,
            'max_hr': int(max_hr) if not pd.isna(max_hr) else None,
            'avg_cadence': avg_cadence if not pd.isna(avg_cadence) else None,
            'estimated_steps': estimated_steps,
            'avg_speed_kmh': avg_speed if not pd.isna(avg_speed) else None,
            'max_speed_kmh': max_speed if not pd.isna(max_speed) else None,
            'total_distance_km': total_distance if not pd.isna(total_distance) else None,
            'calories': int(calories) if not pd.isna(calories) else None,
            'sport': row.get('Sport', 'Unknown'),
            'name': row.get('Name', 'Unknown')
        }

        logger.info(f"Parsed summary data from {csv_file.name}: {duration_minutes:.1f} min, "
                   f"avg HR {summary['avg_hr']}, {estimated_steps} steps (estimated)")

        # Return empty timeseries (will use GPX if available) and summary
        return pd.DataFrame(), summary

    def _parse_timeseries_csv(self, df: pd.DataFrame, csv_file: Path) -> tuple[pd.DataFrame, dict]:
        """
        Parse time-series format CSV (rows with timestamp and sensor data)
        """
        # Common column name variations
        time_cols = ['Time', 'time', 'Timestamp', 'timestamp', 'DateTime', 'datetime']
        hr_cols = ['Heart Rate', 'HR', 'hr', 'HeartRate', 'heart_rate', 'BPM', 'bpm']
        steps_cols = ['Steps', 'steps', 'Step Count', 'step_count']

        # Find the actual column names
        time_col = next((col for col in time_cols if col in df.columns), None)
        hr_col = next((col for col in hr_cols if col in df.columns), None)
        steps_col = next((col for col in steps_cols if col in df.columns), None)

        if not time_col:
            logger.warning(f"No time column found in {csv_file}. Available columns: {df.columns.tolist()}")
            return pd.DataFrame(), {}

        # Standardize column names
        df_clean = pd.DataFrame()
        df_clean['timestamp'] = pd.to_datetime(df[time_col])

        if hr_col:
            df_clean['heart_rate'] = pd.to_numeric(df[hr_col], errors='coerce')

        if steps_col:
            df_clean['steps'] = pd.to_numeric(df[steps_col], errors='coerce')

        # Remove rows with invalid data
        df_clean = df_clean.dropna(subset=['timestamp'])

        logger.info(f"Parsed {len(df_clean)} time-series records from {csv_file.name}")
        return df_clean, {}

    def parse_gpx_file(self, gpx_file: Path) -> pd.DataFrame:
        """Parse GPX file containing GPS track data"""
        if not HAS_GPX:
            logger.warning("GPX parsing not available. Install gpxpy: pip install gpxpy")
            return pd.DataFrame()

        try:
            with open(gpx_file, 'r') as f:
                gpx = gpxpy.parse(f)

            points = []
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        # Convert timestamp to timezone-naive for consistency
                        timestamp = point.time
                        if timestamp is not None and hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                            timestamp = timestamp.replace(tzinfo=None)

                        points.append({
                            'timestamp': timestamp,
                            'latitude': point.latitude,
                            'longitude': point.longitude,
                            'elevation': point.elevation
                        })

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
            namespace = {'tcx': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}

            activity = root.find('.//tcx:Activity', namespace)
            if activity is None:
                logger.warning(f"No activity found in {tcx_file.name}")
                return {}

            # Extract summary data
            activity_type = activity.get('Sport', 'Unknown')

            # Extract lap data
            laps = []
            for lap in activity.findall('.//tcx:Lap', namespace):
                lap_data = {
                    'start_time': lap.get('StartTime'),
                    'total_time_seconds': float(lap.findtext('tcx:TotalTimeSeconds', '0', namespace)),
                    'distance_meters': float(lap.findtext('tcx:DistanceMeters', '0', namespace)),
                    'calories': int(lap.findtext('tcx:Calories', '0', namespace)),
                    'avg_hr': int(lap.findtext('.//tcx:AverageHeartRateBpm/tcx:Value', '0', namespace)),
                    'max_hr': int(lap.findtext('.//tcx:MaximumHeartRateBpm/tcx:Value', '0', namespace))
                }
                laps.append(lap_data)

            logger.info(f"Parsed TCX file {tcx_file.name}: {activity_type} with {len(laps)} laps")
            return {
                'activity_type': activity_type,
                'laps': laps
            }

        except Exception as e:
            logger.error(f"Error parsing TCX file {tcx_file}: {e}")
            return {}

    def calculate_speed_from_gps(self, gps_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate speed from GPS track data"""
        if gps_df.empty or 'latitude' not in gps_df.columns:
            return gps_df

        # Calculate distance between consecutive points using Haversine formula
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Earth radius in km

            dlat = np.radians(lat2 - lat1)
            dlon = np.radians(lon2 - lon1)

            a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

            return R * c

        # Calculate distances
        gps_df = gps_df.sort_values('timestamp').reset_index(drop=True)

        distances = []
        speeds = []

        for i in range(len(gps_df)):
            if i == 0:
                distances.append(0)
                speeds.append(0)
            else:
                dist = haversine(
                    gps_df.loc[i-1, 'latitude'],
                    gps_df.loc[i-1, 'longitude'],
                    gps_df.loc[i, 'latitude'],
                    gps_df.loc[i, 'longitude']
                )

                time_diff = (gps_df.loc[i, 'timestamp'] - gps_df.loc[i-1, 'timestamp']).total_seconds() / 3600

                distances.append(dist)
                speeds.append(dist / time_diff if time_diff > 0 else 0)

        gps_df['distance_km'] = distances
        gps_df['cumulative_distance_km'] = np.cumsum(distances)
        gps_df['speed_kmh'] = speeds

        # Smooth speed data (remove outliers)
        gps_df['speed_kmh'] = gps_df['speed_kmh'].clip(0, 15)  # Max 15 km/h for marching

        return gps_df

    def merge_data_sources(self, csv_df: pd.DataFrame, gps_df: pd.DataFrame, tcx_data: dict) -> pd.DataFrame:
        """Merge data from CSV, GPX, and TCX sources"""
        if csv_df.empty:
            logger.warning("No CSV data available")
            return pd.DataFrame()

        # Start with CSV data
        merged = csv_df.copy()

        # Merge GPS data if available
        if not gps_df.empty:
            gps_df = self.calculate_speed_from_gps(gps_df)

            # Merge on timestamp (nearest match within 5 seconds)
            merged = pd.merge_asof(
                merged.sort_values('timestamp'),
                gps_df[['timestamp', 'speed_kmh', 'cumulative_distance_km']].sort_values('timestamp'),
                on='timestamp',
                direction='nearest',
                tolerance=pd.Timedelta('5s')
            )

        return merged

    def calculate_aggregate_metrics(self, timeseries_df: pd.DataFrame, march_duration_minutes: int) -> dict:
        """Calculate aggregate metrics for the march"""
        if timeseries_df.empty:
            return {}

        metrics = {
            'avg_hr': int(timeseries_df['heart_rate'].mean()) if 'heart_rate' in timeseries_df.columns else None,
            'max_hr': int(timeseries_df['heart_rate'].max()) if 'heart_rate' in timeseries_df.columns else None,
            'total_steps': int(timeseries_df['steps'].max()) if 'steps' in timeseries_df.columns else None,
            'march_duration_minutes': march_duration_minutes,
            'data_completeness': round(len(timeseries_df) / (march_duration_minutes * 60), 2)  # Assuming 1 sample per second
        }

        if 'speed_kmh' in timeseries_df.columns:
            metrics['avg_pace_kmh'] = round(timeseries_df['speed_kmh'].mean(), 2)
            metrics['estimated_distance_km'] = round(timeseries_df['cumulative_distance_km'].max(), 2) if 'cumulative_distance_km' in timeseries_df.columns else None

        return metrics

    def calculate_hr_zones(self, timeseries_df: pd.DataFrame) -> dict:
        """Calculate heart rate zone distribution"""
        if timeseries_df.empty or 'heart_rate' not in timeseries_df.columns:
            return {}

        hr_data = timeseries_df['heart_rate'].dropna()
        total_samples = len(hr_data)

        if total_samples == 0:
            return {}

        # HR zones (using typical zones, adjust as needed)
        zones = {
            'very_light_percent': round((hr_data < 100).sum() / total_samples * 100, 2),
            'light_percent': round(((hr_data >= 100) & (hr_data < 120)).sum() / total_samples * 100, 2),
            'moderate_percent': round(((hr_data >= 120) & (hr_data < 140)).sum() / total_samples * 100, 2),
            'intense_percent': round(((hr_data >= 140) & (hr_data < 160)).sum() / total_samples * 100, 2),
            'beast_mode_percent': round((hr_data >= 160).sum() / total_samples * 100, 2)
        }

        return zones

    def process_participant(self, participant_id: str, files: dict[str, Path]) -> dict:
        """Process all data files for a single participant"""
        logger.info(f"Processing participant: {participant_id}")

        # Parse CSV file (required)
        csv_df, csv_summary = self.parse_csv_file(files['csv'])

        # Parse GPX file (optional)
        gps_df = pd.DataFrame()
        if 'gpx' in files:
            gps_df = self.parse_gpx_file(files['gpx'])

        # Parse TCX file (optional)
        tcx_data = {}
        if 'tcx' in files:
            tcx_data = self.parse_tcx_file(files['tcx'])

        # Handle case where we have summary data but no time-series CSV
        if csv_df.empty and csv_summary:
            logger.info(f"Processing with summary data only for {participant_id}")
            return self._process_from_summary(participant_id, csv_summary, gps_df, tcx_data)

        # Handle case where we have time-series CSV data
        if not csv_df.empty:
            return self._process_from_timeseries(participant_id, csv_df, gps_df, tcx_data)

        # No valid data
        logger.warning(f"No valid data for participant {participant_id}")
        return {}

    def _process_from_timeseries(self, participant_id: str, csv_df: pd.DataFrame,
                                  gps_df: pd.DataFrame, tcx_data: dict) -> dict:
        """Process participant data from time-series CSV"""
        # Merge data sources
        merged_df = self.merge_data_sources(csv_df, gps_df, tcx_data)

        # Calculate time from march start
        if self.march_start_time:
            merged_df['timestamp_minutes'] = (merged_df['timestamp'] - self.march_start_time).dt.total_seconds() / 60
        else:
            # Use relative time from first data point
            merged_df['timestamp_minutes'] = (merged_df['timestamp'] - merged_df['timestamp'].min()).dt.total_seconds() / 60

        # Calculate march duration
        march_duration_minutes = int(merged_df['timestamp_minutes'].max())

        # Resample to 1-minute intervals for timeseries data
        timeseries_df = merged_df.set_index('timestamp').resample('1min').agg({
            'heart_rate': 'mean',
            'steps': 'max',
            'speed_kmh': 'mean' if 'speed_kmh' in merged_df.columns else lambda x: None,
            'cumulative_distance_km': 'max' if 'cumulative_distance_km' in merged_df.columns else lambda x: None,
            'timestamp_minutes': 'mean'
        }).reset_index()

        # Calculate cumulative steps if not available
        if 'steps' in timeseries_df.columns and timeseries_df['steps'].notna().any():
            if timeseries_df['steps'].isna().any():
                # Fill missing values with interpolation
                timeseries_df['steps'] = timeseries_df['steps'].interpolate(method='linear')

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
                gps_positions['timestamp_minutes'] = (gps_positions['timestamp'] - self.march_start_time).dt.total_seconds() / 60
            else:
                gps_positions['timestamp_minutes'] = (gps_positions['timestamp'] - gps_positions['timestamp'].min()).dt.total_seconds() / 60

        return {
            'participant_id': participant_id,
            'march_id': self.march_id,
            'timeseries': timeseries_df,
            'aggregate_metrics': aggregate_metrics,
            'hr_zones': hr_zones,
            'gps_positions': gps_positions,
            'tcx_data': tcx_data
        }

    def _process_from_summary(self, participant_id: str, summary: dict,
                              gps_df: pd.DataFrame, tcx_data: dict) -> dict:
        """Process participant data from summary CSV (no time-series data)"""

        # Use summary data for aggregate metrics
        aggregate_metrics = {
            'avg_hr': summary.get('avg_hr'),
            'max_hr': summary.get('max_hr'),
            'total_steps': summary.get('estimated_steps'),
            'march_duration_minutes': int(summary.get('duration_minutes', 0)),
            'avg_pace_kmh': summary.get('avg_speed_kmh'),
            'estimated_distance_km': summary.get('total_distance_km'),
            'calories': summary.get('calories'),
            'data_completeness': 1.0  # Summary data is always complete
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
                gps_positions['timestamp_minutes'] = (gps_positions['timestamp'] - self.march_start_time).dt.total_seconds() / 60
            else:
                start_time = summary.get('start_time', gps_positions['timestamp'].min())
                gps_positions['timestamp_minutes'] = (gps_positions['timestamp'] - start_time).dt.total_seconds() / 60

        return {
            'participant_id': participant_id,
            'march_id': self.march_id,
            'timeseries': timeseries_df,
            'aggregate_metrics': aggregate_metrics,
            'hr_zones': hr_zones,
            'gps_positions': gps_positions,
            'tcx_data': tcx_data,
            'csv_summary': summary
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
        start_time = summary.get('start_time', gps_with_speed['timestamp'].min())

        # Calculate relative time
        gps_with_speed['timestamp_minutes'] = (gps_with_speed['timestamp'] - start_time).dt.total_seconds() / 60

        # Resample to 1-minute intervals
        timeseries_df = gps_with_speed.set_index('timestamp').resample('1min').agg({
            'speed_kmh': 'mean',
            'cumulative_distance_km': 'max',
            'timestamp_minutes': 'mean'
        }).reset_index()

        # Add constant average heart rate from summary
        if summary.get('avg_hr'):
            timeseries_df['heart_rate'] = summary['avg_hr']

        # Add linearly interpolated steps from summary
        if summary.get('estimated_steps'):
            duration = summary.get('duration_minutes', len(timeseries_df))
            total_steps = summary['estimated_steps']
            # Linear interpolation of steps over duration
            timeseries_df['steps'] = np.linspace(0, total_steps, len(timeseries_df))

        return timeseries_df

    def process_all_participants(self) -> list[dict]:
        """Process data for all participants and their activities"""
        participant_files = self.find_participant_files()

        results = []
        for participant_id, activities in participant_files.items():
            # Process each activity for this participant
            for activity_files in activities:
                activity_num = activity_files.get('activity_num', 1)
                file_id = activity_files.get('file_id', participant_id)

                logger.info(f"Processing {participant_id} - Activity {activity_num} ({file_id})")

                try:
                    result = self.process_participant(participant_id, activity_files)
                    if result:
                        # Add activity metadata to result
                        result['activity_num'] = activity_num
                        result['file_id'] = file_id
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {participant_id} activity {activity_num}: {e}")

        logger.info(f"Successfully processed {len(results)} activities")
        return results

    def save_to_csv(self, results: list[dict], output_dir: Path):
        """Save processed data to CSV files for database import"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save aggregate metrics
        metrics_data = []
        for result in results:
            if result.get('aggregate_metrics'):
                row = {
                    'march_id': result['march_id'],
                    'user_id': result['participant_id'],  # Will need to map to actual user_id
                    **result['aggregate_metrics']
                }
                metrics_data.append(row)

        if metrics_data:
            metrics_df = pd.DataFrame(metrics_data)
            metrics_file = output_dir / 'march_health_metrics.csv'
            metrics_df.to_csv(metrics_file, index=False)
            logger.info(f"Saved aggregate metrics to {metrics_file}")

        # Save HR zones
        zones_data = []
        for result in results:
            if result.get('hr_zones'):
                row = {
                    'march_id': result['march_id'],
                    'user_id': result['participant_id'],
                    **result['hr_zones']
                }
                zones_data.append(row)

        if zones_data:
            zones_df = pd.DataFrame(zones_data)
            zones_file = output_dir / 'march_hr_zones.csv'
            zones_df.to_csv(zones_file, index=False)
            logger.info(f"Saved HR zones to {zones_file}")

        # Save timeseries data
        all_timeseries = []
        for result in results:
            if 'timeseries' in result and not result['timeseries'].empty:
                ts_df = result['timeseries'].copy()
                ts_df['march_id'] = result['march_id']
                ts_df['user_id'] = result['participant_id']
                all_timeseries.append(ts_df)

        if all_timeseries:
            timeseries_df = pd.concat(all_timeseries, ignore_index=True)
            # Select only relevant columns
            columns = ['march_id', 'user_id', 'timestamp_minutes', 'heart_rate',
                      'steps', 'speed_kmh', 'cumulative_distance_km']
            timeseries_df = timeseries_df[[col for col in columns if col in timeseries_df.columns]]

            timeseries_file = output_dir / 'march_timeseries_data.csv'
            timeseries_df.to_csv(timeseries_file, index=False)
            logger.info(f"Saved timeseries data to {timeseries_file}")


        # Save GPS positions
        all_gps = []
        for result in results:
            if result.get('gps_positions') is not None and not result['gps_positions'].empty:
                gps_df = result['gps_positions'].copy()
                gps_df['march_id'] = result['march_id']
                gps_df['user_id'] = result['participant_id']
                all_gps.append(gps_df)

        if all_gps:
            gps_positions_df = pd.concat(all_gps, ignore_index=True)
            # Select relevant columns
            columns = ['march_id', 'user_id', 'timestamp_minutes', 'latitude', 'longitude',
                      'elevation', 'speed_kmh']
            gps_positions_df = gps_positions_df[[col for col in columns if col in gps_positions_df.columns]]

            # Add bearing calculation if possible
            if 'latitude' in gps_positions_df.columns and 'longitude' in gps_positions_df.columns:
                # Calculate bearing from consecutive points
                gps_positions_df['bearing'] = None  # Placeholder for now

            gps_file = output_dir / 'march_gps_positions.csv'
            gps_positions_df.to_csv(gps_file, index=False)
            logger.info(f"Saved GPS positions to {gps_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Process watch data (CSV/GPX/TCX) for march dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--data-dir',
        required=True,
        help='Directory containing watch data files (CSV/GPX/TCX)'
    )

    parser.add_argument(
        '--march-id',
        type=int,
        required=True,
        help='March event ID'
    )

    parser.add_argument(
        '--march-start-time',
        help='March start time (ISO format: YYYY-MM-DDTHH:MM:SS)'
    )

    parser.add_argument(
        '--output',
        default='./output',
        help='Output directory for CSV files (default: ./output)'
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

    try:
        # Create processor
        processor = WatchDataProcessor(
            data_dir=args.data_dir,
            march_id=args.march_id,
            march_start_time=march_start_time
        )

        # Process all participants
        results = processor.process_all_participants()

        if not results:
            logger.error("No data was successfully processed")
            sys.exit(1)

        # Save results
        processor.save_to_csv(results, args.output)

        logger.info(f"Processing complete! Output saved to {args.output}")
        logger.info(f"Processed {len(results)} participants")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
