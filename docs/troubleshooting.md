# Troubleshooting Guide

Common issues and solutions for FitonDuty March Dashboard.

## Database Connection Issues

### Connection Refused

**Symptoms:**
```
connection to server at "192.168.1.100", port 5432 failed: Connection refused
Is the server running on that host and accepting TCP/IP connections?
```

**Causes:**
1. PostgreSQL not running
2. PostgreSQL not listening on network interface
3. Firewall blocking port 5432
4. Wrong host/port in connection string

**Solutions:**

```bash
# 1. Check PostgreSQL is running
ssh user@server 'sudo systemctl status postgresql'

# If not running, start it
ssh user@server 'sudo systemctl start postgresql'

# 2. Check PostgreSQL is listening on network
ssh user@server 'sudo netstat -tlnp | grep 5432'
# or
ssh user@server 'sudo ss -tlnp | grep 5432'

# Should show: 0.0.0.0:5432 (all interfaces) or specific IP

# 3. Check postgresql.conf
ssh user@server "grep 'listen_addresses' /etc/postgresql/*/main/postgresql.conf"

# Should show: listen_addresses = '*'
# If not, edit and restart:
ssh user@server 'sudo vim /etc/postgresql/16/main/postgresql.conf'
# Change: listen_addresses = '*'
ssh user@server 'sudo systemctl restart postgresql'

# 4. Check firewall
ssh user@server 'sudo ufw status'

# Allow PostgreSQL if blocked
ssh user@server 'sudo ufw allow 5432/tcp'

# For iptables:
ssh user@server 'sudo iptables -L -n | grep 5432'
```

### Authentication Failed

**Symptoms:**
```
FATAL: password authentication failed for user "fitonduty_march"
```

**Solutions:**

```bash
# 1. Verify credentials
psql "postgresql://fitonduty_march:password@host:5432/fitonduty_march" -c "SELECT 1"

# 2. Reset password
ssh user@server
sudo -u postgres psql << EOF
ALTER USER fitonduty_march WITH PASSWORD 'newpassword';
EOF

# 3. Check pg_hba.conf allows password authentication
ssh user@server "sudo cat /etc/postgresql/*/main/pg_hba.conf | grep fitonduty_march"

# Should show: scram-sha-256 or md5 authentication method
# If shows 'reject', update pg_hba.conf

# 4. Restart PostgreSQL after changes
ssh user@server 'sudo systemctl restart postgresql'
```

### Permission Denied

**Symptoms:**
```
ERROR: permission denied for table march_events
```

**Solutions:**

```sql
-- Connect as postgres superuser
psql postgresql://postgres:password@host:5432/fitonduty_march

-- Grant all permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fitonduty_march;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fitonduty_march;
GRANT USAGE ON SCHEMA public TO fitonduty_march;
GRANT CREATE ON SCHEMA public TO fitonduty_march;

-- Verify permissions
\dp march_events
```

### Database Does Not Exist

**Symptoms:**
```
FATAL: database "fitonduty_march" does not exist
```

**Solutions:**

```bash
# Check existing databases
psql postgresql://postgres:password@host:5432/postgres -c "\l"

# Create database
psql postgresql://postgres:password@host:5432/postgres << EOF
CREATE DATABASE fitonduty_march;
EOF

# Run schema creation
export DATABASE_URL="postgresql://postgres:password@host:5432/fitonduty_march"
python database/create_schema.py
```

## Ansible Issues

### "postgres user not found"

**Symptoms:**
```
TASK [Create march database working directory]
fatal: [database]: FAILED! => {"msg": "chown failed: failed to look up user postgres"}
```

**Cause:** PostgreSQL not installed yet (postgres system user created by PostgreSQL package)

**Solution:**
This is fixed in the updated playbook which installs PostgreSQL first. Re-run:

```bash
ansible-playbook -i inventory/production.yml --ask-vault-pass playbooks/march_database.yml
```

### Ansible Connection Issues

**Symptoms:**
```
fatal: [host]: UNREACHABLE! => {"changed": false, "msg": "Failed to connect to the host via ssh"}
```

**Solutions:**

```bash
# 1. Test SSH connectivity
ssh user@your-server

# 2. Test Ansible ping
ansible -i inventory/production.yml database_servers -m ping

# 3. Check SSH key
ssh -i ~/.ssh/your-key user@your-server

# 4. Verify inventory file
cat inventory/production.yml

# 5. Try with verbose output
ansible-playbook -i inventory/production.yml --ask-vault-pass -vvv playbooks/march_database.yml
```

### Vault Password Issues

**Symptoms:**
```
ERROR! Attempting to decrypt but no vault secrets found
```

**Solutions:**

