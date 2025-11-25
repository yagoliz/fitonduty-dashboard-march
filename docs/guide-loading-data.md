# Loading March Data Guide

Complete guide for processing and loading real march data from watch exports into the database.

## Overview

After a march is completed and participants hand in their watches, you need to:
1. Export data from watches (CSV/GPX/TCX files)
2. Process the watch data
3. Load it into the database
4. Publish results

This guide walks through each step in detail.

## Prerequisites

- Database is set up and running
- Participants are added to the database
- March event has been created
- Watch data files collected from participants

## Step 1: Collect Watch Export Files

### Supported File Formats

- **CSV**: Heart rate, steps, cadence, speed data
- **GPX**: GPS tracks with position and elevation (optional but recommended)
- **TCX**: Training Center XML with heart rate zones (optional)

### File Naming Convention

Name files with participant identifiers:
```
SM001.CSV
SM001.GPX
SM002.CSV
SM002.GPX
SM003_1.CSV   # Multiple activities (watch stopped/restarted)
SM003_2.CSV
```

### Organize Files

```bash
mkdir -p march_data/march_alpha_2025_03_15
cd march_data/march_alpha_2025_03_15

# Copy watch export files here
# Files should be:
# - SM001.CSV, SM001.GPX
# - SM002.CSV, SM002.GPX
# - etc.
```

## Step 2: Process Watch Data

The `process_watch_data.py` script converts various watch export formats into standardized CSV files for database import.

### Basic Usage

```bash
python scripts/process_watch_data.py \
  --data-dir march_data/march_alpha_2025_03_15 \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output/march_alpha
```

### GPS-Based Trimming (Recommended)

If you know the start/end GPS coordinates of the march, you can trim all data to only include the actual march time:

```bash
python scripts/process_watch_data.py \
  --data-dir march_data/march_alpha_2025_03_15 \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --start-lat 1.234567 \
  --start-lon 103.654321 \
  --end-lat 1.345678 \
  --end-lon 103.765432 \
  --gps-tolerance 50 \
  --output ./output/march_alpha
```

**Benefits of GPS Trimming:**
- Removes data from before march started (e.g., waiting at start point)
- Removes data after march ended (e.g., resting at end point)
- Ensures all metrics are calculated only on actual march data
- Generates `gps_crossing_times.json` for use by step processing

### Parameters

- `--data-dir`: Directory containing watch export files
- `--march-id`: Database ID of the march event
- `--march-start-time`: March start time in ISO format (YYYY-MM-DDTHH:MM:SS)
- `--output`: Output directory for processed CSV files
- `--start-lat`: (Optional) Start point latitude for GPS trimming
- `--start-lon`: (Optional) Start point longitude for GPS trimming
- `--end-lat`: (Optional) End point latitude for GPS trimming
- `--end-lon`: (Optional) End point longitude for GPS trimming
- `--gps-tolerance`: (Optional) GPS tolerance in meters for detecting crossings (default: 50m)

### What It Does

The script:
1. **Detects file formats** - Handles different watch brands (Garmin, Suunto, Polar)
2. **Merges multiple activities** - If a participant has multiple files (watch stopped/restarted)
3. **Calculates metrics** - HR zones, speed from GPS or cadence, cumulative steps
4. **Generates CSVs** - Creates standardized CSV files for database import

### Output Files

The script generates:
- `march_health_metrics.csv` - Aggregate metrics per participant
- `march_hr_zones.csv` - Heart rate zone distributions
- `march_timeseries_data.csv` - Time-series physiological data
- `march_gps_positions.csv` - GPS tracks (if GPX files present)
- `gps_crossing_times.json` - GPS crossing times (if GPS trimming used, for step processing)

### Example Output

**Without GPS Trimming:**
```
Processing participant: SM001
  Loaded SM001.CSV: 5400 rows
  Loaded SM001.GPX: 1800 GPS points
  Parsed 5400 time-series records from SM001.CSV
  Calculated HR zones: moderate=45%, intense=35%, light=20%
  Generated 180 1-minute intervals for timeseries
  Successfully processed SM001 (150 min march, 1800 GPS points)

Processed 4 participants
Output saved to ./output/march_alpha
```

