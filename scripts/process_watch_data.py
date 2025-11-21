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

    def find_participant_files(self) -> dict[str, dict[str, Path]]:
        """
        Find all participant data files in the data directory

        Returns:
            Dict mapping participant IDs to their CSV/GPX/TCX files
        """
        participants = {}

        # Find all CSV files
        csv_files = list(self.data_dir.glob("*.CSV")) + list(self.data_dir.glob("*.csv"))

        for csv_file in csv_files:
            # Extract participant ID from filename (e.g., SM001.CSV -> SM001)
            participant_id = csv_file.stem

            if participant_id not in participants:
                participants[participant_id] = {}

            participants[participant_id]['csv'] = csv_file

            # Look for corresponding GPX and TCX files
            for ext in ['GPX', 'gpx']:
                gpx_file = csv_file.with_suffix(f'.{ext}')
                if gpx_file.exists():
                    participants[participant_id]['gpx'] = gpx_file
                    break

            for ext in ['TCX', 'tcx']:
                tcx_file = csv_file.with_suffix(f'.{ext}')
                if tcx_file.exists():
                    participants[participant_id]['tcx'] = tcx_file
                    break

        logger.info(f"Found {len(participants)} participants with data files")
        return participants

    def parse_csv_file(self, csv_file: Path) -> pd.DataFrame:
        """
        Parse CSV file containing heart rate and sensor data

        Different watch manufacturers use different CSV formats. This function
        attempts to handle common formats.
        """
        try:
            # Try to read the CSV file
            df = pd.read_csv(csv_file)

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
                return pd.DataFrame()

            # Standardize column names
            df_clean = pd.DataFrame()
            df_clean['timestamp'] = pd.to_datetime(df[time_col])

            if hr_col:
                df_clean['heart_rate'] = pd.to_numeric(df[hr_col], errors='coerce')

            if steps_col:
                df_clean['steps'] = pd.to_numeric(df[steps_col], errors='coerce')

            # Remove rows with invalid data
            df_clean = df_clean.dropna(subset=['timestamp'])

            logger.info(f"Parsed {len(df_clean)} records from {csv_file.name}")
            return df_clean

        except Exception as e:
            logger.error(f"Error parsing CSV file {csv_file}: {e}")
            return pd.DataFrame()

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
                        points.append({
                            'timestamp': point.time,
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
        csv_df = self.parse_csv_file(files['csv'])
        if csv_df.empty:
            logger.warning(f"No valid data for participant {participant_id}")
            return {}

        # Parse GPX file (optional)
        gps_df = pd.DataFrame()
        if 'gpx' in files:
            gps_df = self.parse_gpx_file(files['gpx'])

        # Parse TCX file (optional)
        tcx_data = {}
        if 'tcx' in files:
            tcx_data = self.parse_tcx_file(files['tcx'])

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

    def process_all_participants(self) -> list[dict]:
        """Process data for all participants"""
        participant_files = self.find_participant_files()

        results = []
        for participant_id, files in participant_files.items():
            try:
                result = self.process_participant(participant_id, files)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error processing participant {participant_id}: {e}")

        logger.info(f"Successfully processed {len(results)} participants")
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