```bash
# 1. Verify vault file is encrypted
head vars/production/vault.yml
# Should show: $ANSIBLE_VAULT;1.1;AES256

# 2. If not encrypted, encrypt it
ansible-vault encrypt vars/production/vault.yml

# 3. If you forgot password, decrypt with old password and re-encrypt
ansible-vault decrypt vars/production/vault.yml
ansible-vault encrypt vars/production/vault.yml

# 4. Use --ask-vault-pass flag
ansible-playbook -i inventory/production.yml --ask-vault-pass playbooks/march_database.yml
```

## Data Loading Issues

### "No CSV files found"

**Symptoms:**
```
No CSV files found in directory: ./march_data
```

**Solutions:**

```bash
# 1. Verify directory exists and has files
ls -la ./march_data/

# 2. Check file extensions (.CSV or .csv)
ls ./march_data/*.CSV ./march_data/*.csv 2>/dev/null

# 3. Verify you're in correct directory
pwd

# 4. Use absolute path
python scripts/process_watch_data.py \
  --data-dir /full/path/to/march_data \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output
```

### "Could not parse timestamp"

**Symptoms:**
```
ValueError: Could not parse timestamp format in CSV
```

**Solutions:**

1. Check CSV format - ensure it has proper timestamps
2. Verify watch export format is supported
3. Try exporting from watch software with different format
4. Manually inspect CSV:

```bash
head -20 ./march_data/SM001.CSV
```

### "Participant ID not found for mapping"

**Symptoms:**
```
WARNING: Could not map 3 rows with IDs: ['SM001', 'SM002', 'SM003']
```

**Solutions:**

```bash
# 1. List participant IDs in CSV
cut -d',' -f2 ./output/march_health_metrics.csv | sort -u

# 2. List usernames in database
psql $DATABASE_URL -c "SELECT username FROM users WHERE role='participant'"

# 3. Create mapping between CSV IDs and database usernames
python scripts/load_march_data.py \
  --data-dir ./output \
  --march-id 1 \
  --mapping SM001:participant1,SM002:participant2,SM003:participant3
```

### Duplicate Key Error

**Symptoms:**
```
ERROR: duplicate key value violates unique constraint "march_health_metrics_march_id_user_id_key"
```

**Cause:** Data already exists for this march and participant

**Solutions:**

```sql
-- Option 1: Delete existing data for this march
DELETE FROM march_timeseries_data WHERE march_id = 1;
DELETE FROM march_gps_positions WHERE march_id = 1;
DELETE FROM march_hr_zones WHERE march_health_metric_id IN (
  SELECT id FROM march_health_metrics WHERE march_id = 1
);
DELETE FROM march_health_metrics WHERE march_id = 1;

-- Then reload data
```

Or use the script which handles updates:
```bash
# Script automatically replaces timeseries/GPS data
python scripts/load_march_data.py --data-dir ./output --march-id 1
```

## Participant Management Issues

### "Group does not exist"

**Symptoms:**
```
ERROR: Group 'Squad Alpha' not found in database
```

**Solutions:**

```sql
-- List existing groups
SELECT id, group_name FROM groups;

-- Create missing group
INSERT INTO groups (group_name, description)
VALUES ('Squad Alpha', 'Alpha squad members');
```

Or the script creates groups automatically when using seed files.

### "No participants found"

**Symptoms:**
```
No participants found for group: Squad Alpha
```

**Solutions:**

```sql
-- Check participants in group
SELECT u.username, g.group_name
FROM users u
JOIN user_groups ug ON u.id = ug.user_id
JOIN groups g ON ug.group_id = g.id
WHERE g.group_name = 'Squad Alpha'
  AND u.role = 'participant';

-- Add participants to group
INSERT INTO user_groups (user_id, group_id)
SELECT u.id, g.id
FROM users u, groups g
WHERE u.username = 'SM001'
  AND g.group_name = 'Squad Alpha';
```

## Dashboard Issues

### Port Already in Use

**Symptoms:**
```
OSError: [Errno 48] Address already in use
```

**Solutions:**

```bash
# 1. Find process using port 8050
lsof -i :8050

# 2. Kill the process
kill -9 <PID>

# 3. Or use different port
python app.py --port 8051
```

### Import Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'dash'
```

**Solutions:**

```bash
# 1. Verify virtual environment is activated
which python
# Should show: /path/to/venv/bin/python

# 2. Reinstall dependencies
uv pip install -e .

# 3. Check Python version (requires 3.12+)
python --version

# 4. Create fresh virtual environment
rm -rf .venv
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Login Issues

**Symptoms:**
- Can't login with credentials
- "Invalid username or password" error

**Solutions:**

```sql
-- Check user exists
SELECT username, role FROM users WHERE username = 'participant1';

-- Reset password
UPDATE users
SET password = crypt('newpassword', gen_salt('bf'))
WHERE username = 'participant1';

-- Or recreate user using seed file
python scripts/add_participants.py --seed-file config/seed-data/production_seed.yml
```

## Script Issues

### Invalid Date Format

**Symptoms:**
```
ValueError: time data '03/15/2025' does not match format '%Y-%m-%d'
```

