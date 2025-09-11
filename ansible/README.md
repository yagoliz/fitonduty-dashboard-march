# Ansible Database Setup

This directory contains Ansible playbooks for setting up the FitonDuty March Dashboard database on remote servers.

## Quick Setup

### 1. Configure Your Server Details

```bash
# Copy example inventory
cp inventory/example.yml inventory/testing.yml

# Edit with your server details
vim inventory/testing.yml
```

### 2. Configure Database Passwords

```bash
# Copy vault example
cp vars/vault-example.yml vars/<server>/vault.yml

# Edit with your passwords
vim vars/<server>/vault.yml

# Encrypt the vault file
ansible-vault encrypt vars/<server>/vault.yml
```

### 3. Run the Setup

```bash
# Or manually with staging
ansible-playbook -i inventory/testing.yml --ask-vault-pass playbooks/setup_march_database.yml
```

## What It Does

The Ansible playbook will:

1. ✅ Create database working directory (`/opt/fitonduty-march`)
2. ✅ Install Python dependencies in virtual environment  
3. ✅ Copy schema and seeding scripts to server
4. ✅ Create database and user with proper permissions
5. ✅ Run database schema and seed with sample data
6. ✅ Create connection info file with credentials

## Configuration Files

### Inventory (`inventory/staging.yml`)
```yaml
all:
  children:
    database_servers:
      hosts:
        your-server.example.com:
          ansible_user: your-ssh-user
          db_name: fitonduty_march
          db_user: fitonduty_march
```

### Vault (`vault.yml` - encrypted)
```yaml
vault_postgres_password: your-postgres-password
vault_march_db_password: your-march-db-password
```

## Manual Steps Alternative

If you prefer manual setup:

```bash
# 1. Copy files to server
scp -r ../database/ user@server:/opt/fitonduty-march/scripts/

# 2. Create database manually
ssh user@server
sudo -u postgres createdb fitonduty_march
sudo -u postgres psql -d fitonduty_march -f /opt/fitonduty-march/scripts/schema.sql

# 3. Run seeding script
cd /opt/fitonduty-march/scripts
python3 seed_database.py
```

## Server Requirements

- Ubuntu/Debian Linux
- PostgreSQL installed and running
- Python 3.8+ available
- SSH access with sudo privileges

## Files Created on Server

- `/opt/fitonduty-march/` - Working directory
- `/opt/fitonduty-march/venv/` - Python virtual environment
- `/opt/fitonduty-march/scripts/` - Database scripts
- `/opt/fitonduty-march/database_info.txt` - Connection details

## Troubleshooting

### Ansible Connection Issues
```bash
# Test connectivity
ansible -i inventory/staging.yml database_servers -m ping

# Check SSH key
ssh -i ~/.ssh/your-key user@your-server
```

### PostgreSQL Issues
```bash
# Check if PostgreSQL is running
ssh user@server 'sudo systemctl status postgresql'

# Check database exists
ssh user@server 'sudo -u postgres psql -l | grep fitonduty_march'
```

### Permission Issues
```bash
# Check database permissions
ssh user@server 'sudo -u postgres psql -d fitonduty_march -c "\\dp"'
```