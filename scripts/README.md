# March Dashboard Seeding Scripts

This directory contains scripts to seed and manage the production database for the FitonDuty March Dashboard.

## Scripts Overview

### 1. `generate_march_seed.py`
Generates seed data configuration files with participants and auto-generated secure passwords.

**Usage:**
```bash
# Generate from CSV file
python scripts/generate_march_seed.py --csv participants.csv march_2025

# Interactive mode
python scripts/generate_march_seed.py --interactive march_2025

# With custom output path
python scripts/generate_march_seed.py --csv participants.csv march_2025 \
  --output config/seed-data/march_2025.yml

# Dry run (see what would be generated)
python scripts/generate_march_seed.py --csv participants.csv march_2025 --dry-run
```

**CSV Format:**
```csv
participant_id,group
01AB,Squad Alpha
02CD,Squad Alpha
03EF,Squad Bravo
```

**Output:** YAML configuration file with:
- Auto-generated secure passwords for all users
- Group definitions
- Participant assignments

### 2. `add_participants.py`
Adds participants from a seed YAML file to a live database. Only adds new participants, skipping existing ones.

**Usage:**
```bash
# Add participants from seed file (interactive)
python scripts/add_participants.py --seed-file config/seed-data/march_2025.yml

# With custom database URL
python scripts/add_participants.py \
  --seed-file config/seed-data/march_2025.yml \
  --db-url postgresql://user:password@host:5432/dbname

# Dry run (see what would be added)
python scripts/add_participants.py \
  --seed-file config/seed-data/march_2025.yml \
  --dry-run
```

**Features:**
- Safely adds only new participants (preserves existing data)
- Automatically creates missing groups
- Adds admin users if needed
- Uses passwords from seed file
- Confirmation prompt before making changes

### 3. `manage_march_events.py`
Creates and manages march events in the database.

**Usage:**

**Create march event (interactive):**
```bash
python scripts/manage_march_events.py create --interactive
```

**Create march event (command line):**
```bash
python scripts/manage_march_events.py create \
  --name "Training March Alpha" \
  --date 2025-03-15 \
  --distance 8.2 \
  --duration 2.5 \
  --group "Squad Alpha" \
  --route "Forest trail with moderate elevation" \
  --status planned
```

**List all march events:**
```bash
python scripts/manage_march_events.py list
```

**Update march status:**
```bash
python scripts/manage_march_events.py update-status \
  --march-id 1 \
  --status completed
```

**Add participants to a march:**
```bash
# Add all participants from march's group
python scripts/manage_march_events.py add-participants --march-id 1

# Add participants from specific group
python scripts/manage_march_events.py add-participants \
  --march-id 1 \
  --group "Squad Alpha"
```

**Available statuses:**
- `planned` - March is scheduled but not yet conducted
- `completed` - March has been completed
- `processing` - Data is being processed
- `published` - Results are published and visible to participants

## Complete Workflow

### Initial Setup

1. **Prepare participant data**
   ```bash
   # Create a CSV file with participant IDs and groups
   cat > participants.csv << EOF
   participant_id,group
   01AB,Squad Alpha
   02CD,Squad Alpha
   03EF,Squad Bravo
   EOF
   ```

2. **Generate seed configuration**
   ```bash
   python scripts/generate_march_seed.py --csv participants.csv march_2025
   ```

3. **Review and customize the generated file**
   ```bash
   # Edit config/seed-data/march_2025_seed.yml
   # Change admin password if needed
   # Verify all participants are correct
   ```

4. **Add participants to database**
   ```bash
   # Set database URL (optional)
   export DATABASE_URL="postgresql://user:password@host:5432/dbname"

   # Add participants
   python scripts/add_participants.py \
     --seed-file config/seed-data/march_2025_seed.yml
   ```

### Managing March Events

1. **Create a new march event**
   ```bash
   # Interactive mode (recommended)
   python scripts/manage_march_events.py create --interactive

   # Or via command line
   python scripts/manage_march_events.py create \
     --name "Training March Alpha" \
     --date 2025-03-15 \
     --distance 8.2 \
     --duration 2.5 \
     --group "Squad Alpha"
   ```

2. **Add participants to the march**
   ```bash
   python scripts/manage_march_events.py add-participants --march-id 1
   ```

3. **List all marches**
   ```bash
   python scripts/manage_march_events.py list
   ```

4. **Update march status after completion**
   ```bash
   python scripts/manage_march_events.py update-status \
     --march-id 1 \
     --status completed
   ```

### Adding New Participants to Existing Campaign

1. **Update participants CSV with new entries**
   ```csv
   participant_id,group
   11UV,Squad Alpha
   12WX,Squad Bravo
   ```

2. **Generate updated seed file**
   ```bash
   python scripts/generate_march_seed.py \
     --csv new_participants.csv \
     march_2025_update
   ```

3. **Add only new participants**
   ```bash
   python scripts/add_participants.py \
     --seed-file config/seed-data/march_2025_update_seed.yml
   ```

## Environment Variables

All scripts support the following environment variables:

- `DATABASE_URL` - PostgreSQL connection URL
  ```bash
  export DATABASE_URL="postgresql://user:password@host:5432/dbname"
  ```

## Database URL Format

```
postgresql://username:password@host:port/database_name
```

**Examples:**
```bash
# Local development
postgresql://postgres:password@localhost:5432/fitonduty_march

# Production
postgresql://march_admin:SecurePass123@db.example.com:5432/fitonduty_march_prod
```

## Security Best Practices

1. **Password Management**
   - All scripts generate secure random passwords
   - Store seed files securely (never commit to version control)
   - Change default admin password immediately after setup
   - Consider using a password manager for storing credentials

2. **Database Access**
   - Use environment variables for database URLs in production
   - Create separate database users with minimal required privileges
   - Use SSL/TLS for database connections in production

3. **Seed File Storage**
   - Add `config/seed-data/*_seed.yml` to `.gitignore`
   - Store production seed files in secure vault (e.g., Ansible Vault)
   - Encrypt seed files containing production credentials

## Troubleshooting

### Connection Issues
```bash
# Test database connection
psql postgresql://user:password@host:5432/dbname -c "SELECT 1"

# Check if database exists
psql -U postgres -l
```

### Permission Errors
```bash
# Grant necessary permissions
psql -U postgres -d fitonduty_march << EOF
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO march_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO march_admin;
EOF
```

### Script Errors
- Ensure all required dependencies are installed: `pip install pyyaml sqlalchemy werkzeug psycopg2-binary`
- Check database schema is up to date
- Verify CSV file format matches expected structure

## Example Files

See `config/seed-data/` for example files:
- `example_seed.yml` - Example seed configuration
- `example_participants.csv` - Example CSV format

## Integration with Deployment

These scripts can be integrated into deployment workflows:

```bash
# Ansible playbook example
- name: Generate seed data
  command: python scripts/generate_march_seed.py --csv /path/to/participants.csv campaign_name

- name: Add participants to database
  command: python scripts/add_participants.py --seed-file /path/to/seed.yml
  environment:
    DATABASE_URL: "{{ database_url }}"
```