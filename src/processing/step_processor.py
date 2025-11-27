import json
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, sosfiltfilt, butter
from typing import Union, Any


def _validate_filter_params(signal: Union[np.ndarray, list], cutoff: float, fs: float, order: int, filter_type: str):
    """Validate common filter parameters."""
    # Convert to numpy array if needed
    signal = np.asarray(signal)

    # Check signal length
    if len(signal) < 2:
        raise ValueError(f"Signal too short for filtering: {len(signal)} samples. Minimum 2 samples required.")

    # For very short signals, check scipy limitations
    # sosfiltfilt requires signal length > 3 * ntaps, where ntaps = 2 * order
    min_samples_required = 6 * order + 1  # scipy requirement
    min_samples_recommended = 3 * order  # Quality recommendation

    if len(signal) <= min_samples_required:
        raise ValueError(f"Signal too short for order-{order} filter: {len(signal)} samples. "
                        f"Minimum required: {min_samples_required + 1} samples. "
                        f"Consider using a lower filter order or longer signal.")

    if len(signal) < min_samples_recommended * 3:  # More conservative warning
        print(f"Signal length ({len(signal)}) is shorter than recommended minimum "
                      f"({min_samples_recommended * 3}) for order-{order} filter. Results may contain artifacts.")

    # Validate sampling frequency
    if fs <= 0:
        raise ValueError(f"Sampling frequency must be positive, got {fs}")

    # Validate filter order
    if order < 1:
        raise ValueError(f"Filter order must be >= 1, got {order}")

    # Check Nyquist frequency constraints
    nyquist = 0.5 * fs

    if cutoff <= 0:
        raise ValueError(f"Cutoff frequency must be positive, got {cutoff}")

    if cutoff >= nyquist:
        raise ValueError(f"Cutoff frequency ({cutoff} Hz) must be less than Nyquist frequency "
                        f"({nyquist} Hz) for sampling rate {fs} Hz")

    # Additional check for frequencies very close to Nyquist (can cause numerical issues)
    if cutoff > 0.95 * nyquist:
        raise ValueError(f"Cutoff frequency ({cutoff} Hz) is too close to Nyquist frequency "
                        f"({nyquist} Hz). Maximum recommended: {0.95 * nyquist:.2f} Hz")

    return np.asarray(signal)

def _validate_bandpass_params(signal: Union[np.ndarray, list], lowcut: float, highcut: float, fs: float, order: int):
    """Validate bandpass filter parameters."""
    # First validate common parameters (using lowcut as cutoff)
    signal = _validate_filter_params(signal, lowcut, fs, order, "bandpass")

    # Additional bandpass-specific validations
    if highcut <= 0:
        raise ValueError(f"High cutoff frequency must be positive, got {highcut}")

    if lowcut >= highcut:
        raise ValueError(f"Low cutoff frequency ({lowcut}) must be less than high cutoff frequency ({highcut})")

    nyquist = 0.5 * fs
    if highcut >= nyquist:
        raise ValueError(f"High cutoff frequency ({highcut} Hz) must be less than Nyquist frequency "
                        f"({nyquist} Hz) for sampling rate {fs} Hz")

    if highcut > 0.95 * nyquist:
        raise ValueError(f"High cutoff frequency ({highcut} Hz) is too close to Nyquist frequency "
                        f"({nyquist} Hz). Maximum recommended: {0.95 * nyquist:.2f} Hz")

    return signal

def highpass_filter(
    s: Union[np.ndarray, list], lowcut: float, fs: float, order: int = 5
) -> np.ndarray:
    """
    Apply a Butterworth highpass filter to the signal.

    ### Args:
    - signal (np.ndarray): Array-like, the signal to be filtered.
    - lowcut (float): The low cutoff frequency of the filter.
    - fs (float): Sampling frequency of the signal
    - order (int): Order of the filter

    ### Returns:
    Array-like, the filtered signal.

    ### Raises:
    - ValueError: If parameters are invalid or signal is too short

    ### Example:

      >>> import numpy as np
      >>> data = np.random.randn(100)
      >>> lc = 0.4
      >>> fs = 50.0
      >>> filtered_data = highpass_filter(data, lc, fs, order=5)

    """
    # Validate parameters and convert signal
    signal = _validate_filter_params(s, lowcut, fs, order, "highpass")

    try:
        nyq = 0.5 * fs
        low = lowcut / nyq
        sos = butter(order, low, btype="highpass", output="sos")
        y = sosfiltfilt(sos, signal)
        return y
    except Exception as e:
        print(f"Error in highpass filter: {str(e)}")
        raise RuntimeError(f"Filter operation failed: {str(e)}") from e


