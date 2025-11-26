import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TemperatureProcessor:
    """Process temperature data to computetempsfor multiple participants"""

    def __init__(
        self,
        data_dir: Path,
        march_id: int,
        march_start_time: datetime | None = None,
        gps_crossing_times: dict | None = None
    ):
        """
        Initialize the processor

        Parameters
        ----------
        data_dir : Path
            Root directory containing participant folders
        march_id : int
            March event ID
        """
        self.data_dir = Path(data_dir)
        self.march_id = march_id
        self.march_start_time = march_start_time
        self.gps_crossing_times = gps_crossing_times or {}

        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")

    def find_participant_files(self) -> dict[str, list[Path]]:
        """
        Find all participant temperature files

        Structure: /path/to/data/<participant>/<date>/temp.parquet

        Returns
        -------
        dict[str, list[Path]]
            Dictionary mapping participant IDs to list of temp.parquet file paths
        """
        participants = {}

        # Look for folders with structure: participant/date/temp.parquet
        for participant_dir in self.data_dir.iterdir():
            if not participant_dir.is_dir():
                continue

            participant_id = participant_dir.name
            temp_files = []

            # Look for date subdirectories
            for date_dir in participant_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                temp_file = date_dir / "temp.parquet"
                if temp_file.exists():
                    temp_files.append(temp_file)
                    logger.info(f"Found temperature data: {participant_id}/{date_dir.name}")

            if temp_files:
                participants[participant_id] = sorted(temp_files)  # Sort by path (date)

        if not participants:
            logger.warning(f"No temperature files found in {self.data_dir}")
        else:
            total_files = sum(len(files) for files in participants.values())
            logger.info(
                f"Found {len(participants)} participants with {total_files} total temperature files"
            )

        return participants

    def process_participant(self, participant_id: str, temp_file: Path) -> pd.DataFrame | None:
        """
        Process temperature data for a single participant

        Parameters
        ----------
        participant_id : str
            Participant identifier
        temp_file : Path
            Path to temp.parquet file

        Returns
        -------
        Optional[pd.DataFrame]
            DataFrame with columns: time, sps (steps per second),temps(cumulative)
            Returns None if processing fails
        """
        try:
            logger.info(f"Processing {participant_id}...")

            # Read temperature data
            df_temp = pd.read_parquet(temp_file)

            # Check required columns
            required_cols = ["skin_temp", "heat_flux", "core_temp"]
            if not all(col in df_temp.columns for col in required_cols):
                logger.error(f"Missing required columns in {temp_file}. Required: {required_cols}")
                return None

            # We need advance the index by 1 hour so that it matches watch data
            df_temp.index += pd.Timedelta(hours=1)

            # Use index as timestamp if no timestamp column
            if "timestamp" not in df_temp.columns:
                df_temp = df_temp.reset_index()

            # Trim data using GPS crossing times FIRST (if available)
            if participant_id in self.gps_crossing_times:
                crossing_times = self.gps_crossing_times[participant_id]
                original_len = len(df_temp)

                # Parse start time if available
                if "start" in crossing_times:
                    start_time = pd.to_datetime(crossing_times["start"])
                    df_temp = df_temp[df_temp["Time"] >= start_time]
                    logger.info(f"{participant_id}: Trimmed to GPS start time {start_time}")

                # Parse end time if available
                if "end" in crossing_times:
                    end_time = pd.to_datetime(crossing_times["end"])
                    df_temp = df_temp[df_temp["Time"] <= end_time]
                    logger.info(f"{participant_id}: Trimmed to GPS end time {end_time}")

                trimmed_len = len(df_temp)
                if trimmed_len < original_len:
                    logger.info(
                        f"{participant_id}: GPS trimming removed {original_len - trimmed_len} rows "
                        f"({original_len} -> {trimmed_len})"
                    )

                if df_temp.empty:
                    logger.warning(f"No data after GPS trimming for {participant_id}")
                    return None

            # Remove unnecessary rows if march_start_time is specified (fallback if no GPS trimming)
            elif self.march_start_time is not None:
                df_temp = df_temp[df_temp["Time"] >= self.march_start_time]
                if df_temp.empty:
                    logger.warning(f"No data after march start time for {participant_id}")
                    return None

            # Remove rows with erroneous core_temp values
            df_temp = df_temp[(df_temp["core_temp"] >= 30) & (df_temp["core_temp"] <= 45)]

            if df_temp.empty:
                logger.warning(f"No temperature data in valid range for {participant_id}")
                return None

            # Add participant ID
            df_temp["participant_id"] = participant_id

            logger.info(
                f"Successfully processed {participant_id}: {len(df_temp)} temperature records"
            )

            return df_temp

        except Exception as e:
            logger.error(f"Error processing {participant_id}: {e}")
            return None

    def process_all_participants(self) -> list[pd.DataFrame]:
        """
        Process all participants

        Returns
        -------
        list[pd.DataFrame]
            List of DataFrames with temp data for each participant
        """
        participant_files = self.find_participant_files()

        if not participant_files:
            logger.error("No participant files found to process")
            return []

        results = []
        for participant_id, temp_files in participant_files.items():
            # Process all temp.parquet files for this participant and combine
            participant_dfs = []

            for temp_file in temp_files:
                logger.info(f"Processing {participant_id} - {temp_file.parent.name}")
                df_temps = self.process_participant(participant_id, temp_file)
                if df_temps is not None:
                    participant_dfs.append(df_temps)

            # Combine all date data for this participant
            if participant_dfs:
                if len(participant_dfs) > 1:
                    logger.info(f"Combining {len(participant_dfs)} date files for {participant_id}")
                    combined_df = pd.concat(participant_dfs, ignore_index=True)
                    # Sort by timestamp
                    combined_df = combined_df.sort_values("Time").reset_index(drop=True)
                    results.append(combined_df)
                else:
                    results.append(participant_dfs[0])

        logger.info(f"Successfully processed {len(results)}/{len(participant_files)} participants")
        return results

    def save_to_csv(self, results: list[pd.DataFrame], output_dir: Path):
        """
        Save processed temp data to CSV files

        Parameters
        ----------
        results : list[pd.DataFrame]
            List of processed temp data DataFrames
        output_dir : Path
            Output directory for CSV files
        """
        if not results:
            logger.warning("No results to save")
            return

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Combine all results
        all_data = []

        for df_temps in results:
            participant_id = df_temps["participant_id"].iloc[0]

            # Prepare data for output
            df_output = pd.DataFrame(
                {
                    "march_id": self.march_id,
                    "user_id": participant_id,
                    "timestamp": df_temps["Time"],
                    "skin_temp": df_temps["skin_temp"],
                    "heat_flux": df_temps["heat_flux"],
                    "core_temp": df_temps["core_temp"],
                }
            )

            # Calculate timestamp_minutes if march_start_time is provided
            if self.march_start_time is not None:
                df_output["timestamp_minutes"] = (
                    pd.to_datetime(df_output["timestamp"]) - self.march_start_time
                ).dt.total_seconds() / 60
            else:
                # Use relative time from first timestamp
                first_timestamp = pd.to_datetime(df_output["timestamp"].iloc[0])
                df_output["timestamp_minutes"] = (
                    pd.to_datetime(df_output["timestamp"]) - first_timestamp
                ).dt.total_seconds() / 60

            all_data.append(df_output)

        # Concatenate all results
        combined_df = pd.concat(all_data, ignore_index=True)

        # Save temp data
        output_file = output_dir / "march_temp_data.csv"
        combined_df.to_csv(output_file, index=False)
        logger.info(f"Saved temp data to {output_file}")

        # Save summary statistics
        summary_data = []
        for df_temps in results:
            participant_id = df_temps["participant_id"].iloc[0]
            avg_temp = df_temps["core_temp"].mean()
            min_temp = df_temps["core_temp"].min()
            max_temp = df_temps["core_temp"].max()

            summary_data.append(
                {
                    "march_id": self.march_id,
                    "user_id": participant_id,
                    "avg_core_temp": round(avg_temp, 2) if not pd.isna(avg_temp) else None,
                    "min_core_temp": round(min_temp, 2) if not pd.isna(min_temp) else None,
                    "max_core_temp": round(max_temp, 2) if not pd.isna(max_temp) else None,
                    "temp_readings_count": len(df_temps),
                }
            )

        summary_df = pd.DataFrame(summary_data)
        summary_file = output_dir / "march_temp_summary.csv"
        summary_df.to_csv(summary_file, index=False)
        logger.info(f"Saved temp summary to {summary_file}")


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description="Process temperature data to computetempsfor march participants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process temperature data
  python process_step_data.py --data-dir /path/to/participants --march-id 1 --output ./output

  # Use custom window size
  python process_step_data.py --data-dir /path/to/participants --march-id 1 --output ./output

  # With march start time for timestamp alignment
  python process_step_data.py --data-dir /path/to/participants --march-id 1 --march-start-time 2025-03-15T08:00:00 --output ./output

  # With GPS crossing times for trimming
  python process_step_data.py --data-dir /path/to/participants --march-id 1 --gps-trim-file gps_times.json --output ./output
        """,
    )

    parser.add_argument(
        "--data-dir",
        required=True,
        help="Root directory containing participant folders with temp.parquet files",
    )

    parser.add_argument("--march-id", type=int, required=True, help="March event ID")

    parser.add_argument(
        "--march-start-time",
        help="March start time (ISO format: YYYY-MM-DDTHH:MM:SS) for timestamp alignment",
    )

    parser.add_argument(
        "--gps-trim-file",
        help="JSON file with GPS crossing times (output from process_watch_data.py)",
    )

    parser.add_argument(
        "--output", default="./output", help="Output directory for CSV files (default: ./output)"
    )

    args = parser.parse_args()

    # Parse march start time if provided
    march_start_time = None
    if args.march_start_time:
        try:
            march_start_time = datetime.fromisoformat(args.march_start_time)
            logger.info(f"Using march start time: {march_start_time}")
        except ValueError:
            logger.error(f"Invalid march start time format: {args.march_start_time}")
            sys.exit(1)

    # Load GPS crossing times if provided
    gps_crossing_times = None
    if args.gps_trim_file:
        try:
            with open(args.gps_trim_file, "r") as f:
                gps_crossing_times = json.load(f)
            logger.info(
                f"Loaded GPS crossing times for {len(gps_crossing_times)} participants from {args.gps_trim_file}"
            )
        except FileNotFoundError:
            logger.error(f"GPS trim file not found: {args.gps_trim_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in GPS trim file: {e}")
            sys.exit(1)

    try:
        # Create processor
        processor = TemperatureProcessor(
            data_dir=args.data_dir,
            march_id=args.march_id,
            march_start_time=march_start_time,
            gps_crossing_times=gps_crossing_times,
        )

        # Process all participants
        logger.info("Starting temperature data processing...")
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
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
