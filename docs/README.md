# FitonDuty March Dashboard Documentation

Complete documentation for setting up and managing the FitonDuty March Dashboard - a post-event analysis system for long march physiological monitoring.

## Documentation Index

### Setup Guides
- **[Database Setup](./setup-database.md)** - Set up PostgreSQL database with Ansible or manually

### User Guides
- **[Managing Participants](./guide-participants.md)** - Add and manage march participants
- **[Managing March Events](./guide-march-events.md)** - Create and manage march events
- **[Loading March Data](./guide-loading-data.md)** - Process and load real march data from watches
- **[Step Data Processing](./process_step_data.md)** - Accelerometer-based step computation

### Reference
- **[Scripts Reference](./reference-scripts.md)** - Complete reference for all scripts
- **[GPS Visualization](./reference-gps.md)** - GPS route tracking and visualization

### Operations
- **[Troubleshooting](./troubleshooting.md)** - Common issues and solutions

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
ansible-playbook -i inventory/<environment>.yml playbooks/march_database.yml

# 2. One-time setup: Add participants
python scripts/participants/add_participants.py --seed-file config/seed-data/participants.yml

# 3. Before march: Create march event
python scripts/events/manage_march_events.py create --interactive

# 4. After march: Process watch data
python scripts/data/process_watch_data.py \
  --data-dir ./watch_exports \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output

# 5. After processing: Load data to database
python scripts/data/load_march_data.py \
  --data-dir ./output \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2

# 6. Publish results
python scripts/events/manage_march_events.py update-status --march-id 1 --status published
```

See [Loading March Data Guide](./guide-loading-data.md) for detailed instructions.

## Contributing

Found an error in the documentation? Have a suggestion? Please update the docs or create an issue.

## Getting Help

- **Troubleshooting:** See [Troubleshooting Guide](./troubleshooting.md)
- **Issues:** Check existing issues or create a new one
- **Contact:** [Your contact information]
