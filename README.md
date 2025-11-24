# FitonDuty March Dashboard

A post-event analysis dashboard for long march physiological monitoring, focusing on pace analysis and performance comparisons.

## Overview

This dashboard provides detailed analysis of physiological data collected during military/training marches. Unlike real-time monitoring, data becomes available after participants hand in their measurement devices and the data is processed.

## Key Features

- **Individual March Analysis**: Personal performance breakdown with pace estimation
- **Group Comparisons**: Rankings and comparative analysis across participants
- **Pace Calculator**: Speed estimation using movement algorithms (no GPS required)
- **Historical Tracking**: Performance progression over multiple marches
- **Heart Rate Analysis**: HR zones and effort scoring during marches

## Documentation

**Complete documentation is available in the [`docs/`](./docs/) directory.**

### Quick Links

- **[Complete March Workflow](./docs/README.md#common-workflows)** - Full workflow from setup to published results
- **[Database Setup](./docs/setup-database.md)** - Set up PostgreSQL database with Ansible
- **[Loading March Data](./docs/guide-loading-data.md)** - Process and load watch data
- **[Managing Participants](./docs/guide-participants.md)** - Add and manage participants
- **[Managing March Events](./docs/guide-march-events.md)** - Create and manage marches
- **[Troubleshooting](./docs/troubleshooting.md)** - Common issues and solutions

### Documentation Index

See [`docs/README.md`](./docs/README.md) for complete documentation index.

## Quick Start

### 1. Set Up Database

```bash
# Configure Ansible inventory and passwords
cd ansible
cp inventory/example.yml inventory/production.yml
# Edit inventory/production.yml with your server details

# Run Ansible playbook (creates database, no mock data)
ansible-playbook -i inventory/production.yml --ask-vault-pass playbooks/march_database.yml
```

See [Database Setup Guide](./docs/setup-database.md) for detailed instructions.

### 2. Add Participants

```bash
# Generate participant configuration
cat > participants.csv << EOF
participant_id,group
SM001,Squad Alpha
SM002,Squad Alpha
EOF

python scripts/generate_march_seed.py --csv participants.csv production

# Add to database
export DATABASE_URL="postgresql://user:password@host:5432/fitonduty_march"
python scripts/add_participants.py --seed-file config/seed-data/production_seed.yml
```

See [Managing Participants Guide](./docs/guide-participants.md) for details.

### 3. Create March Event

```bash
python scripts/manage_march_events.py create --interactive
```

See [Managing March Events Guide](./docs/guide-march-events.md) for details.

### 4. Load March Data

After march completion:

```bash
# Process watch exports
python scripts/process_watch_data.py \
  --data-dir ./watch_exports \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output

# Load to database
python scripts/load_march_data.py \
  --data-dir ./output \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2

# Publish results
python scripts/manage_march_events.py update-status --march-id 1 --status published
```

See [Loading March Data Guide](./docs/guide-loading-data.md) for complete workflow.

## Architecture

- **Database**: PostgreSQL with custom march schema
- **Backend**: Python 3.12+, Dash (Flask-based)
- **Frontend**: Dash Bootstrap Components (LUX theme)
- **Authentication**: Flask-Login with role-based access
- **Deployment**: Docker, Gunicorn, Ansible

See [Architecture Overview](./docs/architecture.md) for detailed design.

## Development

### Local Setup

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e .

# Set up local database
python database/create_schema.py

# Run development server
python app.py
```

Visit http://localhost:8050

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## Project Structure

```
fitonduty-dashboard-march/
├── docs/                    # Complete documentation
├── ansible/                 # Deployment automation
├── scripts/                 # Database management scripts
│   ├── process_watch_data.py
│   ├── load_march_data.py
│   ├── add_participants.py
│   └── manage_march_events.py
├── database/                # Database schema and setup
│   ├── schema.sql
│   ├── create_schema.py
│   └── seed_database.py
├── app.py                   # Main application
├── components/              # UI components
├── callbacks/               # Dash callbacks
└── utils/                   # Utilities and helpers
```

## Getting Help

- **Documentation**: See [`docs/`](./docs/) directory
- **Troubleshooting**: See [Troubleshooting Guide](./docs/troubleshooting.md)
- **Issues**: Check existing issues or create a new one

## License

[Your license information]