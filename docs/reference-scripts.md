# Scripts Reference

Complete reference for all command-line scripts in the FitonDuty March Dashboard.

## Overview

All scripts are located in the `scripts/` directory and handle database management, data processing, and march operations.

## Quick Reference

| Script | Purpose |
|--------|---------|
| `generate_march_seed.py` | Generate participant seed configurations |
| `add_participants.py` | Add participants to database |
| `manage_march_events.py` | Create and manage march events |
| `process_watch_data.py` | Process watch export files to CSV |
| `load_march_data.py` | Load processed CSV data to database |

## generate_march_seed.py

Generate seed data configuration files with participants and auto-generated secure passwords.

### Usage

```bash
# From CSV file
python scripts/generate_march_seed.py --csv participants.csv campaign_name

# Interactive mode
python scripts/generate_march_seed.py --interactive campaign_name

# With custom output path
python scripts/generate_march_seed.py --csv participants.csv campaign_name \
  --output config/seed-data/custom.yml

# Dry run
python scripts/generate_march_seed.py --csv participants.csv campaign_name --dry-run
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `campaign_name` | Yes | Name for the campaign (used in output filename) |
| `--csv FILE` | No | CSV file with participant data |
| `--interactive` | No | Interactive mode (prompts for input) |
| `--output FILE` | No | Custom output file path |
| `--dry-run` | No | Show what would be generated without saving |

### CSV Format

```csv
participant_id,group
SM001,Squad Alpha
SM002,Squad Alpha
SM003,Squad Bravo
```

### Output

Creates `config/seed-data/{campaign_name}_seed.yml` with:
- Auto-generated secure passwords
- Group definitions
- Admin user account
- Participant assignments

### Example

```bash
# Create participant CSV
cat > participants.csv << EOF
participant_id,group
A001,Squad Alpha
A002,Squad Alpha
B001,Squad Bravo
EOF

# Generate seed file
python scripts/generate_march_seed.py --csv participants.csv campaign_2025

# Output: config/seed-data/campaign_2025_seed.yml
```

## add_participants.py

Add participants from a seed YAML file to database. Only adds new participants, skipping existing ones.

### Usage

```bash
# Add participants from seed file
python scripts/add_participants.py --seed-file config/seed-data/participants.yml

# With custom database URL
python scripts/add_participants.py \
  --seed-file config/seed-data/participants.yml \
  --db-url postgresql://user:password@host:5432/dbname

# Dry run
python scripts/add_participants.py \
  --seed-file config/seed-data/participants.yml \
  --dry-run
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--seed-file FILE` | Yes | Path to seed YAML file |
| `--db-url URL` | No | Database connection URL (or use DATABASE_URL env var) |
| `--dry-run` | No | Preview changes without making them |

### Features

- Safely adds only new participants (preserves existing data)
- Automatically creates missing groups
- Adds admin users if needed
- Uses passwords from seed file
- Confirmation prompt before making changes

### Example

```bash
export DATABASE_URL="postgresql://fitonduty_march:password@host:5432/fitonduty_march"

# Dry run first
python scripts/add_participants.py \
  --seed-file config/seed-data/campaign_2025_seed.yml \
  --dry-run

# Add to database
python scripts/add_participants.py \
  --seed-file config/seed-data/campaign_2025_seed.yml
```

## manage_march_events.py

Create and manage march events in the database.

### Commands

- `create` - Create new march event
- `list` - List all march events
- `update-status` - Update march status
- `add-participants` - Add participants to march

### Create March Event

```bash
# Interactive mode
python scripts/manage_march_events.py create --interactive

# Command line
python scripts/manage_march_events.py create \
  --name "Training March Alpha" \
  --date 2025-03-15 \
  --distance 8.2 \
  --duration 2.5 \
  --group "Squad Alpha" \
  --route "Forest trail with moderate elevation" \
  --status planned
```

#### Create Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--name TEXT` | Yes | March event name |
| `--date DATE` | Yes | March date (YYYY-MM-DD) |
| `--distance FLOAT` | Yes | Distance in kilometers |
| `--duration FLOAT` | Yes | Duration in hours |
| `--group TEXT` | Yes | Group name |
| `--route TEXT` | No | Route description |
| `--status TEXT` | No | Status (planned/completed/processing/published), default: planned |
| `--db-url URL` | No | Database connection URL |

### List March Events

```bash
python scripts/manage_march_events.py list [--db-url URL]
```

### Update March Status

```bash
python scripts/manage_march_events.py update-status \
  --march-id 1 \
  --status completed \
  [--db-url URL]
```

#### Status Values

- `planned` - March is scheduled but not yet conducted
- `completed` - March has been completed
- `processing` - Data is being processed
- `published` - Results are published and visible to participants

### Add Participants to March

```bash
# Add all participants from march's group
python scripts/manage_march_events.py add-participants --march-id 1

# Add participants from specific group
python scripts/manage_march_events.py add-participants \
  --march-id 1 \
  --group "Squad Bravo"
```

### Example

```bash
export DATABASE_URL="postgresql://fitonduty_march:password@host:5432/fitonduty_march"

# Create march
python scripts/manage_march_events.py create --interactive

# Add participants
python scripts/manage_march_events.py add-participants --march-id 1

# List marches
python scripts/manage_march_events.py list

# Update status
python scripts/manage_march_events.py update-status --march-id 1 --status completed
```

## process_watch_data.py

Process watch export files (CSV/GPX/TCX) from Garmin, Suunto, Polar, etc. and generate CSV files for database import.

### Usage

```bash
python scripts/process_watch_data.py \
  --data-dir /path/to/watch/exports \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--data-dir DIR` | Yes | Directory containing watch export files |
| `--march-id INT` | Yes | March event ID |
| `--march-start-time TIME` | Yes | March start time (ISO format: YYYY-MM-DDTHH:MM:SS) |
| `--output DIR` | Yes | Output directory for CSV files |

### Input Files

Supported formats:
- **CSV**: Heart rate, steps, cadence, speed data
- **GPX**: GPS tracks with position and elevation
- **TCX**: Training Center XML with heart rate zones

File naming:
- `SM001.CSV`, `SM001.GPX` - Participant ID with file extension
- `SM003_1.CSV`, `SM003_2.CSV` - Multiple activities (watch stopped/restarted)

### Output Files

Generates:
- `march_health_metrics.csv` - Aggregate metrics per participant
- `march_hr_zones.csv` - Heart rate zone distributions
- `march_timeseries_data.csv` - Time-series physiological data
- `march_gps_positions.csv` - GPS tracks (if GPX files present)

### Features

- Handles multiple file formats (summary-only, time-series, combined)
- Merges multiple activities per participant
- Calculates speed from GPS or cadence
- Generates HR zones and movement speed distributions

### Example

```bash
# Organize files
mkdir -p march_data/alpha_2025_03_15
cp /path/to/exports/*.CSV march_data/alpha_2025_03_15/
cp /path/to/exports/*.GPX march_data/alpha_2025_03_15/

# Process
python scripts/process_watch_data.py \
  --data-dir march_data/alpha_2025_03_15 \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output/alpha
```

## load_march_data.py

Load processed watch data CSVs (generated by `process_watch_data.py`) into the database.

### Usage

```bash
# Load data with automatic participant mapping
python scripts/load_march_data.py \
  --data-dir ./output \
  --march-id 1

# With custom participant ID mapping
python scripts/load_march_data.py \
  --data-dir ./output \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2

# With custom database URL
python scripts/load_march_data.py \
  --data-dir ./output \
  --march-id 1 \
  --db-url postgresql://user:password@host:5432/dbname

# Dry run
python scripts/load_march_data.py \
  --data-dir ./output \
  --march-id 1 \
  --dry-run
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--data-dir DIR` | Yes | Directory containing CSV files from process_watch_data.py |
| `--march-id INT` | Yes | March event ID to load data for |
| `--mapping MAP` | No | Participant ID mapping (ID1:username1,ID2:username2) |
| `--db-url URL` | No | Database connection URL (or use DATABASE_URL env var) |
| `--dry-run` | No | Show what would be loaded without making changes |

### Participant ID Mapping

**Automatic:** If CSV `user_id` matches database `username`
- CSV has `participant1` → Database has user `participant1`
- No mapping needed

**Custom:** Use `--mapping` flag to map watch IDs to usernames
- CSV has `SM001` → Map to database user `participant1`
- `--mapping SM001:participant1,SM002:participant2`

### Features

- Maps participant IDs from CSV files to database user IDs
- Handles missing columns gracefully
- Updates existing data (replaces timeseries/GPS, updates metrics)
- Batch inserts for performance with large datasets
- Automatic participant registration for the march
- Confirmation prompt before making changes

### Example

```bash
export DATABASE_URL="postgresql://fitonduty_march:password@host:5432/fitonduty_march"

# Dry run first
python scripts/load_march_data.py \
  --data-dir ./output/alpha \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2 \
  --dry-run

# Load to database
python scripts/load_march_data.py \
  --data-dir ./output/alpha \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2

# Verify
psql $DATABASE_URL -c "SELECT COUNT(*) FROM march_timeseries_data WHERE march_id = 1"
```

## Environment Variables

All scripts support the `DATABASE_URL` environment variable:

```bash
# Set database connection
export DATABASE_URL="postgresql://user:password@host:port/database"

# Verify
echo $DATABASE_URL

# Use in scripts (no need for --db-url flag)
python scripts/add_participants.py --seed-file config/seed-data/participants.yml
```

## Database URL Format

```
postgresql://[user]:[password]@[host]:[port]/[database]
```

Examples:
```bash
# Local development
postgresql://postgres:password@localhost:5432/fitonduty_march

# Production
postgresql://fitonduty_march:SecurePass123@db.example.com:5432/fitonduty_march
```

## Complete Workflow Example

```bash
# Set database connection
export DATABASE_URL="postgresql://fitonduty_march:password@server:5432/fitonduty_march"

# 1. Generate participant configuration
cat > participants.csv << EOF
participant_id,group
SM001,Squad Alpha
SM002,Squad Alpha
SM003,Squad Bravo
EOF

python scripts/generate_march_seed.py --csv participants.csv campaign_2025

# 2. Add participants to database
python scripts/add_participants.py --seed-file config/seed-data/campaign_2025_seed.yml

# 3. Create march event
python scripts/manage_march_events.py create --interactive

# 4. Add participants to march
python scripts/manage_march_events.py add-participants --march-id 1

# 5. After march: Process watch data
python scripts/process_watch_data.py \
  --data-dir march_data/alpha_2025_03_15 \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output/alpha

# 6. Load processed data
python scripts/load_march_data.py \
  --data-dir ./output/alpha \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2,SM003:participant3

# 7. Publish results
python scripts/manage_march_events.py update-status --march-id 1 --status published
```

## Common Patterns

### Check Before Running

```bash
# Dry run to preview
python scripts/add_participants.py --seed-file config/seed-data/participants.yml --dry-run
python scripts/load_march_data.py --data-dir ./output --march-id 1 --dry-run

# List before updating
python scripts/manage_march_events.py list
```

### Verify After Running

```bash
# Check participants
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users WHERE role='participant'"

# Check march events
psql $DATABASE_URL -c "SELECT id, name, status FROM march_events"

# Check loaded data
psql $DATABASE_URL << EOF
SELECT
  'Health Metrics' as table_name,
  COUNT(*) as records
FROM march_health_metrics WHERE march_id = 1
UNION ALL
SELECT 'Timeseries', COUNT(*) FROM march_timeseries_data WHERE march_id = 1;
EOF
```

### Batch Operations

```bash
# Add multiple seed files
for file in config/seed-data/squad_*.yml; do
  python scripts/add_participants.py --seed-file "$file"
done

# Process multiple marches
for dir in march_data/*/; do
  march_name=$(basename "$dir")
  python scripts/process_watch_data.py \
    --data-dir "$dir" \
    --march-id $march_id \
    --march-start-time $start_time \
    --output "./output/$march_name"
done
```

## Error Handling

All scripts include:
- Input validation
- Database connection testing
- Confirmation prompts
- Detailed error messages
- Graceful failure handling

Example error output:
```
Error: Database connection failed
  Connection: postgresql://fitonduty_march@localhost:5432/fitonduty_march
  Details: FATAL: database "fitonduty_march" does not exist

Suggestions:
  1. Create database: psql -U postgres -c "CREATE DATABASE fitonduty_march;"
  2. Check DATABASE_URL environment variable
  3. Verify PostgreSQL is running: sudo systemctl status postgresql
```

## Debugging

### Enable Verbose Output

```bash
# Python verbose mode
python -v scripts/load_march_data.py --data-dir ./output --march-id 1

# Check what script is doing
python -c "import sys; print(sys.path)"
```

### Inspect Generated Files

```bash
# Check seed file
cat config/seed-data/campaign_2025_seed.yml

# Check processed CSVs
head -20 ./output/march_health_metrics.csv
wc -l ./output/march_timeseries_data.csv
```

### Test Database Connection

```bash
# Test with psql
psql $DATABASE_URL -c "SELECT 1"

# Test with Python
python -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('Connection successful!')
"
```

## See Also

- [Managing Participants Guide](./guide-participants.md) - Detailed participant management
- [Managing March Events Guide](./guide-march-events.md) - Detailed march event management
- [Loading March Data Guide](./guide-loading-data.md) - Complete data loading workflow
- [Troubleshooting Guide](./troubleshooting.md) - Common issues and solutions