def lowpass_filter(
    s: Union[np.ndarray, list], highcut: float, fs: float, order: int = 5
) -> np.ndarray:
    """
    Apply a Butterworth lowpass filter to the signal.

    ### Args:
    - signal (np.ndarray): Array-like, the signal to be filtered.
    - highcut (float): The high cutoff frequency of the filter.
    - fs (float): Sampling frequency of the signal
    - order (int): Order of the filter

    ### Returns:
    Array-like, the filtered signal.

    ### Raises:
    - ValueError: If parameters are invalid or signal is too short

    ### Example:

      >>> import numpy as np
      >>> data = np.random.randn(100)
      >>> hc = 10.5
      >>> fs = 50.0
      >>> filtered_data = lowpass_filter(data, hc, fs, order=5)

    """
    # Validate parameters and convert signal
    signal = _validate_filter_params(s, highcut, fs, order, "lowpass")

    try:
        nyq = 0.5 * fs
        high = highcut / nyq
        sos = butter(order, high, btype="lowpass", output="sos")
        y = sosfiltfilt(sos, signal)
        return y
    except Exception as e:
        print(f"Error in lowpass filter: {str(e)}")
        raise RuntimeError(f"Filter operation failed: {str(e)}") from e


def bandpass_filter(
    s: Union[np.ndarray, list], lowcut: float, highcut: float, fs: float, order: int = 5
) -> np.ndarray:
    """
    Apply a Butterworth bandpass filter to the signal.

    ### Args:
    - signal (np.ndarray): Array-like, the signal to be filtered.
    - lowcut (float): The low cutoff frequency of the filter.
    - highcut (float): The high cutoff frequency of the filter.
    - fs (float): Sampling frequency of the signal
    - order (int): Order of the filter

    ### Returns:
    Array-like, the filtered signal.

    ### Raises:
    - ValueError: If parameters are invalid or signal is too short

    ### Example:

      >>> import numpy as np
      >>> data = np.random.randn(100)
      >>> lc = 2.0
      >>> hc = 10.5
      >>> fs = 50.0
      >>> filtered_data = bandpass_filter(data, lc, hc, fs, order=5)

    """
    # Validate parameters and convert signal
    signal = _validate_bandpass_params(s, lowcut, highcut, fs, order)

    try:
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        sos = butter(order, [low, high], btype="bandpass", output="sos")
        y = sosfiltfilt(sos, signal)
        return y
    except Exception as e:
        print(f"Error in bandpass filter: {str(e)}")
        raise RuntimeError(f"Filter operation failed: {str(e)}") from e


def acceleration_filter(
    acc: pd.DataFrame, fs: float, lowcut: float = 10.0
) -> pd.DataFrame:
    """
    Apply a Butterworth highpass filter to the acceleration signals.

    ### Args:
    - acc (pd.DataFrame): DataFrame, the acceleration signals.
    - fs (int): Sampling frequency of the signal
    - lowcut (float): The low cutoff frequency of th filter.

    ### Returns:
    DataFrame, the filtered acceleration signals.

    ### Example:

      >>> import pandas as pd
      >>> data = pd.DataFrame({"x": np.random(100), "y": np.random(100), "z": np.random(100)})
      >>> fs = 50.0
      >>> filtered_data = acceleration_filter(data, fs, lowcut=10.0)

    """
    acc["Xf"] = highpass_filter(acc["X"].values, lowcut, fs)
    acc["Yf"] = highpass_filter(acc["Y"].values, lowcut, fs)
    acc["Zf"] = highpass_filter(acc["Z"].values, lowcut, fs)

    return acc


