#!/usr/bin/env python3
"""
Merge watch data and step data for march dashboard

This script merges processed watch data (heart rate, speed) with step data
(accelerometer-based steps) to create a unified timeseries dataset.

The script performs intelligent merging:
- LEFT JOIN: Preserves all watch data, adds step data where available
- Merges on timestamp (with configurable tolerance) or timestamp_minutes
- Replaces watch-based steps with more accurate accelerometer steps
- Estimates missing steps using stride length calculation:
  * Calculates average stride length: total_distance / total_steps
  * Estimates missing steps: cumulative_distance / avg_stride_length
- Preserves all other watch metrics (heart rate, speed, distance)
- Handles missing data gracefully with detailed logging

Usage:
    python merge_march_data.py --watch-data ./output/march_timeseries_data.csv --step-data ./output/march_step_data.csv --output ./output
    python merge_march_data.py --watch-data watch.csv --step-data steps.csv --tolerance 30 --output merged_output
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarchDataMerger:
    """Merge watch and step data into unified timeseries"""

    def __init__(self, watch_data_file: Path, step_data_file: Path,
                 merge_on: str = 'timestamp', tolerance: Optional[float] = None,
                 watch_summary_file: Optional[Path] = None,
                 step_summary_file: Optional[Path] = None):
        """
        Initialize the merger

        Parameters
        ----------
        watch_data_file : Path
            Path to march_timeseries_data.csv from watch processing
        step_data_file : Path
            Path to march_step_data.csv from step processing
        merge_on : str
            Column to merge on: 'timestamp' or 'timestamp_minutes' (default: 'timestamp')
        tolerance : Optional[float]
            Tolerance for merge_asof in seconds (for timestamp) or minutes (for timestamp_minutes)
            Default: 30 seconds for timestamp, 1 minute for timestamp_minutes
        watch_summary_file : Optional[Path]
            Path to march_health_metrics.csv (optional)
        step_summary_file : Optional[Path]
            Path to march_step_summary.csv (optional)
        """
        self.watch_data_file = Path(watch_data_file)
        self.step_data_file = Path(step_data_file)
        self.merge_on = merge_on
        self.tolerance = tolerance
        self.watch_summary_file = Path(watch_summary_file) if watch_summary_file else None
        self.step_summary_file = Path(step_summary_file) if step_summary_file else None

        # Validate files exist
        if not self.watch_data_file.exists():
            raise FileNotFoundError(f"Watch data file not found: {watch_data_file}")
        if not self.step_data_file.exists():
            raise FileNotFoundError(f"Step data file not found: {step_data_file}")

        # Validate optional summary files
        if self.watch_summary_file and not self.watch_summary_file.exists():
            logger.warning(f"Watch summary file not found: {watch_summary_file}")
            self.watch_summary_file = None
        if self.step_summary_file and not self.step_summary_file.exists():
            logger.warning(f"Step summary file not found: {step_summary_file}")
            self.step_summary_file = None

        # Set default tolerance based on merge column
        if self.tolerance is None:
            if merge_on == 'timestamp':
                self.tolerance = 30  # 30 seconds
            else:
                self.tolerance = 1.0  # 1 minute

    def load_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load watch and step data from CSV files

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            Watch data and step data DataFrames
        """
        logger.info(f"Loading watch data from {self.watch_data_file}")
        df_watch = pd.read_csv(self.watch_data_file)
        logger.info(f"Loaded {len(df_watch)} watch data records")

        logger.info(f"Loading step data from {self.step_data_file}")
        df_steps = pd.read_csv(self.step_data_file)
        logger.info(f"Loaded {len(df_steps)} step data records")

        # Parse timestamp columns
        if 'timestamp' in df_watch.columns:
            df_watch['timestamp'] = pd.to_datetime(df_watch['timestamp'])
        if 'timestamp' in df_steps.columns:
            df_steps['timestamp'] = pd.to_datetime(df_steps['timestamp'])

        return df_watch, df_steps

    def prepare_step_data(self, df_steps: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare step data for merging

        Parameters
        ----------
        df_steps : pd.DataFrame
            Step data DataFrame

        Returns
        -------
        pd.DataFrame
            Prepared step data with renamed columns
        """
        # Select relevant columns
        merge_cols = ['march_id', 'user_id', self.merge_on]

        # Add step columns if available
        if 'cumulative_steps' in df_steps.columns:
            merge_cols.append('cumulative_steps')
        if 'steps_per_second' in df_steps.columns:
            merge_cols.append('steps_per_second')

        df_steps_merge = df_steps[merge_cols].copy()

        # Rename columns to avoid conflicts
        rename_map = {}
        if 'cumulative_steps' in df_steps_merge.columns:
            rename_map['cumulative_steps'] = 'steps_acc'
        if 'steps_per_second' in df_steps_merge.columns:
            rename_map['steps_per_second'] = 'sps_acc'

        if rename_map:
            df_steps_merge = df_steps_merge.rename(columns=rename_map)

        logger.info(f"Prepared step data with columns: {df_steps_merge.columns.tolist()}")
        return df_steps_merge

    def _estimate_steps_from_distance(self, merged: pd.DataFrame, user_id: str, march_id: int) -> pd.DataFrame:
        """
        Estimate steps from cumulative distance using calculated average stride length

        Strategy:
        1. Calculate average stride length: total_distance / total_steps
        2. For rows with distance but no steps: estimated_steps = cumulative_distance / avg_stride_length

        Parameters
        ----------
        merged : pd.DataFrame
            Merged data with steps_acc and cumulative_distance_km columns
        user_id : str
            User/participant ID (for logging)
        march_id : int
            March event ID (for logging)

        Returns
        -------
        pd.DataFrame
            DataFrame with estimated steps filled in
        """
        # Check if we have cumulative distance data
        if 'cumulative_distance_km' not in merged.columns:
            return merged

        # Find rows with both distance and steps (for calculating stride length)
        has_both = (
            merged['cumulative_distance_km'].notna() &
            merged['steps_acc'].notna() &
            (merged['cumulative_distance_km'] > 0) &
            (merged['steps_acc'] > 0)
        )

        if not has_both.any():
            # No rows with both distance and steps to calculate stride length
            return merged

        # Calculate average stride length using the maximum values (most reliable)
        # This gives us the overall average stride length for this participant
        max_distance_km = merged.loc[has_both, 'cumulative_distance_km'].max()
        max_steps = merged.loc[has_both, 'steps_acc'].max()

        if max_distance_km > 0 and max_steps > 0:
            # Convert distance to meters
            max_distance_m = max_distance_km * 1000

            # Calculate average stride length in meters
            avg_stride_length_m = max_distance_m / max_steps

            # Sanity check: typical stride length is 0.4m to 1.5m
            if 0.4 <= avg_stride_length_m <= 1.5:
                # Find rows with distance but no steps
                needs_estimation = (
                    merged['cumulative_distance_km'].notna() &
                    merged['steps_acc'].isna() &
                    (merged['cumulative_distance_km'] > 0)
                )

                if needs_estimation.any():
                    # Estimate steps: cumulative_steps = cumulative_distance / stride_length
                    distance_m = merged.loc[needs_estimation, 'cumulative_distance_km'] * 1000
                    estimated_steps = distance_m / avg_stride_length_m

                    # Update the steps column with estimates
                    merged.loc[needs_estimation, 'steps'] = estimated_steps

                    estimated_count = needs_estimation.sum()
                    logger.info(f"  Estimated steps for {estimated_count} rows using stride length {avg_stride_length_m:.2f}m")
                    logger.info(f"    (calculated from {max_distance_km:.2f}km / {int(max_steps)} steps)")
            else:
                logger.warning(f"  Invalid stride length {avg_stride_length_m:.2f}m - skipping estimation")

        return merged

    def merge_participant_data(self, watch_group: pd.DataFrame,
                               step_group: pd.DataFrame,
                               march_id: int, user_id: str) -> pd.DataFrame:
        """
        Merge watch and step data for a single participant

        Uses a LEFT JOIN approach - all watch data is preserved, step data is added where available.

        Parameters
        ----------
        watch_group : pd.DataFrame
            Watch data for this participant
        step_group : pd.DataFrame
            Step data for this participant
        march_id : int
            March event ID
        user_id : str
            User/participant ID

        Returns
        -------
        pd.DataFrame
            Merged data for this participant (all watch records preserved)
        """
        watch_records = len(watch_group)

        if step_group.empty:
            logger.warning(f"No step data found for {user_id} in march {march_id} - keeping all {watch_records} watch records")
            return watch_group

        # Determine tolerance for merge_asof
        if self.merge_on == 'timestamp':
            tolerance = pd.Timedelta(seconds=self.tolerance)
        else:
            tolerance = self.tolerance

        # Merge using merge_asof (LEFT JOIN - preserves all watch data)
        # This keeps ALL rows from watch_group and adds matching step data where available
        merged = pd.merge_asof(
            watch_group.sort_values(self.merge_on),
            step_group.sort_values(self.merge_on),
            on=self.merge_on,
            by=['march_id', 'user_id'],
            direction='nearest',
            tolerance=tolerance
        )

        # Verify we didn't lose any watch records
        if len(merged) != watch_records:
            logger.warning(f"  Warning: Expected {watch_records} records, got {len(merged)}")

        # Replace watch steps with accelerometer steps if available
        if 'steps_acc' in merged.columns:
            # Count how many rows have step data
            step_count = merged['steps_acc'].notna().sum()
            logger.info(f"  Matched {step_count}/{watch_records} records with step data ({step_count/watch_records*100:.1f}%)")

            # Replace steps column where accelerometer data is available
            if 'steps' in merged.columns:
                # Keep original watch steps where no accelerometer data
                merged['steps'] = merged['steps_acc'].fillna(merged['steps'])
            else:
                # No original steps, just use accelerometer data
                merged['steps'] = merged['steps_acc']

            # Estimate steps from distance where step data is missing but distance is available
            merged = self._estimate_steps_from_distance(merged, user_id, march_id)

            merged = merged.drop(columns=['steps_acc'])
        else:
            logger.info(f"  Kept all {watch_records} watch records (no step data matched)")

        # Optionally keep sps_acc as additional column for reference
        if 'sps_acc' in merged.columns:
            # Rename for clarity
            merged = merged.rename(columns={'sps_acc': 'steps_per_second'})

        return merged

    def merge_data(self, df_watch: pd.DataFrame, df_steps: pd.DataFrame) -> pd.DataFrame:
        """
        Merge watch and step data for all participants

        Uses LEFT JOIN - all watch data is preserved, step data is added where available.
        This ensures participants with watch data but no step data are still included.

        Parameters
        ----------
        df_watch : pd.DataFrame
            Watch data
        df_steps : pd.DataFrame
            Step data

        Returns
        -------
        pd.DataFrame
            Merged data (all watch records preserved)
        """
        logger.info(f"Merging data on column: {self.merge_on}")
        logger.info(f"Input: {len(df_watch)} watch records, {len(df_steps)} step records")

        # Prepare step data
        df_steps_merge = self.prepare_step_data(df_steps)

        # Merge by march_id and user_id
        merged_data = []
        participant_groups = df_watch.groupby(['march_id', 'user_id'])

        total_participants = len(participant_groups)
        participants_with_steps = 0

        for (march_id, user_id), watch_group in participant_groups:
            # Get corresponding step data
            step_group = df_steps_merge[
                (df_steps_merge['march_id'] == march_id) &
                (df_steps_merge['user_id'] == user_id)
            ]

            if not step_group.empty:
                participants_with_steps += 1

            # Merge this participant's data (LEFT JOIN preserves all watch data)
            logger.info(f"Merging data for {user_id} in march {march_id}")
            merged_group = self.merge_participant_data(
                watch_group, step_group, march_id, user_id
            )
            merged_data.append(merged_group)

        # Combine all merged groups
        df_merged = pd.concat(merged_data, ignore_index=True)

        logger.info(f"Merge complete:")
        logger.info(f"  Total records: {len(df_merged)} (preserved all {len(df_watch)} watch records)")
        logger.info(f"  Participants: {total_participants} total, {participants_with_steps} with step data")

        return df_merged

    def save_merged_data(self, df_merged: pd.DataFrame, output_dir: Path,
                        output_filename: str = 'march_timeseries_data_merged.csv'):
        """
        Save merged data to CSV

        Parameters
        ----------
        df_merged : pd.DataFrame
            Merged data
        output_dir : Path
            Output directory
        output_filename : str
            Output filename (default: march_timeseries_data_merged.csv)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / output_filename
        df_merged.to_csv(output_file, index=False)
        logger.info(f"Saved merged data to {output_file}")

        # Print summary statistics
        logger.info(f"Merged data summary:")
        logger.info(f"  Total records: {len(df_merged)}")
        logger.info(f"  Participants: {df_merged['user_id'].nunique()}")
        logger.info(f"  Marches: {df_merged['march_id'].nunique()}")

        # Check data completeness
        if 'steps' in df_merged.columns:
            step_completeness = (df_merged['steps'] > 0).sum() / len(df_merged) * 100
            logger.info(f"  Step data completeness: {step_completeness:.1f}%")

        if 'heart_rate' in df_merged.columns:
            hr_completeness = df_merged['heart_rate'].notna().sum() / len(df_merged) * 100
            logger.info(f"  Heart rate completeness: {hr_completeness:.1f}%")

    def merge_summary_files(self, output_dir: Path,
                           output_filename: str = 'march_health_metrics_merged.csv'):
        """
        Merge step summary data INTO health metrics for upload

        Uses LEFT JOIN to preserve all health metrics records and add step data where available.

        Parameters
        ----------
        output_dir : Path
            Output directory
        output_filename : str
            Output filename (default: march_health_metrics_merged.csv)
        """
        if not self.watch_summary_file:
            logger.warning("No watch summary file provided - cannot merge")
            return

        try:
            # Load health metrics (base file)
            logger.info(f"Loading health metrics from {self.watch_summary_file}")
            df_health_metrics = pd.read_csv(self.watch_summary_file)
            logger.info(f"Loaded {len(df_health_metrics)} health metrics records")

            # If no step summary file, just use health metrics as-is
            if not self.step_summary_file:
                logger.info("No step summary file - using health metrics only")
                df_merged = df_health_metrics
            else:
                # Load step summary
                logger.info(f"Loading step summary from {self.step_summary_file}")
                df_step_summary = pd.read_csv(self.step_summary_file)
                logger.info(f"Loaded {len(df_step_summary)} step summary records")

                # Select step columns to add (exclude join keys march_id, user_id)
                step_columns_to_add = ['march_id', 'user_id']  # Join keys

                # Add step-specific columns
                for col in ['total_steps', 'avg_steps_per_second', 'window_size_seconds']:
                    if col in df_step_summary.columns:
                        step_columns_to_add.append(col)

                df_step_subset = df_step_summary[step_columns_to_add].copy()

                # LEFT JOIN: Keep all health metrics, add step data where available
                df_merged = pd.merge(
                    df_health_metrics,
                    df_step_subset,
                    on=['march_id', 'user_id'],
                    how='left'  # Preserve all health metrics records
                )

                # Since there is 2 total steps columns, we get the new one as total_steps_y
                if 'total_steps_y' in df_merged.columns:
                    # Rename to total_steps for clarity
                    df_merged = df_merged.rename(columns={'total_steps_y': 'total_steps'})

                    # Drop old total_steps_x if exists
                    if 'total_steps_x' in df_merged.columns:
                        df_merged = df_merged.drop(columns=['total_steps_x'])

                # Log merge statistics
                step_data_count = df_merged['total_steps'].notna().sum()
                logger.info(f"Merged step data: {step_data_count}/{len(df_merged)} participants have step data")

                # If health metrics already has total_steps, prefer step summary data
                # (step summary uses accelerometer, more accurate)
                if 'total_steps' in df_health_metrics.columns and 'total_steps' in df_step_subset.columns:
                    # Count replacements
                    replaced_count = (df_health_metrics['total_steps'].notna() & df_merged['total_steps'].notna()).sum()
                    if replaced_count > 0:
                        logger.info(f"  Replaced {replaced_count} watch-based step counts with accelerometer data")

            # Save merged health metrics
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_dir / output_filename
            df_merged.to_csv(output_file, index=False)
            logger.info(f"Saved merged health metrics to {output_file}")

            # Print summary statistics
            logger.info(f"Merged health metrics summary:")
            logger.info(f"  Total participants: {len(df_merged)}")
            logger.info(f"  Marches: {df_merged['march_id'].nunique()}")
            logger.info(f"  Columns: {len(df_merged.columns)}")

            if 'total_steps' in df_merged.columns:
                step_completeness = df_merged['total_steps'].notna().sum()
                avg_steps = df_merged['total_steps'].mean()
                logger.info(f"  Step data: {step_completeness}/{len(df_merged)} participants ({step_completeness/len(df_merged)*100:.1f}%)")
                if pd.notna(avg_steps):
                    logger.info(f"  Average total steps: {int(avg_steps)}")

            if 'avg_hr' in df_merged.columns:
                hr_completeness = df_merged['avg_hr'].notna().sum()
                avg_hr = df_merged['avg_hr'].mean()
                logger.info(f"  Heart rate data: {hr_completeness}/{len(df_merged)} participants")
                if pd.notna(avg_hr):
                    logger.info(f"  Average heart rate: {int(avg_hr)} bpm")

        except Exception as e:
            logger.error(f"Error merging summary files: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Merge watch data and step data for march dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge using timestamp (most precise)
  python merge_march_data.py --watch-data ./output/march_timeseries_data.csv --step-data ./output/march_step_data.csv --output ./output

  # Merge using timestamp_minutes with custom tolerance
  python merge_march_data.py --watch-data watch.csv --step-data steps.csv --merge-on timestamp_minutes --tolerance 2.0 --output ./output

  # Merge with tight tolerance for high-resolution data
  python merge_march_data.py --watch-data watch.csv --step-data steps.csv --tolerance 10 --output ./output
        """
    )

    parser.add_argument(
        '--watch-data',
        required=True,
        help='Path to march_timeseries_data.csv from watch processing'
    )

    parser.add_argument(
        '--step-data',
        required=True,
        help='Path to march_step_data.csv from step processing'
    )

    parser.add_argument(
        '--watch-summary',
        help='Path to march_health_metrics.csv (optional, for summary merge)'
    )

    parser.add_argument(
        '--step-summary',
        help='Path to march_step_summary.csv (optional, for summary merge)'
    )

    parser.add_argument(
        '--merge-on',
        default='timestamp',
        choices=['timestamp', 'timestamp_minutes'],
        help='Column to merge on (default: timestamp)'
    )

    parser.add_argument(
        '--tolerance',
        type=float,
        help='Merge tolerance in seconds (for timestamp) or minutes (for timestamp_minutes). '
             'Default: 30 seconds for timestamp, 1 minute for timestamp_minutes'
    )

    parser.add_argument(
        '--output',
        default='./data/output',
        help='Output directory for merged CSV file (default: ./data/output)'
    )

    parser.add_argument(
        '--output-filename',
        default='march_timeseries_data_merged.csv',
        help='Output filename (default: march_timeseries_data_merged.csv)'
    )

    args = parser.parse_args()

    try:
        # Create merger
        merger = MarchDataMerger(
            watch_data_file=args.watch_data,
            step_data_file=args.step_data,
            merge_on=args.merge_on,
            tolerance=args.tolerance,
            watch_summary_file=args.watch_summary,
            step_summary_file=args.step_summary
        )

        # Load data
        df_watch, df_steps = merger.load_data()

        # Merge timeseries data
        df_merged = merger.merge_data(df_watch, df_steps)

        if df_merged.empty:
            logger.error("Merge resulted in empty dataset")
            sys.exit(1)

        # Save merged timeseries data
        merger.save_merged_data(df_merged, args.output, args.output_filename)

        # Merge summary files if provided
        if args.watch_summary or args.step_summary:
            logger.info("\nMerging summary files...")
            merger.merge_summary_files(args.output)

        logger.info("\nMerge complete!")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()