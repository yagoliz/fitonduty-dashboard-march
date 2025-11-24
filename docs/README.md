# FitonDuty March Dashboard Documentation

Complete documentation for setting up and managing the FitonDuty March Dashboard - a post-event analysis system for long march physiological monitoring.

## Documentation Index

### Getting Started
- **[Quick Start Guide](./quick-start.md)** - Get up and running in 15 minutes
- **[Architecture Overview](./architecture.md)** - System design and components

### Setup Guides
- **[Database Setup](./setup-database.md)** - Set up PostgreSQL database with Ansible or manually
- **[Production Deployment](./setup-production.md)** - Deploy to production environment
- **[Development Setup](./setup-development.md)** - Set up local development environment

### User Guides
- **[Managing Participants](./guide-participants.md)** - Add and manage march participants
- **[Managing March Events](./guide-march-events.md)** - Create and manage march events
- **[Loading March Data](./guide-loading-data.md)** - Process and load real march data from watches
- **[Publishing Results](./guide-publishing.md)** - Publish march results to participants

### Reference
- **[Scripts Reference](./reference-scripts.md)** - Complete reference for all scripts
- **[GPS Visualization](./reference-gps.md)** - GPS route tracking and visualization
- **[Database Schema](./reference-schema.md)** - Database tables and relationships
- **[Configuration](./reference-config.md)** - Configuration options and environment variables
- **[API & Endpoints](./reference-api.md)** - Dashboard API endpoints

### Operations
- **[Troubleshooting](./troubleshooting.md)** - Common issues and solutions
- **[Backup & Recovery](./operations-backup.md)** - Database backup and recovery procedures
- **[Monitoring](./operations-monitoring.md)** - System monitoring and health checks

## Quick Links

**For First-Time Setup:**
1. [Database Setup](./setup-database.md) - Set up infrastructure with Ansible
2. [Managing Participants](./guide-participants.md) - Add your participants
3. [Loading March Data](./guide-loading-data.md) - Load your first march

**For Ongoing Operations:**
- [Managing March Events](./guide-march-events.md) - Create new marches
- [Loading March Data](./guide-loading-data.md) - Load watch data after each march
- [Troubleshooting](./troubleshooting.md) - Fix common issues

## Common Workflows

### Complete March Workflow (Start to Finish)

```bash
# 1. One-time setup: Database infrastructure
ansible-playbook -i inventory/production.yml playbooks/march_database.yml

# 2. One-time setup: Add participants
python scripts/add_participants.py --seed-file config/seed-data/participants.yml

# 3. Before march: Create march event
python scripts/manage_march_events.py create --interactive

# 4. After march: Process watch data
python scripts/process_watch_data.py \
  --data-dir ./watch_exports \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output

# 5. After processing: Load data to database
python scripts/load_march_data.py \
  --data-dir ./output \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2

# 6. Publish results
python scripts/manage_march_events.py update-status --march-id 1 --status published
```

See [Loading March Data Guide](./guide-loading-data.md) for detailed instructions.

## Contributing

Found an error in the documentation? Have a suggestion? Please update the docs or create an issue.

## Getting Help

- **Troubleshooting:** See [Troubleshooting Guide](./troubleshooting.md)
- **Issues:** Check existing issues or create a new one
- **Contact:** [Your contact information]