**Solution:**
Use ISO 8601 format: `YYYY-MM-DD`

```bash
# Correct
--date 2025-03-15
--march-start-time 2025-03-15T08:00:00

# Incorrect
--date 03/15/2025  # Wrong format
--date 15-03-2025  # Wrong format
```

### Script Not Executable

**Symptoms:**
```
bash: python: command not found
```

**Solutions:**

```bash
# 1. Check Python is installed
which python3
python3 --version

# 2. Use python3 explicitly
python3 scripts/add_participants.py --help

# 3. Create alias (add to ~/.bashrc)
alias python=python3

# 4. Make script executable
chmod +x scripts/add_participants.py
```

### Environment Variable Not Set

**Symptoms:**
```
Using default database URL: postgresql://postgres:password@localhost:5432/fitonduty_march
```

**Solution:**

```bash
# Set DATABASE_URL
export DATABASE_URL="postgresql://user:password@host:5432/fitonduty_march"

# Verify it's set
echo $DATABASE_URL

# Make permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export DATABASE_URL="postgresql://user:password@host:5432/fitonduty_march"' >> ~/.bashrc
source ~/.bashrc
```

## Performance Issues

### Slow Data Loading

**Symptoms:**
- Loading timeseries data takes very long
- Database becomes unresponsive

**Solutions:**

1. **Use batch inserts** (script already does this)
2. **Increase batch size** if needed
3. **Check database indexes:**

```sql
-- Verify indexes exist
\di march_timeseries_data*

-- Should show indexes on (march_id, user_id, timestamp_minutes)
```

4. **Disable constraints temporarily for large loads:**

```sql
-- Disable triggers
ALTER TABLE march_timeseries_data DISABLE TRIGGER ALL;

-- Load data
-- ... run load_march_data.py ...

-- Re-enable triggers
ALTER TABLE march_timeseries_data ENABLE TRIGGER ALL;
```

### Database Disk Space

**Symptoms:**
```
ERROR: could not extend file: No space left on device
```

**Solutions:**

```bash
# Check disk space
df -h

# Check database size
psql $DATABASE_URL -c "\l+"

# Check table sizes
psql $DATABASE_URL -c "\dt+"

# Clean up old data if needed
psql $DATABASE_URL << EOF
DELETE FROM march_timeseries_data
WHERE march_id IN (
  SELECT id FROM march_events WHERE date < '2024-01-01'
);
VACUUM FULL;
EOF
```

## Common SQL Queries for Debugging

```sql
-- Check participant count
SELECT role, COUNT(*) FROM users GROUP BY role;

-- Check groups and members
SELECT g.group_name, COUNT(ug.user_id) as members
FROM groups g
LEFT JOIN user_groups ug ON g.id = ug.group_id
GROUP BY g.group_name;

-- Check march events
SELECT id, name, date, status,
  (SELECT COUNT(*) FROM march_participants WHERE march_id = me.id) as participants
FROM march_events me
ORDER BY date DESC;

-- Check data for specific march
SELECT
  'Health Metrics' as table_name,
  COUNT(*) as record_count
FROM march_health_metrics
WHERE march_id = 1
UNION ALL
SELECT 'Timeseries Data', COUNT(*)
FROM march_timeseries_data
WHERE march_id = 1
UNION ALL
SELECT 'GPS Positions', COUNT(*)
FROM march_gps_positions
WHERE march_id = 1;

-- Check database connections
SELECT count(*), state
FROM pg_stat_activity
WHERE datname = 'fitonduty_march'
GROUP BY state;
```

## Getting More Help

### Enable Verbose Logging

```bash
# Python scripts
python -v scripts/load_march_data.py --data-dir ./output --march-id 1

# Ansible
ansible-playbook -i inventory/production.yml -vvv playbooks/march_database.yml

# PostgreSQL logging
# Edit postgresql.conf:
log_statement = 'all'
log_min_duration_statement = 0
```

### Check Logs

```bash
# PostgreSQL logs
ssh user@server 'sudo tail -f /var/log/postgresql/postgresql-16-main.log'

# System logs
ssh user@server 'sudo journalctl -u postgresql -f'

# Application logs
tail -f logs/dashboard.log
```

### Database Health Check

```bash
psql $DATABASE_URL << EOF
-- Check table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check indexes
SELECT
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Check active queries
SELECT pid, usename, state, query_start, query
FROM pg_stat_activity
WHERE datname = 'fitonduty_march'
  AND state != 'idle';
EOF
```

## Still Having Issues?

1. Check you're using the latest version
2. Review the relevant guide:
   - [Database Setup](./setup-database.md)
   - [Loading March Data](./guide-loading-data.md)
   - [Managing Participants](./guide-participants.md)
   - [Managing March Events](./guide-march-events.md)
3. Create an issue with:
   - Error message (full stack trace)
   - Steps to reproduce
   - Environment details (OS, Python version, PostgreSQL version)
   - Relevant configuration (sanitized, no passwords)
