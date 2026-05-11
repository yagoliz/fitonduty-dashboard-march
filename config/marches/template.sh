#!/bin/bash
# =============================================================================
# March Processing Configuration Template
# =============================================================================
# Copy this file when creating a new march configuration:
#   cp template.sh my_new_march.sh
#
# Then fill in the specific values for your march.
# =============================================================================

# --- Required: March Identity -----------------------------------------------
# The database ID for this march. Get this from the march_events table or
# from the event organizer.
MARCH_ID=""

# Human-readable name for this march (used in logging and documentation)
MARCH_NAME=""

# City or location name (used for participants CSV lookup and documentation)
MARCH_CITY=""

# --- Required: GPS Coordinates ----------------------------------------------
# Starting point coordinates (latitude and longitude)
# Get these from the march route planning or GPS device
START_LAT=""
START_LON=""

# Ending point coordinates (latitude and longitude)
END_LAT=""
END_LON=""

# --- Optional: Processing Parameters -----------------------------------------
# GPS tolerance in meters for detecting crossing events
# Default: 150
# GPS_TOLERANCE=150

# Minimum delay in milliseconds between GPS crossing events
# Default: 10000
# MIN_GPS_CROSSING_DELAY=10000

# --- Optional: Paths --------------------------------------------------------
# Root directory where march data is stored
# Default: /data
# DATA_ROOT="/data"

# Root directory for processing output
# Default: ./.output
# OUTPUT_ROOT="./.output"

# Path to participants CSV file
# If not specified, uses: config/seed-data/participants_{YYYYMMDD}.csv
# PARTICIPANTS_CSV=""

# Custom data directory for watch data
# If not specified, derived from DATA_ROOT and date
# WATCH_DATA_DIR=""

# Custom station directory
# If not specified, derived from DATA_ROOT and date
# STATION_DIR=""

# Custom environment file for database loading
# If not specified, uses: .env.{YYYYMMDD} or config/environments/.env.{YYYYMMDD}
# ENV_FILE=""