def ppg_filter(
    ppg: pd.DataFrame, fs: float, lowcut: float = 0.3, highcut: float = 4.0
) -> pd.DataFrame:
    """
    Apply a Butterworth bandpass filter to the PPG signals.

    ### Args:
    - ppg (pd.DataFrame): DataFrame, the PPG signals.
    - fs (int): Sampling frequency of the signal
    - lowcut (float): The low cutoff frequency of th filter.
    - highcut (float): The high cutoff frequency of th filter.

    ### Returns:
    DataFrame, the filtered PPG signals.

    ### Example:

      >>> import pandas as pd
      >>> data = pd.DataFrame({"P0": np.random(100), "P1": np.random(100), "P2": np.random(100)})
      >>> fs = 50.0
      >>> filtered_data = ppg_filter(data, fs, lowcut=0.3, highcut=4.0)

    """
    ppg["P0f"] = bandpass_filter(ppg["P0"].values, lowcut, highcut, fs)
    ppg["P1f"] = bandpass_filter(ppg["P1"].values, lowcut, highcut, fs)
    ppg["P2f"] = bandpass_filter(ppg["P2"].values, lowcut, highcut, fs)

    return ppg



def find_peaks_and_minimas_np(mag: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Find peaks and minima in the magnitude data using a custom algorithm.
    This function processes the magnitude data to identify significant peaks and minima,
    which are then used to calculate steps per second.

    Parameters
    ----------
    mag : np.ndarray
        The magnitude data as a NumPy array.

    Returns
    -------
    minima_indices : np.ndarray
        Indices of the minima in the magnitude data.
    peaks_indices : np.ndarray
        Indices of the peaks in the magnitude data.
    """

    # Get the minimum points for range of 5
    argmins = [np.argmin(mag[i : i + 5]) + i for i in range(0, mag.shape[0] - 10, 5)]
    argmins_mag = [mag[i] for i in argmins]

    # Find minima in the processed data
    minima, _ = find_peaks(-np.array(argmins_mag).reshape(-1), height=100)

    # Get indices and magnitudes of minima
    minima_indices = np.array(argmins)[minima]
    minima_magnitudes = np.array(argmins_mag)[minima]

    # Find peaks between minima
    peaks_indices = np.array(
        [
            np.argmax(mag[minima_indices[i] : minima_indices[i + 1]]) + minima_indices[i]
            for i in range(len(minima_indices) - 1)
        ]
    )
    peaks_magnitudes = np.array([mag[i] for i in peaks_indices])

    # Only use peaks with magnitudes greater than 100
    peaks_indices = peaks_indices[peaks_magnitudes > 100]
    peaks_magnitudes = peaks_magnitudes[peaks_magnitudes > 100]

    # Find minima between peaks
    minima_indices = np.array(
        [
            np.argmin(mag[peaks_indices[i] : peaks_indices[i + 1]]) + peaks_indices[i]
            for i in range(len(peaks_indices) - 1)
        ]
    )
    minima_magnitudes = np.array([mag[i] for i in minima_indices])

    # Difference between peak and minima magnitudes
    diff_magnitudes = peaks_magnitudes[:-1] - minima_magnitudes
    consecutive_diff_ratio = diff_magnitudes / np.roll(diff_magnitudes, -1)
    correction_vector = (consecutive_diff_ratio > 0.5).astype(int)

    # Adjust with correction vector
    array = np.array(
        [minima_indices, minima_magnitudes, peaks_indices[:-1], peaks_magnitudes[:-1]]
    ).T
    array = array[correction_vector == 1]

    # Difference between peaks and magnitudes index
    correction_vector = ((array[:, 0] - array[:, 2]) < 40).astype(int)
    array = array[correction_vector == 1]

    # Get the 0.75 quantile of the peak magnitude
    median_value = np.median(array[:, 3])
    array = np.array([array[:-1, 0], array[:-1, 1], array[1:, 2], array[1:, 3]]).T
    correction_vector = (array[:, 3] > (median_value * 0.5)).astype(int)
    array = array[correction_vector == 1]

    # Get values again
    minima_indices = array[:, 0].astype(int)
    minima_magnitudes = array[:, 1]
    peaks_indices = array[:, 2].astype(int)
    peaks_magnitudes = array[:, 3]

    return minima_indices, peaks_indices


def _perform_fft(mag: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Perform Fast Fourier Transform (FFT) on the magnitude data and filter the results.

    Parameters
    ----------
    mag : np.ndarray
        The magnitude data as a NumPy array.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        A tuple containing:
        - pos_fft_magnitudes: The magnitudes of the positive frequencies after filtering.
        - pos_frequencies: The positive frequencies corresponding to the magnitudes.
    """

    #  Apply hamming window
    N = len(mag)
    window = np.hamming(N)
    windowed_mag = mag * window

    # Fourier Transform
    fft_windowed_mag = np.fft.fft(windowed_mag)
    T = 1 / 52

    # Frequencies
    frequencies = np.fft.fftfreq(N, T)
    pos_frequencies = frequencies[: N // 2]

    # Filter my fft results:
    low_cutoff = 1.4
    high_cutoff = 10

    # Create filter mask
    filter_mask = (np.abs(frequencies) >= low_cutoff) & (np.abs(frequencies) <= high_cutoff)

    # Apply filter (only for windowed) part
    filtered_fft_win_mag = fft_windowed_mag * filter_mask

    # Magnitudes
    fft_magnitudes = np.abs(filtered_fft_win_mag)

    # Positive frequencies and magnitudes
    pos_fft_magnitudes = fft_magnitudes[: N // 2]

    return pos_fft_magnitudes, pos_frequencies


def _calculate_steps_amplitude_peaks_ptn(
    pos_fft_magnitudes: np.ndarray, pos_frequencies: np.ndarray, interval: int
) -> tuple[float, float, float]:
    """
    Calculate steps per second, amplitude, and peak-to-noise ratio from FFT results.
    This function processes the FFT magnitudes and frequencies to determine the steps per second,
    amplitude, and peak-to-noise ratio, which are used to assess the quality of the FFT results.

    Parameters
    ----------
    pos_fft_magnitudes : np.ndarray
        The magnitudes of the positive frequencies from the FFT.
    pos_frequencies : np.ndarray
        The positive frequencies corresponding to the magnitudes.
    interval : int
        The interval in seconds for which the FFT was calculated.

    Returns
    -------
    tuple
        A tuple containing:
        - steps_per_second: The calculated steps per second.
        - amplitude: The corrected amplitude of the FFT.
        - ptn_ratio: The peak-to-noise ratio calculated from the FFT magnitudes.
    """

    # Get the steps per second
    if (
        len(pos_fft_magnitudes) == len(pos_frequencies) == int(interval / 2)
        and max(pos_fft_magnitudes) > 0
    ):
        max_mag = max(pos_fft_magnitudes)

        index_max_mag, _ = find_peaks(pos_fft_magnitudes, height=max_mag)
        index_max_mag = index_max_mag[0]

        # Steps per second or frequency
        steps_per_second = 0
        if pos_frequencies.size > 0:
            steps_per_second = pos_frequencies[int(index_max_mag)]

        # Get the corrected magnitude of the amplitude to judge if someone is actually walking -> cuts out any low activity movements
        window_correction = 1.63  # Approximation for hamming
        amplitude = (max_mag / interval) * window_correction * 2

        # Calculate peak to noise ratio to judge the quality of the fft
        adj_pos_magnitudes = [pos_fft_magnitudes[7:51]]
        ptn_ratio = float(np.median([(mag / max_mag) * 10 for mag in adj_pos_magnitudes]))

        # Return the steps per second calculation and the amplitude
        return steps_per_second, amplitude, ptn_ratio
    else:
        return 0, 0, 0


def fft_and_processing(df: pd.DataFrame, start: int, interval_seconds: int) -> float:
    """
    Perform FFT on the magnitude data and calculate steps per second.
    This function processes the magnitude data from a DataFrame, applies FFT, and calculates
    the steps per second based on the frequency and amplitude of the FFT results.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing accelerometer data with a 'magnitude' column.
    start : int
        The starting index for the FFT calculation.
    interval_seconds : int
        The interval in seconds for which the FFT is calculated.

    Returns
    -------
    float
        The calculated steps per second based on the FFT results. Returns 0 if the conditions are not met.
    """

    # Get interval and window
    interval = df.shape[0]

    frequency = 52

    # Transform to np array
    mag = np.array(df["magnitude"])

    # Perform fft and return positive magnitudes and frequencies
    pos_fft_magnitudes, pos_frequencies = _perform_fft(mag)

    # Get steps per second, amplitudes and ptn_ratio from fft values
    sps_fft, amplitude_fft, ptn_ratio = _calculate_steps_amplitude_peaks_ptn(
        pos_fft_magnitudes, pos_frequencies, interval
    )

    # Check if the values are in the right range to be considered as steps
    if 10 > sps_fft >= 1.4 and amplitude_fft > 100 and ptn_ratio < 2:
        filtered_mag = lowpass_filter(mag, highcut=10, fs=frequency, order=2)

        # Get peaks and minima
        minima, peaks = find_peaks_and_minimas_np(filtered_mag)

        # Steps from minima
        sps_peaks = (len(peaks) + 1) / (interval_seconds)

        # Adjust if the fft got twice the sps
        if (
            abs(sps_fft / 2 - sps_peaks) <= 0.5 and sps_peaks >= 1.4 and sps_fft >= 2.8
        ) or sps_fft >= 5:
            sps_fft = sps_fft / 2

        return sps_fft
    else:
        return 0


def get_magnitudes(df_input: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate the magnitude of the accelerometer data and apply a high-pass filter.

    Parameters
    ----------
    df_input : pd.DataFrame
        DataFrame containing accelerometer data with columns 'X', 'Y', 'Z'.

    Returns
    -------
    pd.DataFrame
        DataFrame with the calculated magnitudes and filtered values.
    """

    df = df_input.copy()
    time_series = None

    np_df = np.array(df[["X", "Y", "Z"]])
    np_df = np_df.astype(float)

    time_series = df["Time"]
    mag = np.linalg.norm(np_df, axis=1)

    # High-pass filter the magnitude
    try:
        filtered_mag = highpass_filter(mag, lowcut=0.5, fs=52, order=2)
    except Exception as e:
        print(f"High-pass filtering failed - Reason: {e}")
        return pd.DataFrame()

    df_mag = pd.DataFrame(
        {
            "time": time_series,
            "X": np_df[:, 0],
            "Y": np_df[:, 1],
            "Z": np_df[:, 2],
            "magnitude": filtered_mag,
        }
    )

    # Reset_index of df
    df_mag.reset_index(inplace=True, drop=True)

    return df_mag


def get_steps(df: pd.DataFrame, interval_size: int = 8) -> pd.DataFrame:
    """
    Calculate steps from the magnitude data in a DataFrame.
    Uses time-based grouping to handle gaps in the data properly.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing accelerometer data with a 'magnitude' column and 'time' column.
    interval_size : int
        Size of the interval in seconds for calculating steps.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the calculated steps per second, sample, and time.
    """

    # window to get the fft from
    min_samples = 3 * 52  # 3 seconds of data at 52 Hz

    # Ensure time column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = pd.to_datetime(df['time'])

    # Set time as index for groupby
    df_indexed = df.set_index('time').sort_index()

    # Group by time intervals
    grouped = df_indexed.groupby(pd.Grouper(freq=f'{interval_size}s'))

    # lists for steps
    sps_l = []
    sample_l = []
    time_l = []

    # Process each time chunk
    for timestamp, group in grouped:
        # Use starting timestamp of the chunk
        time_l.append(timestamp)

        if group.shape[0] < min_samples:
            sps_l.append(0)
            sample_l.append(0)
            continue

        # Reset index to get integer-based indexing for fft_and_processing
        group_reset = group.reset_index()

        # Use the first sample of the chunk (start = 0)
        sps = fft_and_processing(group_reset, start=0, interval_seconds=interval_size)

        # Use the middle sample index relative to original df
        # (for backward compatibility with existing code)
        mid_idx = len(group) // 2
        sample_l.append(mid_idx)

        sps_l.append(sps)

    df_steps = pd.DataFrame(
        {
            "time": time_l,
            "sample": sample_l,
            "sps": sps_l,
        }
    )

    return df_steps


def calculate_steps(df: pd.DataFrame, interval_size: int = 8) -> tuple[pd.DataFrame, int]:
    """
    Calculate steps from accelerometer data in a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing accelerometer data with 'X', 'Y', and 'Z' columns.
    interval_size : int
        Size of the interval in seconds for calculating steps.

    Returns
    -------
    tuple[pd.DataFrame, int]
        A tuple containing:
        - DataFrame with calculated steps per second, sample, and time.
        - Interval size in seconds.
    """

    df_mag = get_magnitudes(df)
    df
    if df_mag.empty:
        print("No valid data found for step calculation.")
        return pd.DataFrame(), interval_size

    df_steps = get_steps(df_mag, interval_size)
    return df_steps, interval_size


def get_step_count_and_distribution(df: pd.DataFrame, interval_size: int = 8) -> pd.DataFrame:
    """
    Calculate the step count and distribution of activities based on accelerometer data.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing accelerometer data with 'X', 'Y', and 'Z' columns.
    interval_size : int
        Size of the interval in seconds for calculating steps.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the total number of steps and the distribution of activities.
    """

    # Ensure the DataFrame has the required columns
    if not {"X", "Y", "Z"}.issubset(df.columns):
        raise ValueError("DataFrame must contain 'X', 'Y', and 'Z' columns.")

    # Calculate the magnitudes and get the DataFrame with magnitudes
    df_steps, interval_size = calculate_steps(df)
    if df_steps.empty:
        return pd.DataFrame()

    # Extract the total number of steps
    total_number_of_steps = int(df_steps["sps"].sum() * interval_size)

    # Get the number of entries for eaach activity
    slow_walking = df_steps[df_steps["sps"].between(1, 1.8)]
    fast_walking = df_steps[df_steps["sps"].between(1.81, 2.4)]
    jogging = df_steps[df_steps["sps"].between(2.41, 2.9)]
    running = df_steps[df_steps["sps"] > 2.9]

    # Calculate the number of seconds for each activity
    slow_walking_seconds = int(len(slow_walking) * interval_size)
    fast_walking_seconds = int(len(fast_walking) * interval_size)
    jogging_seconds = int(len(jogging) * interval_size)
    running_seconds = int(len(running) * interval_size)

    # Create a DataFrame with the results
    result = {}
    result["steps"] = [total_number_of_steps]
    result["walking"] = [slow_walking_seconds]
    result["walking_fast"] = [fast_walking_seconds]
    result["jogging"] = [jogging_seconds]
    result["running"] = [running_seconds]
    result["walking_minutes"] = [slow_walking_seconds / 60]
    result["walking_fast_minutes"] = [fast_walking_seconds / 60]
    result["jogging_minutes"] = [jogging_seconds / 60]
    result["running_minutes"] = [running_seconds / 60]
    result["interval_size"] = [interval_size]

    return pd.DataFrame.from_dict(result, orient="columns")


# ============================================================================
# Main processing functions for batch processing
# ============================================================================

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AccelerometerStepProcessor:
    """Process accelerometer data to compute steps for multiple participants"""

    def __init__(self, data_dir: Path, march_id: int, window_size: int = 8,
                 march_start_time: Optional[datetime] = None,
                 gps_crossing_times: Optional[dict] = None):
        """
        Initialize the processor

        Parameters
        ----------
        data_dir : Path
            Root directory containing participant folders
        march_id : int
            March event ID
        window_size : int
            Window size in seconds for step computation (default: 8)
        march_start_time : Optional[datetime]
            March start time for timestamp alignment
        gps_crossing_times : Optional[dict]
            Dictionary mapping participant IDs to GPS crossing times
            Format: {'participant_id': {'start': datetime_string, 'end': datetime_string}}
        """
        self.data_dir = Path(data_dir)
        self.march_id = march_id
        self.window_size = window_size
        self.march_start_time = march_start_time
        self.gps_crossing_times = gps_crossing_times or {}

        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")

    def find_participant_files(self) -> dict[str, list[Path]]:
        """
        Find all participant accelerometer files

        Structure: /path/to/data/<participant>/<date>/acc.parquet

        Returns
        -------
        dict[str, list[Path]]
            Dictionary mapping participant IDs to list of acc.parquet file paths
        """
        participants = {}

        # Look for folders with structure: participant/date/acc.parquet
        for participant_dir in self.data_dir.iterdir():
            if not participant_dir.is_dir():
                continue

            participant_id = participant_dir.name
            acc_files = []

            # Look for date subdirectories
            for date_dir in participant_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                acc_file = date_dir / "acc.parquet"
                if acc_file.exists():
                    acc_files.append(acc_file)
                    logger.info(f"Found accelerometer data: {participant_id}/{date_dir.name}")

            if acc_files:
                participants[participant_id] = sorted(acc_files)  # Sort by path (date)

        if not participants:
            logger.warning(f"No accelerometer files found in {self.data_dir}")
        else:
            total_files = sum(len(files) for files in participants.values())
            logger.info(f"Found {len(participants)} participants with {total_files} total accelerometer files")

        return participants

    def process_participant(self, participant_id: str, acc_file: Path) -> Optional[pd.DataFrame]:
        """
        Process accelerometer data for a single participant

        Parameters
        ----------
        participant_id : str
            Participant identifier
        acc_file : Path
            Path to acc.parquet file

        Returns
        -------
        Optional[pd.DataFrame]
            DataFrame with columns: time, sps (steps per second), steps (cumulative)
            Returns None if processing fails
        """
        try:
            logger.info(f"Processing {participant_id}...")

            # Read accelerometer data
            df_acc = pd.read_parquet(acc_file)

            # Check required columns
            required_cols = ['X', 'Y', 'Z']
            if not all(col in df_acc.columns for col in required_cols):
                logger.error(f"Missing required columns in {acc_file}. Required: {required_cols}")
                return None

            # We need advance the index by 1 hour so that it matches watch data
            df_acc.index += pd.Timedelta(hours=1)

            # Use index as timestamp if no timestamp column
            if 'timestamp' not in df_acc.columns:
                df_acc = df_acc.reset_index()

            # IMPORTANT: Trim data using GPS crossing times FIRST (if available)
            if participant_id in self.gps_crossing_times:
                crossing_times = self.gps_crossing_times[participant_id]
                original_len = len(df_acc)

                # Parse start time if available
                if 'start' in crossing_times:
                    start_time = pd.to_datetime(crossing_times['start'])
                    df_acc = df_acc[df_acc['Time'] >= start_time]
                    logger.info(f"{participant_id}: Trimmed to GPS start time {start_time}")

                # Parse end time if available
                if 'end' in crossing_times:
                    end_time = pd.to_datetime(crossing_times['end'])
                    df_acc = df_acc[df_acc['Time'] <= end_time]
                    logger.info(f"{participant_id}: Trimmed to GPS end time {end_time}")

                trimmed_len = len(df_acc)
                if trimmed_len < original_len:
                    logger.info(
                        f"{participant_id}: GPS trimming removed {original_len - trimmed_len} rows "
                        f"({original_len} -> {trimmed_len})"
                    )

                if df_acc.empty:
                    logger.warning(f"No data after GPS trimming for {participant_id}")
                    return None

            # Remove unnecessary rows if march_start_time is specified (fallback if no GPS trimming)
            elif self.march_start_time is not None:
                df_acc = df_acc[df_acc['Time'] >= self.march_start_time]
                if df_acc.empty:
                    logger.warning(f"No data after march start time for {participant_id}")
                    return None

            # Calculate steps
            df_steps, interval_size = calculate_steps(df_acc, interval_size=self.window_size)

            if df_steps.empty:
                logger.warning(f"No steps calculated for {participant_id}")
                return None

            # Calculate cumulative steps
            df_steps['cumulative_steps'] = (df_steps['sps'] * interval_size).cumsum()

            # Add participant ID
            df_steps['participant_id'] = participant_id

            logger.info(f"Successfully processed {participant_id}: {int(df_steps['cumulative_steps'].iloc[-1])} total steps")

            return df_steps

        except Exception as e:
            logger.error(f"Error processing {participant_id}: {e}")
            return None

    def process_all_participants(self) -> list[pd.DataFrame]:
        """
        Process all participants

        Returns
        -------
        list[pd.DataFrame]
            List of DataFrames with step data for each participant
        """
        participant_files = self.find_participant_files()

        if not participant_files:
            logger.error("No participant files found to process")
            return []

        results = []
        for participant_id, acc_files in participant_files.items():
            # Process all acc.parquet files for this participant and combine
            participant_dfs = []

            for acc_file in acc_files:
                logger.info(f"Processing {participant_id} - {acc_file.parent.name}")
                df_steps = self.process_participant(participant_id, acc_file)
                if df_steps is not None:
                    participant_dfs.append(df_steps)

            # Combine all date data for this participant
            if participant_dfs:
                if len(participant_dfs) > 1:
                    logger.info(f"Combining {len(participant_dfs)} date files for {participant_id}")
                    combined_df = pd.concat(participant_dfs, ignore_index=True)
                    # Sort by timestamp and recalculate cumulative steps
                    combined_df = combined_df.sort_values('time').reset_index(drop=True)
                    combined_df['cumulative_steps'] = (combined_df['sps'] * self.window_size).cumsum()
                    results.append(combined_df)
                else:
                    results.append(participant_dfs[0])

        logger.info(f"Successfully processed {len(results)}/{len(participant_files)} participants")
        return results

    def save_to_csv(self, results: list[pd.DataFrame], output_dir: Path):
        """
        Save processed step data to CSV files

        Parameters
        ----------
        results : list[pd.DataFrame]
            List of processed step data DataFrames
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

        for df_steps in results:
            participant_id = df_steps['participant_id'].iloc[0]

            # Prepare data for output
            df_output = pd.DataFrame({
                'march_id': self.march_id,
                'user_id': participant_id,
                'timestamp': df_steps['time'],
                'steps_per_second': df_steps['sps'],
                'cumulative_steps': df_steps['cumulative_steps'],
                'sample': df_steps['sample'],
                'window_size_seconds': self.window_size
            })

            # Calculate timestamp_minutes if march_start_time is provided
            if self.march_start_time is not None:
                df_output['timestamp_minutes'] = (
                    pd.to_datetime(df_output['timestamp']) - self.march_start_time
                ).dt.total_seconds() / 60
            else:
                # Use relative time from first timestamp
                first_timestamp = pd.to_datetime(df_output['timestamp'].iloc[0])
                df_output['timestamp_minutes'] = (
                    pd.to_datetime(df_output['timestamp']) - first_timestamp
                ).dt.total_seconds() / 60

            all_data.append(df_output)

        # Concatenate all results
        combined_df = pd.concat(all_data, ignore_index=True)

        # Save step data
        output_file = output_dir / 'march_step_data.csv'
        combined_df.to_csv(output_file, index=False)
        logger.info(f"Saved step data to {output_file}")

        # Save summary statistics
        summary_data = []
        for df_steps in results:
            participant_id = df_steps['participant_id'].iloc[0]
            total_steps = int(df_steps['cumulative_steps'].iloc[-1])
            avg_sps = df_steps['sps'][df_steps['sps'] > 0].mean()

            summary_data.append({
                'march_id': self.march_id,
                'user_id': participant_id,
                'total_steps': total_steps,
                'avg_steps_per_second': round(avg_sps, 2) if not pd.isna(avg_sps) else 0,
                'window_size_seconds': self.window_size
            })

        summary_df = pd.DataFrame(summary_data)
        summary_file = output_dir / 'march_step_summary.csv'
        summary_df.to_csv(summary_file, index=False)
        logger.info(f"Saved step summary to {summary_file}")



def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description="Process accelerometer data to compute steps for march participants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process accelerometer data
  python process_step_data.py --data-dir /path/to/participants --march-id 1 --output ./output

  # Use custom window size
  python process_step_data.py --data-dir /path/to/participants --march-id 1 --window-size 10 --output ./output

  # With march start time for timestamp alignment
  python process_step_data.py --data-dir /path/to/participants --march-id 1 --march-start-time 2025-03-15T08:00:00 --output ./output
        """
    )

    parser.add_argument(
        '--data-dir',
        required=True,
        help='Root directory containing participant folders with acc.parquet files'
    )

    parser.add_argument(
        '--march-id',
        type=int,
        required=True,
        help='March event ID'
    )

    parser.add_argument(
        '--window-size',
        type=int,
        default=8,
        help='Window size in seconds for step computation (default: 8)'
    )

    parser.add_argument(
        '--march-start-time',
        help='March start time (ISO format: YYYY-MM-DDTHH:MM:SS) for timestamp alignment'
    )

    parser.add_argument(
        '--gps-trim-file',
        help='JSON file with GPS crossing times (output from process_watch_data.py)'
    )

    parser.add_argument(
        '--output',
        default='./data/output',
        help='Output directory for CSV files (default: ./data/output)'
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
            with open(args.gps_trim_file, 'r') as f:
                gps_crossing_times = json.load(f)
            logger.info(f"Loaded GPS crossing times for {len(gps_crossing_times)} participants from {args.gps_trim_file}")
        except FileNotFoundError:
            logger.error(f"GPS trim file not found: {args.gps_trim_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in GPS trim file: {e}")
            sys.exit(1)

    try:
        # Create processor
        processor = AccelerometerStepProcessor(
            data_dir=args.data_dir,
            march_id=args.march_id,
            window_size=args.window_size,
            march_start_time=march_start_time,
            gps_crossing_times=gps_crossing_times
        )

        # Process all participants
        logger.info(f"Starting processing with window size: {args.window_size} seconds")
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


if __name__ == '__main__':
    main()
