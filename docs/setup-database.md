# Database Setup Guide

Complete guide for setting up the PostgreSQL database for FitonDuty March Dashboard.

## Overview

The database can be set up in two ways:
1. **Ansible (Recommended)** - Automated setup for production
2. **Manual** - Step-by-step for custom setups or troubleshooting

Both methods create the same result: a PostgreSQL database with the march dashboard schema, ready for real data.

## Method 1: Ansible Setup (Recommended)

### Prerequisites

- Ubuntu/Debian server (20.04+ recommended)
- SSH access with sudo privileges
- Ansible installed on control machine

### Step 1: Configure Inventory

```bash
cd ansible

# Copy example inventory
cp inventory/example.yml inventory/production.yml

# Edit with your details
vim inventory/production.yml
```

Inventory configuration:
```yaml
all:
  children:
    database_servers:
      hosts:
        your-server.example.com:
          ansible_user: ubuntu          # SSH user
          db_name: fitonduty_march       # Database name
          db_user: fitonduty_march       # Database user
```

### Step 2: Set Passwords

```bash
# Copy vault template
cp vars/vault-example.yml vars/production/vault.yml

# Edit passwords
vim vars/production/vault.yml
```

Set secure passwords:
```yaml
vault_postgres_password: "your-secure-postgres-password"
vault_march_db_password: "your-secure-march-db-password"
```

Encrypt the vault file:
```bash
ansible-vault encrypt vars/production/vault.yml
# Enter vault password when prompted
```

### Step 3: Run Playbook

```bash
ansible-playbook -i inventory/production.yml \
  --ask-vault-pass \
  playbooks/march_database.yml
```

You'll be prompted for the vault password you created in Step 2.

### What the Playbook Does

1. Install PostgreSQL (if not already installed)
2. Configure PostgreSQL for remote connections
3. Set PostgreSQL superuser password
4. Create march database
5. Create march database user with password
6. Run database schema (creates all tables, indexes)
7. Configure permissions
8. Create connection info file

### Seeding Modes

**Default (Schema Only - No Mock Data):**
```bash
# Default creates schema only
ansible-playbook -i inventory/production.yml --ask-vault-pass playbooks/march_database.yml
```

**Development (With Mock Data):**
```bash
# Override to include mock data for testing
ansible-playbook -i inventory/production.yml --ask-vault-pass \
  -e "march_seed_mode=mock" \
  playbooks/march_database.yml
```

### Verify Setup

After playbook completes:

```bash
# Test connection
psql "postgresql://fitonduty_march:your-password@your-server:5432/fitonduty_march" \
  -c "SELECT COUNT(*) FROM march_events"

# Should return: count = 0 (for schema-only mode)
```

## Method 2: Manual Setup

### Step 1: Install PostgreSQL

```bash
# SSH to server
ssh user@your-server

# Update package list
sudo apt update

# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Step 2: Configure PostgreSQL

Set superuser password:
```bash
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'your-secure-password';"
```

Configure for remote connections:
```bash
# Edit postgresql.conf
sudo vim /etc/postgresql/16/main/postgresql.conf
# Change: listen_addresses = '*'

# Edit pg_hba.conf
sudo vim /etc/postgresql/16/main/pg_hba.conf
# Add: host all all 0.0.0.0/0 scram-sha-256

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Step 3: Create Database

```bash
sudo -u postgres psql << EOF
CREATE DATABASE fitonduty_march;
CREATE USER fitonduty_march WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE fitonduty_march TO fitonduty_march;
EOF
```

### Step 4: Create Schema

```bash
# Download schema file
cd /tmp
git clone https://github.com/your-org/fitonduty-dashboard-march
cd fitonduty-dashboard-march

# Apply schema
sudo -u postgres psql -d fitonduty_march -f database/schema.sql
```

Or use the Python script:
```bash
export DATABASE_URL="postgresql://postgres:password@localhost:5432/fitonduty_march"
python database/create_schema.py
```

### Step 5: Grant Permissions

```bash
sudo -u postgres psql -d fitonduty_march << EOF
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fitonduty_march;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fitonduty_march;
GRANT USAGE ON SCHEMA public TO fitonduty_march;
EOF
```

### Step 6: Verify Setup

```bash
psql "postgresql://fitonduty_march:password@localhost:5432/fitonduty_march" << EOF
\dt
SELECT COUNT(*) FROM march_events;
EOF
```

Should show all tables and count = 0.

## Database Connection

### Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]
```

### Example

```bash
# Production
postgresql://fitonduty_march:SecurePass123@db.example.com:5432/fitonduty_march

# Local development
postgresql://fitonduty_march:password@localhost:5432/fitonduty_march
```

### Using Connection String

Set as environment variable:
```bash
export DATABASE_URL="postgresql://fitonduty_march:password@host:5432/fitonduty_march"

# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Use in scripts
python scripts/add_participants.py --seed-file config/seed-data/participants.yml
```

## Database Schema

The schema includes these tables:

**User Management:**
- `users` - User accounts (admin, participant)
- `groups` - Participant groups/squads
- `user_groups` - Group memberships
- `sessions` - Login sessions

**March Events:**
- `march_events` - March definitions
- `march_participants` - Participant assignments

**Performance Data:**
- `march_health_metrics` - Aggregate metrics per participant
- `march_hr_zones` - Heart rate zone distributions
- `march_movement_speeds` - Movement speed analysis
- `march_timeseries_data` - Time-series physiological data
- `march_gps_positions` - GPS tracks

See [Database Schema Reference](./reference-schema.md) for detailed documentation.

## Security Best Practices

### 1. Strong Passwords

Use strong, unique passwords:
```bash
# Generate secure password
openssl rand -base64 32
```

### 2. Restrict Database Access

Production pg_hba.conf should limit to specific IPs:
```
# Replace 0.0.0.0/0 with specific IPs
host all all 192.168.1.0/24 scram-sha-256
host all all 10.0.0.5/32 scram-sha-256
```

### 3. SSL/TLS Connections

For production, enable SSL:
```bash
# postgresql.conf
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'
```

Connect with SSL:
```bash
postgresql://user:pass@host:5432/db?sslmode=require
```

### 4. Firewall Rules

Restrict port 5432:
```bash
# Ubuntu/Debian
sudo ufw allow from 192.168.1.0/24 to any port 5432
sudo ufw enable

# Or iptables
sudo iptables -A INPUT -p tcp -s 192.168.1.0/24 --dport 5432 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5432 -j DROP
```

### 5. Regular Backups

Set up automated backups:
```bash
# Daily backup script
pg_dump -h host -U fitonduty_march fitonduty_march | \
  gzip > /backups/march_$(date +%Y%m%d).sql.gz

# Add to cron
0 2 * * * /path/to/backup-script.sh
```

See [Backup & Recovery Guide](./operations-backup.md) for details.

## Troubleshooting

### Connection Refused

**Problem:** Can't connect to database

**Solutions:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check listening on network
sudo netstat -tlnp | grep 5432

# Verify listen_addresses
grep listen_addresses /etc/postgresql/*/main/postgresql.conf

# Check pg_hba.conf
sudo cat /etc/postgresql/*/main/pg_hba.conf | grep "0.0.0.0"

# Restart after changes
sudo systemctl restart postgresql
```

### Authentication Failed

**Problem:** Password incorrect

**Solutions:**
```bash
# Reset postgres password
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'newpassword';"

# Reset march user password
sudo -u postgres psql -d fitonduty_march -c "ALTER USER fitonduty_march WITH PASSWORD 'newpassword';"
```

### Permission Denied

**Problem:** User can't access tables

**Solutions:**
```bash
sudo -u postgres psql -d fitonduty_march << EOF
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fitonduty_march;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fitonduty_march;
GRANT USAGE ON SCHEMA public TO fitonduty_march;
EOF
```

### Firewall Blocking

**Problem:** Connection times out

**Solutions:**
```bash
# Check firewall status
sudo ufw status
sudo iptables -L -n | grep 5432

# Allow PostgreSQL port
sudo ufw allow 5432/tcp
```

### Version Mismatch

**Problem:** Ansible can't find PostgreSQL config files

**Solutions:**
```bash
# Find PostgreSQL version
psql --version

# Update Ansible playbook or set variable
ansible-playbook ... -e "postgresql_version=14"
```

## Next Steps

After database is set up:
1. [Add Participants](./guide-participants.md) - Add march participants
2. [Create March Events](./guide-march-events.md) - Define your marches
3. [Load March Data](./guide-loading-data.md) - Load real march data

## See Also

- [Production Deployment Guide](./setup-production.md) - Full production setup
- [Ansible README](../ansible/README.md) - Detailed Ansible documentation
- [Troubleshooting Guide](./troubleshooting.md) - Common issues
- [Database Schema Reference](./reference-schema.md) - Complete schema documentation