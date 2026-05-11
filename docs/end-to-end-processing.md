# FitonDuty March Data Processing

## Quick Start

The data processing pipeline is now **configuration-driven**. You create one config file per march, then simply pass the date when you want to process data.

### Run the pipeline:

```bash
./process_data.sh --march config/marches/my_march.sh --date 20260410
```

That's it! No more editing scripts, no more hunting through bash history. 
---

## Directory Structure

```
config/
├── environments/          # Database connection env files (.env.20260410)
├── marches/               # March configuration files (one per event):
│   ├── template.sh        # Copy this to create a new march config
│   ├── liestal.sh        # Liestal march (2026-04-10)
│   ├── bulach.sh         # Bülach march (2026-04-24)
│   └── emmen.sh          # Emmen march (2026-05-01)
└── seed-data/             # Participants CSV and seed YAML files

process_data.sh           # NEW: Main processing script
data_process.example.sh   # OLD: Manual script (deprecated)
```

---

## Setting Up a New March

### 1. Create a March Configuration

```bash
# Copy the template
cp config/marches/template.sh config/marches/my_new_event.sh

# Edit it with your march details
nano config/marches/my_new_event.sh
```

Fill in at minimum:
- `MARCH_ID` — from the database (`march_events` table)
- `START_LAT`, `START_LON` — GPS start coordinates
- `END_LAT`, `END_LON` — GPS end coordinates

You can also add:
- `MARCH_NAME` — human-readable name (for logs)
- `MARCH_CITY` — city/location name
- `GPS_TOLERANCE` — default is 150 meters
- `MIN_GPS_CROSSING_DELAY` — default is 10000 ms

### 2. Process Data

```bash
./process_data.sh --march config/marches/my_new_event.sh --date 20260410
```

The script will:
1. Load the march configuration
2. Derive paths from the date you provide
3. Run watch → fill → step → temp → merge → load pipeline
4. Show a summary and confirmation before database load

---

## Reprocessing the Same March

The whole point! You use the **same config file** with different dates:

```bash
# Day 1
./process_data.sh --march config/marches/liestal.sh --date 20260410

# Day 2 (same march, different gathering)
./process_data.sh --march config/marches/liestal.sh --date 20260411

# Reprocess Day 1 with new data
./process_data.sh --march config/marches/liestal.sh --date 20260410
```

---

## Command-line Options

```bash
./process_data.sh --march <config> --date <YYYYMMDD> [options]
```

| Option | Description |
|--------|-------------|
| `--march <path>` | **Required.** Path to march configuration file |
| `--date <YYYYMMDD>` | **Required.** Processing date (e.g., `20260410`) |
| `--skip-process` | Skip all processing, only run merge and load |
| `--skip-load` | Skip database loading step |
| `--env-file <path>` | Override environment file for DB connection |
| `--participants <path>` | Override participants CSV file |
| `-h`, `--help` | Show help message |

### Examples:

```bash
# Reprocess without touching the database
./process_data.sh --march config/marches/liestal.sh --date 20260410 --skip-load

# Only load existing output (skip all processing)
./process_data.sh --march config/marches/liestal.sh --date 20260410 --skip-process

# Use a custom env file
./process_data.sh --march config/marches/liestal.sh --date 20260410 --env-file .env.my_custom

# Use a different participants file
./process_data.sh --march config/marches/liestal.sh --date 20260410 --participants /mnt/data/backup_participants.csv
```

---

## Existing March Configurations

The following march configs are available (fill in the missing values):

| File | Event | Date | Status |
|------|-------|------|--------|
| `config/marches/liestal.sh` | Liestal March | 2026-04-10 | Needs MARCH_ID and coordinates |
| `config/marches/bulach.sh` | Bülach March | 2026-04-24 | Needs MARCH_ID and coordinates |
| `config/marches/emmen.sh` | Emmen March | 2026-05-01 | Needs MARCH_ID and coordinates |

### To complete a config:

1. Find the `MARCH_ID` in the database:
   ```bash
   uv run scripts/events/manage_march_events.py list
   ```

2. Find the GPS coordinates from the route or previous run.

3. Edit the config file:
   ```bash
   nano config/marches/liestal.sh
   ```

---

## How Path Derivation Works

Given `DATE=20260410` and `MARCH_CITY=Liestal`:

| Variable | Derived Path |
|----------|-------------|
| `DATE_YYYY_MM_DD` | `2026_04_10` |
| `DATA_ROOT` | `/data` |
| `MARCH_DATA_DIR` | `/data/20260410_march` |
| `WATCH_DATA_DIR` | `/data/20260410_march/station_march_2026_04_10/watch_data/` |
| `STATION_DIR` | `/data/20260410_march/admin_march_2026_04_10/station_march_2026_04_10/` |
| `OUTPUT_DIR` | `./.output/20260410` |
| `PARTICIPANTS_CSV` | `config/seed-data/participants_20260410.csv` |
| `ENV_FILE` | `.env.20260410` or `config/environments/.env.20260410` |

You can override any of these in the march config file if your directory structure differs.

---

## Troubleshooting

### "Watch data directory not found"
- Make sure you've synced/loaded the watch data into the expected directory
- Check `DATA_ROOT` in the config file
- Verify the date format is `YYYYMMDD`

### "Participants CSV not found"
- The script expects `config/seed-data/participants_YYYYMMDD.csv`
- Generate it from the march seed data:
  ```bash
  # Or create it manually from the YML
  ```

### "Environment file not found"
- Make sure `.env.YYYYMMDD` exists or is in `config/environments/`
- Or use `--env-file` to specify a custom path
- Or use `--skip-load` if you only want to process, not load

### "Error: MARCH_ID must be set"
- You forgot to fill in `MARCH_ID` in the config file
- Run `manage_march_events.py list` to find it

---

## Migration from Old Workflow

| Old Way | New Way |
|---------|---------|
| Edit `process_data.example.sh` every run | Create `config/marches/my_march.sh` once |
| Hardcode paths and coordinates in script | Coordinates live in reusable config |
| Bash history archaeology | `./process_data.sh --march config/marches/... --date <date>` |
| Copy and modify script for each march | One runner script, many configs |

The old `process_data.example.sh` is preserved for reference but should not be used for regular processing.

---

## Adding a New March

1. Run the march event creation script:
   ```bash
   uv run scripts/events/manage_march_events.py create --interactive
   ```

2. Note the MARCH_ID

3. Get the GPS coordinates from the route

4. Create the config:
   ```bash
   cp config/marches/template.sh config/marches/<city>.sh
   # Edit and fill in values
   ```

5. Generate participants CSV and seed data

6. Create the `.env.<date>` file for database loading

7. Process:
   ```bash
   ./process_data.sh --march config/marches/<city>.sh --date <YYYYMMDD>
   ```

---