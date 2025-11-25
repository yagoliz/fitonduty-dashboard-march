#!/bin/bash

# Process watch data
# uv run scripts/process_watch_data.py \
#     --data-dir /Users/ygglc/Work/Projects/FitonDuty/Data/2025/March/Watch \
#     --march-id 1 \
#     --start-lat 47.151100006328655 \
#     --start-lon 8.75823979978386 \
#     --end-lat 47.35666186747409 \
#     --end-lon 8.334098604173358 \
#     --gps-tolerance 50 \
#     --output ./.output/20251119

# Process step data
# uv run scripts/process_step_data.py \
#   --data-dir /Users/ygglc/Work/Projects/FitonDuty/Data/2025/March/Logger \
#   --march-id 1 \
#   --gps-trim-file ./.output/20251119/gps_crossing_times.json \
#   --output ./.output/20251119

# Merging
# uv run scripts/merge_march_data.py \
#     --watch-data ./.output/20251119/march_timeseries_data.csv \
#     --step-data ./.output/20251119/march_step_data.csv \
#     --watch-summary ./.output/20251119/march_health_metrics.csv \
#     --step-summary ./.output/20251119/march_step_summary.csv \
#     --output ./.output

# Loading
uv run scripts/load_march_data.py --data-dir .output/ --march-id 1 