**With GPS Trimming:**
```
GPS start trimming point: 1.234567, 103.654321
GPS end trimming point: 1.345678, 103.765432
GPS trimming tolerance: 50.0m

Processing participant: SM001
  SM001: Finding GPS crossing times...
  SM001: Start crossing at 2025-03-15 08:15:23 (distance: 28.3m from target)
  SM001: End crossing at 2025-03-15 10:45:18 (distance: 35.7m from target)
  SM001: Trimming GPS data using GPS crossing times
  Trimmed GPS data: 1800 -> 1650 rows (150 rows removed)
  SM001: Trimming CSV data using GPS crossing times
  Trimmed CSV data: 5400 -> 4950 rows (450 rows removed)
  Successfully processed SM001

Processed 4 participants
Saved GPS crossing times for 4 participants to ./output/march_alpha/gps_crossing_times.json
Output saved to ./output/march_alpha
```

## Step 3: Review Processed Data

Before loading to database, verify the processed data:

```bash
# Check generated files
ls -lh ./output/march_alpha/
# Should show:
# march_health_metrics.csv
# march_hr_zones.csv
# march_timeseries_data.csv
# march_gps_positions.csv

# Inspect data
head -20 ./output/march_alpha/march_health_metrics.csv
```

### Verify Participant IDs

Check that participant IDs in CSVs match your database usernames or that you have a mapping:

```bash
# See what participant IDs were found
cut -d',' -f2 ./output/march_alpha/march_health_metrics.csv | sort -u
```

## Step 4: Load Data into Database

The `load_march_data.py` script loads the processed CSVs into the database.

### Basic Usage (Automatic Mapping)

If CSV participant IDs match database usernames:

```bash
export DATABASE_URL="postgresql://user:password@host:5432/fitonduty_march"

python scripts/load_march_data.py \
  --data-dir ./output/march_alpha \
  --march-id 1
```

### With Custom Mapping

If CSV has custom participant IDs (like SM001, SM002) that need to be mapped to database usernames:

```bash
python scripts/load_march_data.py \
  --data-dir ./output/march_alpha \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2,SM003:participant3,SM004:participant4
```

### Dry Run

Preview what will be loaded without making changes:

```bash
python scripts/load_march_data.py \
  --data-dir ./output/march_alpha \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2 \
  --dry-run
```

### What It Does

The script:
1. **Maps participant IDs** - Converts CSV IDs to database user IDs
2. **Loads health metrics** - Aggregate performance data
3. **Loads HR zones** - Heart rate zone distributions
4. **Loads timeseries data** - Time-series physiological data (batch inserts for performance)
5. **Loads GPS positions** - GPS tracks if available
6. **Registers participants** - Marks participants as completed for the march

### Example Output

```
Loading CSV files...
  Loaded march_health_metrics.csv: 4 rows
  Loaded march_hr_zones.csv: 4 rows
  Loaded march_timeseries_data.csv: 720 rows
  Loaded march_gps_positions.csv: 7200 rows

Mapping participant IDs to database user IDs...
  Mapped SM001 -> participant1 (user_id=2)
  Mapped SM002 -> participant2 (user_id=3)
  Mapped SM003 -> participant3 (user_id=4)
  Mapped SM004 -> participant4 (user_id=5)
  Mapped 4/4 rows to database user IDs

Proceed with loading data for march ID 1? (y/N): y

Loading march health metrics...
  Loaded 4 health metrics records

Loading march HR zones...
  Loaded 4 HR zones records

Loading march timeseries data...
  ... loaded 720 records

Loading march GPS positions...
  ... loaded 7200 records

Successfully loaded 7928 total records!

March 1 data has been updated.
You may want to update the march status to 'published' to make it visible.
```

## Step 5: Verify Data Load

Check that data was loaded correctly:

```bash
# Connect to database
psql "postgresql://user:password@host:5432/fitonduty_march"

# Check march participants
SELECT mp.march_id, u.username, mp.completed, mp.finish_time_minutes
FROM march_participants mp
JOIN users u ON mp.user_id = u.id
WHERE mp.march_id = 1;

# Check health metrics
SELECT u.username, mhm.avg_hr, mhm.max_hr, mhm.total_steps, mhm.march_duration_minutes
FROM march_health_metrics mhm
JOIN users u ON mhm.user_id = u.id
WHERE mhm.march_id = 1;

# Count timeseries data points
SELECT u.username, COUNT(*) as data_points
FROM march_timeseries_data mtd
JOIN users u ON mtd.user_id = u.id
WHERE mtd.march_id = 1
GROUP BY u.username;
```

## Step 6: Publish Results

Once data is verified, make it visible to participants:

```bash
python scripts/manage_march_events.py update-status \
  --march-id 1 \
  --status published
```

Status options:
- `planned` - March is scheduled but not conducted
- `completed` - March finished, data not yet loaded
- `processing` - Data is being processed (optional)
- `published` - Results visible to participants

## Troubleshooting

### Issue: "No CSV files found"

**Problem:** Script can't find watch data files

**Solution:**
```bash
# Check files are in directory
ls -la march_data/march_alpha_2025_03_15/

# Verify file extensions (should be .CSV or .csv)
ls *.CSV *.csv 2>/dev/null
```

### Issue: "Could not parse timestamp"

**Problem:** CSV has unexpected date/time format

**Solution:**
- Check CSV contains proper timestamps
- Verify watch export format is supported
- Try exporting from watch software again with different format

### Issue: "Participant ID not found for mapping"

**Problem:** CSV has participant IDs that don't match database usernames

**Solution:**
```bash
# List participant IDs in CSV
cut -d',' -f2 ./output/march_alpha/march_health_metrics.csv | sort -u

# List usernames in database
psql $DATABASE_URL -c "SELECT username FROM users WHERE role='participant'"

# Create mapping
python scripts/load_march_data.py \
  --data-dir ./output/march_alpha \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2
```

### Issue: "Duplicate key error"

**Problem:** Data already exists for this march

**Solution:**
The script replaces existing timeseries/GPS data. If you get duplicate errors for health metrics:
```sql
-- Delete existing data for march
DELETE FROM march_timeseries_data WHERE march_id = 1;
DELETE FROM march_gps_positions WHERE march_id = 1;
DELETE FROM march_hr_zones WHERE march_health_metric_id IN (
  SELECT id FROM march_health_metrics WHERE march_id = 1
);
DELETE FROM march_health_metrics WHERE march_id = 1;
DELETE FROM march_participants WHERE march_id = 1;

-- Then reload
python scripts/load_march_data.py --data-dir ./output/march_alpha --march-id 1
```

## Complete Example Workflow

```bash
# 1. Organize watch files
mkdir -p march_data/alpha_2025_03_15
cp /path/to/watch/exports/*.CSV march_data/alpha_2025_03_15/
cp /path/to/watch/exports/*.GPX march_data/alpha_2025_03_15/

# 2. Process watch data
python scripts/process_watch_data.py \
  --data-dir march_data/alpha_2025_03_15 \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output/alpha

# 3. Review output
ls -lh ./output/alpha/
head ./output/alpha/march_health_metrics.csv

# 4. Dry run to verify
python scripts/load_march_data.py \
  --data-dir ./output/alpha \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2,SM003:participant3 \
  --dry-run

# 5. Load to database
export DATABASE_URL="postgresql://fitonduty_march:password@server:5432/fitonduty_march"
python scripts/load_march_data.py \
  --data-dir ./output/alpha \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2,SM003:participant3

# 6. Verify in database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM march_timeseries_data WHERE march_id = 1"

# 7. Publish results
python scripts/manage_march_events.py update-status --march-id 1 --status published
```

## Next Steps

- **View Results:** Start dashboard with `python app.py` and login
- **Export Reports:** Use dashboard to export march analysis
- **Next March:** Repeat process for subsequent marches

## See Also

- [Managing March Events](./guide-march-events.md) - Create and manage marches
- [Managing Participants](./guide-participants.md) - Add participants
- [Scripts Reference](./reference-scripts.md) - Complete script documentation
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions