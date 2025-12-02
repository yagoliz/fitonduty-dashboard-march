# Management Scripts

This directory contains management and utility scripts for the FitonDuty March Dashboard.

## Directory Structure

```
scripts/
├── participants/       # User and participant management
├── events/            # March event management
└── data/              # Data processing wrappers
```

## Participant Management (`participants/`)

Scripts for managing user accounts and participants.

### `add_participants.py`
Add new participants to the database from a seed configuration file.

```bash
python scripts/participants/add_participants.py \
  --seed-file config/seed-data/march_2025_seed.yml
```

### `generate_march_seed.py`
Generate seed configuration files for march participants.

```bash
# From CSV file
python scripts/participants/generate_march_seed.py \
  --csv participants.csv march_2025

# Interactive mode
python scripts/participants/generate_march_seed.py \
  --interactive march_2025
```

## Event Management (`events/`)

Scripts for managing march events.

### `manage_march_events.py`
Create and manage march events.

```bash
# Create march event (interactive)
python scripts/events/manage_march_events.py create --interactive

# Create march event (CLI)
python scripts/events/manage_march_events.py create \
  --name "Training March Alpha" \
  --date 2025-03-15 \
  --distance 8.2

# List all march events
python scripts/events/manage_march_events.py list

# Update march status
python scripts/events/manage_march_events.py update-status \
  --march-id 1 --status completed
```

## Data Processing (`data/`)

Backward-compatible wrappers for data processing scripts. The actual implementations
are in `src/processing/`.

### Available Scripts

- `process_temp_data.py` - Process temperature data
- `process_step_data.py` - Process step/accelerometer data
- `process_watch_data.py` - Process watch data (HR, GPS, steps)
- `load_march_data.py` - Load processed data into database
- `merge_march_data.py` - Merge march data from multiple sources

### New CLI Commands

Prefer using the new CLI commands (available after `uv pip install -e .`):

```bash
fitonduty-process-temp --data-dir /path --march-id 1
fitonduty-process-steps --data-dir /path --march-id 1
fitonduty-process-watch --data-dir /path --march-id 1
fitonduty-load-data --data-dir /path --march-id 1
fitonduty-merge-data --input-dir /path
```

## Configuration

Environment variables are managed in `config/environments/`:

- `.env.development` - Development environment
- `.env.production` - Production environment
- `.env.example` - Example configuration

The root `.env` is a symlink to `.env.development` by default.

## Database Setup

Database management scripts are in `src/database/management/`:

```bash
# Create database schema
python src/database/management/create_schema.py

# Seed database with test data
python src/database/management/seed_database.py
```

Or use backward-compatible wrappers:

```bash
python database/create_schema_wrapper.py
python database/seed_database_wrapper.py
```

## See Also

- **Processing Scripts**: See `src/processing/` for implementation details
- **Database Schema**: See `src/database/schema.sql`
- **Migration Guide**: See `MIGRATION_PLAN.md` for repository structure changes
