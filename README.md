# FitonDuty March Dashboard

> A post-event analysis dashboard for long march physiological monitoring, focusing on pace analysis and performance comparisons.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Dash](https://img.shields.io/badge/Dash-3.2+-green.svg)](https://dash.plotly.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

This dashboard provides detailed analysis of physiological data collected during military/training marches. Unlike real-time monitoring systems, this tool focuses on **post-event analysis** - data becomes available after participants hand in their measurement devices and is processed offline.

### Key Features

- **Individual March Analysis**: Comprehensive personal performance breakdown with intelligent pace estimation
- **Group Comparisons**: Rankings and comparative analysis across participants and squads
- **Pace Calculator**: Speed estimation using movement algorithms (no GPS required)
- **Historical Tracking**: Performance progression across multiple march events
- **Heart Rate Analysis**: HR zones, effort scoring, and cardiovascular load during marches
- **Route Mapping**: GPX track visualization with elevation and pace overlays
- **Role-Based Access**: Separate views for administrators, supervisors, and participants

## Table of Contents

- [Documentation](#documentation)
- [Quick Start](#quick-start)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Development](#development)
- [Deployment](#deployment)
- [Testing](#testing)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Documentation

**Complete documentation is available in the [`docs/`](./docs/) directory.**

### Quick Links

- **[Complete March Workflow](./docs/README.md#common-workflows)** - Full workflow from setup to published results
- **[Database Setup](./docs/setup-database.md)** - Set up PostgreSQL database with Ansible
- **[Loading March Data](./docs/guide-loading-data.md)** - Process and load watch data
- **[Managing Participants](./docs/guide-participants.md)** - Add and manage participants
- **[Managing March Events](./docs/guide-march-events.md)** - Create and manage marches
- **[Deployment Guide](./deployment/README.md)** - Docker and Ansible deployment
- **[Script Reference](./scripts/README.md)** - Database management scripts
- **[Troubleshooting](./docs/troubleshooting.md)** - Common issues and solutions

### Documentation Index

See [`docs/README.md`](./docs/README.md) for complete documentation index.

## Quick Start

### 1. Set Up Database

```bash
# Configure Ansible inventory and vault passwords
cd deployment/ansible
cp inventory/example.yml inventory/production.yml
cp vaults/vault-example.yml vaults/production-vault.yml

# Edit inventory and vault files with your server details
# Then run Ansible playbook (creates database, no mock data)
ansible-playbook -i inventory/production.yml --ask-vault-pass playbooks/march_database.yml
```

See [Database Setup Guide](./docs/setup-database.md) for detailed instructions.

### 2. Add Participants

```bash
# Create participants CSV file
cat > participants.csv << EOF
participant_id,group
SM001,Squad Alpha
SM002,Squad Alpha
SM003,Squad Bravo
EOF

# Generate participant configuration with auto-generated passwords
python scripts/participants/generate_march_seed.py --csv participants.csv production

# Add participants to database
export DATABASE_URL="postgresql://user:password@host:5432/fitonduty_march"
python scripts/participants/add_participants.py --seed-file config/seed-data/production_seed.yml
```

See [Managing Participants Guide](./docs/guide-participants.md) for details.

### 3. Create March Event

```bash
# Interactive mode (recommended)
python scripts/events/manage_march_events.py create --interactive

# Or via command line
python scripts/events/manage_march_events.py create \
  --name "Training March Alpha" \
  --date 2025-03-15 \
  --distance 8.2 \
  --duration 2.5 \
  --group "Squad Alpha"
```

See [Managing March Events Guide](./docs/guide-march-events.md) for details.

### 4. Load March Data

After march completion and device collection:

```bash
# Process raw watch exports
python scripts/data/process_watch_data.py \
  --data-dir ./watch_exports \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output

# Load processed data to database
python scripts/data/load_march_data.py \
  --data-dir ./output \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2

# Update march status to publish results
python scripts/events/manage_march_events.py update-status --march-id 1 --status published
```

See [Loading March Data Guide](./docs/guide-loading-data.md) for complete workflow.

## System Requirements

### Software Requirements

- **Python**: 3.12 or higher
- **PostgreSQL**: 14.0 or higher
- **Operating System**: Linux, macOS, or Windows with WSL2
- **Node.js**: Not required (pure Python stack)

### Hardware Requirements

**Minimum:**
- 2 CPU cores
- 4 GB RAM
- 10 GB disk space

**Recommended:**
- 4+ CPU cores
- 8+ GB RAM
- 20+ GB disk space (for data storage)

### Browser Requirements

Modern browsers with JavaScript enabled:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Installation

### Using uv (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/fitonduty-dashboard-march.git
cd fitonduty-dashboard-march

# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .

# Install development dependencies (optional)
uv pip install -e ".[dev]"
```

### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

### Environment Configuration

```bash
# Copy example environment file
cp config/environments/.env.example .env

# Edit .env with your settings
nano .env
```

**Required environment variables:**

```bash
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=postgresql://user:password@host:5432/fitonduty_march

# Dashboard
DASHBOARD_TITLE="FitonDuty March Dashboard"
LOG_LEVEL=INFO
```

See `config/environments/.env.example` for complete list of configuration options.

## Usage

### Development Mode

```bash
# Start development server (with auto-reload)
python app.py
```

Visit http://localhost:8050

**Default test credentials:**
- Admin: `admin` / `test123`
- Participant: `participant1` / `test123`

### Production Mode

```bash
# Using Gunicorn (recommended)
gunicorn -b 0.0.0.0:8050 -w 4 app:server

# Or with custom configuration
gunicorn -c deployment/gunicorn_config.py app:server
```

### Database Management

```bash
# Create database schema (development)
python src/database/management/create_schema.py

# Seed with test data (development only)
python src/database/management/seed_database.py

# Add participants (production)
python scripts/participants/add_participants.py --seed-file config/seed-data/production_seed.yml

# Manage march events
python scripts/events/manage_march_events.py --help
```

### Data Processing

```bash
# Process watch data
fitonduty-process-watch --help

# Process temperature data
fitonduty-process-temp --help

# Process step data
fitonduty-process-steps --help

# Load data to database
fitonduty-load-data --help
```

See `pyproject.toml` for all available CLI commands.

## Project Structure

```
fitonduty-dashboard-march/
├── docs/                           # Complete documentation
│   ├── README.md                   # Documentation index
│   ├── setup-database.md           # Database setup guide
│   ├── guide-loading-data.md       # Data loading workflow
│   ├── guide-participants.md       # Participant management
│   ├── guide-march-events.md       # Event management
│   └── troubleshooting.md          # Common issues
├── deployment/                     # Deployment configurations
│   ├── ansible/                    # Ansible playbooks
│   │   ├── playbooks/              # Deployment playbooks
│   │   ├── inventory/              # Environment inventories
│   │   └── vaults/                 # Encrypted secrets
│   ├── docker/                     # Docker configurations
│   └── README.md                   # Deployment guide
├── scripts/                        # Database management scripts
│   ├── data/                       # Data processing scripts
│   │   ├── process_watch_data.py
│   │   ├── load_march_data.py
│   │   └── merge_march_data.py
│   ├── events/                     # Event management
│   │   └── manage_march_events.py
│   ├── participants/               # Participant management
│   │   ├── add_participants.py
│   │   └── generate_march_seed.py
│   └── README.md                   # Script documentation
├── src/                            # Source code
│   ├── app/                        # Dashboard application
│   │   ├── main.py                 # Main entry point
│   │   ├── components/             # UI components
│   │   │   ├── auth.py
│   │   │   └── march/              # March-specific components
│   │   ├── callbacks/              # Dash callbacks
│   │   └── utils/                  # Utilities
│   │       ├── auth.py
│   │       └── visualization/      # Charts and visualizations
│   ├── database/                   # Database management
│   │   ├── management/             # Schema and seed scripts
│   │   └── utils.py                # Database utilities
│   └── processing/                 # Data processing pipeline
│       ├── watch_processor.py      # Watch data processor
│       ├── temp_processor.py       # Temperature processor
│       ├── step_processor.py       # Step data processor
│       └── data_loader.py          # Database loader
├── tests/                          # Test suite
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   └── conftest.py                 # Test fixtures
├── config/                         # Configuration files
│   └── seed-data/                  # Seed data templates
├── database/                       # Legacy database scripts (wrappers)
│   └── schema.sql                  # Database schema (reference)
├── app.py                          # Application entry point (wrapper)
├── pyproject.toml                  # Project configuration
├── .env.example                    # Example environment variables
└── README.md                       # This file
```

## Development

### Setting Up Development Environment

```bash
# Install all dependencies including dev tools
uv pip install -e ".[dev,test,notebooks]"

# Install pre-commit hooks (optional)
pre-commit install
```

### Code Style

This project uses:
- **Black** for code formatting (100 char line length)
- **Ruff** for linting

```bash
# Format code
black .

# Lint code
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html --cov-report=term

# Run specific test types
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
pytest -m database       # Database tests only

# Run specific test file
pytest tests/unit/test_auth.py -v

# Run tests in parallel
pytest -n auto
```

### Database Development

```bash
# Create development database
python src/database/management/create_database.py

# Apply schema
python src/database/management/create_schema.py

# Seed with test data
python src/database/management/seed_database.py

# Reset database (drop and recreate)
python src/database/management/create_database.py --drop
python src/database/management/create_schema.py
python src/database/management/seed_database.py
```

### Adding New Features

1. **Create a branch** for your feature
2. **Add tests** first (TDD approach recommended)
3. **Implement feature** following existing patterns
4. **Run tests** and ensure they pass
5. **Format code** with Black and Ruff
6. **Update documentation** if needed
7. **Submit pull request**

See [Contributing](#contributing) for detailed guidelines.

## Deployment

### Docker Deployment

```bash
# Build image
docker build -t fitonduty-march-dashboard .

# Run container
docker run -d \
  -p 8050:8050 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/fitonduty_march" \
  -e SECRET_KEY="your-secret-key" \
  --name march-dashboard \
  fitonduty-march-dashboard

# View logs
docker logs -f march-dashboard
```

### Ansible Deployment

```bash
# Deploy to production
cd deployment/ansible
ansible-playbook -i inventory/production.yml --ask-vault-pass playbooks/deploy.yml

# Deploy database only
ansible-playbook -i inventory/production.yml --ask-vault-pass playbooks/march_database.yml
```

See [Deployment Guide](./deployment/README.md) for comprehensive instructions.

### Systemd Service (Linux)

```bash
# Copy service file
sudo cp deployment/fitonduty-march.service /etc/systemd/system/

# Edit service file with correct paths
sudo nano /etc/systemd/system/fitonduty-march.service

# Enable and start service
sudo systemctl enable fitonduty-march
sudo systemctl start fitonduty-march

# Check status
sudo systemctl status fitonduty-march
```

## Testing

### Test Organization

- **Unit Tests** (`tests/unit/`): Test individual components in isolation
- **Integration Tests** (`tests/integration/`): Test component interactions
- **Database Tests**: Require actual database connection

### Running Specific Tests

```bash
# Test authentication
pytest tests/unit/test_auth.py

# Test database queries
pytest tests/integration/test_database.py

# Test with verbose output
pytest -v

# Test with markers
pytest -m "not slow"  # Skip slow tests
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Architecture

### Technology Stack

**Backend:**
- Python 3.12+
- Flask (web framework)
- Dash (interactive dashboards)
- SQLAlchemy (database ORM)
- Flask-Login (authentication)

**Frontend:**
- Dash Bootstrap Components (UI framework)
- Plotly (data visualization)
- LUX theme (Bootstrap theme)

**Database:**
- PostgreSQL 14+
- Custom march schema with:
  - User management (admin, supervisor, participant roles)
  - March event tracking
  - Time-series physiological data
  - Aggregate performance metrics

**Deployment:**
- Docker containers
- Gunicorn WSGI server
- Ansible automation
- Systemd service management

### Database Schema

Key tables:
- `users` - User accounts with role-based access
- `groups` - Participant squads/teams
- `march_events` - March event definitions
- `march_participants` - Participant-march assignments
- `march_health_metrics` - Aggregate performance data
- `march_timeseries_data` - Time-series HR, steps, speed data
- `march_hr_zones` - Heart rate zone distributions

**March Status Flow:**
```
planned → completed → processing → published
```

See [`database/schema.sql`](./database/schema.sql) for complete schema.

### Data Processing Pipeline

1. **Watch Export** - Collect raw data from devices
2. **Processing** - Extract and process physiological metrics
3. **Aggregation** - Calculate performance statistics
4. **Loading** - Upload to database
5. **Publishing** - Make results available in dashboard

## Contributing

We welcome contributions! Please follow these guidelines:

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Format code (`black . && ruff check --fix .`)
6. Commit changes (`git commit -m 'Add amazing feature'`)
7. Push to branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Coding Standards

- Follow PEP 8 style guide
- Use Black for formatting (100 char line length)
- Add docstrings to all functions and classes
- Write tests for new features
- Update documentation as needed

### Commit Messages

Use conventional commit format:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `style:` Code style changes
- `chore:` Maintenance tasks

Example: `feat: add pace estimation algorithm for uphill sections`

## Troubleshooting

### Common Issues

**Database Connection Errors:**
```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check if database exists
psql -U postgres -l | grep fitonduty_march
```

**Port Already in Use:**
```bash
# Find process using port 8050
lsof -i :8050

# Kill process
kill -9 <PID>
```

**Import Errors:**
```bash
# Reinstall dependencies
uv pip install -e .

# Check Python version
python --version  # Should be 3.12+
```

**Permission Denied (Database):**
```bash
# Grant privileges
psql -U postgres -d fitonduty_march -c "
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO march_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO march_user;
"
```

See [Troubleshooting Guide](./docs/troubleshooting.md) for more solutions.

## Security

### Best Practices

- Never commit passwords or secrets to version control
- Use environment variables for sensitive configuration
- Store seed files securely (consider Ansible Vault)
- Change default admin password immediately in production
- Use SSL/TLS for database connections in production
- Enable HTTPS for web dashboard
- Rotate database passwords regularly
- Keep dependencies updated

### Reporting Security Issues

Please report security vulnerabilities to [security@example.com](mailto:security@example.com)

## Performance Considerations

- Database queries use indexes for frequently accessed columns
- Time-series data uses pagination for large datasets
- Expensive computations are cached when possible
- Gunicorn workers scale based on CPU cores (2 × CPU + 1)
- PostgreSQL connection pooling recommended for production

## License

[MIT License](LICENSE) - see LICENSE file for details

## Related Projects

This project is part of the FitonDuty infrastructure:

- **[fitonduty-database](https://github.com/your-org/fitonduty-database)** - Main database schema and migrations
- **[fitonduty-processing](https://github.com/your-org/fitonduty-processing)** - Physiological data processing pipeline
- **[fitonduty-dashboard](https://github.com/your-org/fitonduty-dashboard)** - Real-time monitoring dashboard

## Resources

- **[Dash Documentation](https://dash.plotly.com/)** - Dash framework
- **[Dash Bootstrap Components](https://dash-bootstrap-components.opensource.faculty.ai/)** - UI components
- **[SQLAlchemy](https://docs.sqlalchemy.org/)** - Database ORM
- **[Flask-Login](https://flask-login.readthedocs.io/)** - Authentication
- **[Plotly](https://plotly.com/python/)** - Visualization library

## Support

- **Documentation**: [`docs/`](./docs/) directory
- **Script Reference**: [`scripts/README.md`](./scripts/README.md)
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

## Acknowledgments

- Built with [Dash](https://dash.plotly.com/) by Plotly
- UI components from [Dash Bootstrap Components](https://dash-bootstrap-components.opensource.faculty.ai/)
- Icons from [Bootstrap Icons](https://icons.getbootstrap.com/)

---

**Built with care for physiological monitoring and performance analysis.**