# Managing Participants Guide

Complete guide for adding and managing march participants.

## Overview

Participants are user accounts with login credentials who can view their own march results. This guide covers:
- Generating participant configurations
- Adding participants to the database
- Managing groups and permissions
- Updating participant information

## Prerequisites

- Database is set up and running
- You have the DATABASE_URL connection string

## Understanding Participants and Groups

### Users
User accounts with login credentials. Types:
- **Admin**: Full access, can view all data and manage system
- **Supervisor**: Can view all participants in their groups
- **Participant**: Can only view their own results

### Groups
Organizational units for participants (squads, units, teams). Each participant belongs to one or more groups.

### User Groups
Many-to-many relationship between users and groups. A participant can be in multiple groups.

## Method 1: Generate from CSV (Recommended)

### Step 1: Create Participants CSV

Create a CSV file with participant information:

```bash
cat > participants.csv << EOF
participant_id,group
SM001,Squad Alpha
SM002,Squad Alpha
SM003,Squad Bravo
SM004,Squad Bravo
SM005,Squad Charlie
EOF
```

CSV format:
- `participant_id`: Unique identifier for participant (will be their username)
- `group`: Group/squad name

### Step 2: Generate Seed Configuration

```bash
python scripts/generate_march_seed.py --csv participants.csv production
```

This creates `config/seed-data/production_seed.yml` with:
- Auto-generated secure passwords for all participants
- Group definitions
- Admin user account
- All participants assigned to their groups

Example output:
```yaml
admin:
  username: admin
  password: X7k9mP2nQ8vL5w
  role: admin

groups:
  - name: Squad Alpha
    description: Squad Alpha participants
  - name: Squad Bravo
    description: Squad Bravo participants

participants:
  - username: SM001
    password: aB3dE8fG1hI4jK
    group: Squad Alpha
  - username: SM002
    password: cD6eF9gH2iJ5kL
    group: Squad Alpha
```

### Step 3: Review and Customize

Edit the generated file if needed:

```bash
vim config/seed-data/production_seed.yml
```

You may want to:
- Change admin password
- Update group descriptions
- Customize passwords (optional, generated ones are secure)

### Step 4: Add to Database

```bash
export DATABASE_URL="postgresql://fitonduty_march:password@host:5432/fitonduty_march"

python scripts/add_participants.py --seed-file config/seed-data/production_seed.yml
```

The script will:
1. Show you what will be added
2. Ask for confirmation
3. Create groups (if they don't exist)
4. Add admin user (if it doesn't exist)
5. Add all participants

Example output:
```
Reading seed file: config/seed-data/production_seed.yml

Found:
  - 1 admin users
  - 3 groups
  - 5 participants

Connecting to database...
  Connected successfully

Checking existing data...
  Found 0 existing participants

Will add:
  Groups: Squad Alpha, Squad Bravo, Squad Charlie
  Admin: admin
  Participants: SM001, SM002, SM003, SM004, SM005

Proceed? (y/N): y

Adding groups...
  Created group: Squad Alpha
  Created group: Squad Bravo
  Created group: Squad Charlie

Adding admin users...
  Created admin: admin

Adding participants...
  Created participant: SM001 (Squad Alpha)
  Created participant: SM002 (Squad Alpha)
  Created participant: SM003 (Squad Bravo)
  Created participant: SM004 (Squad Bravo)
  Created participant: SM005 (Squad Charlie)

Successfully added 5 participants!
```

### Step 5: Save Credentials

**IMPORTANT:** Save the generated credentials securely!

```bash
# Keep the seed file secure
chmod 600 config/seed-data/production_seed.yml

# Or store in password manager
# Participants will need their username and password to login
```

## Method 2: Interactive Generation

Generate seed configuration interactively:

```bash
python scripts/generate_march_seed.py --interactive production
```

The script will prompt you for:
- Number of participants
- Participant IDs
- Group assignments
- Admin password

## Method 3: Manual YAML Creation

Create seed file manually:

```yaml
# config/seed-data/custom_seed.yml
admin:
  username: admin
  password: YourSecurePassword123
  role: admin

groups:
  - name: Team Alpha
    description: Alpha team members
  - name: Team Bravo
    description: Bravo team members

participants:
  - username: participant1
    password: SecurePass1
    group: Team Alpha
  - username: participant2
    password: SecurePass2
    group: Team Alpha
  - username: participant3
    password: SecurePass3
    group: Team Bravo
```

Then load it:
```bash
python scripts/add_participants.py --seed-file config/seed-data/custom_seed.yml
```

## Adding New Participants to Existing Campaign

### Option 1: Create New Seed File

```bash
# Create CSV with new participants only
cat > new_participants.csv << EOF
participant_id,group
SM006,Squad Alpha
SM007,Squad Bravo
EOF

# Generate new seed file
python scripts/generate_march_seed.py --csv new_participants.csv production_update

# Add to database (only new participants will be added)
python scripts/add_participants.py --seed-file config/seed-data/production_update_seed.yml
```

### Option 2: Update Existing Seed File

```bash
# Edit existing seed file
vim config/seed-data/production_seed.yml

# Add new participants to the participants list
# Then run add_participants.py again
python scripts/add_participants.py --seed-file config/seed-data/production_seed.yml
```

The script is smart - it only adds NEW participants and skips existing ones.

## Dry Run Mode

Preview changes without making them:

```bash
python scripts/add_participants.py \
  --seed-file config/seed-data/production_seed.yml \
  --dry-run
```

This shows what would be added without actually modifying the database.

## Custom Database URL

Specify a different database:

```bash
python scripts/add_participants.py \
  --seed-file config/seed-data/production_seed.yml \
  --db-url postgresql://user:password@different-host:5432/dbname
```

## Verifying Participants

Check participants were added:

```bash
psql $DATABASE_URL << EOF
-- List all participants
SELECT u.username, u.role, g.group_name
FROM users u
LEFT JOIN user_groups ug ON u.id = ug.user_id
LEFT JOIN groups g ON ug.group_id = g.id
WHERE u.role = 'participant'
ORDER BY u.username;

-- Count participants per group
SELECT g.group_name, COUNT(ug.user_id) as participant_count
FROM groups g
LEFT JOIN user_groups ug ON g.id = ug.group_id
GROUP BY g.group_name
ORDER BY g.group_name;
EOF
```

## Managing Participants

### Update Participant Password

```sql
-- Connect to database
psql $DATABASE_URL

-- Update password (hashed automatically by app)
UPDATE users
SET password = crypt('newpassword', gen_salt('bf'))
WHERE username = 'SM001';
```

Or use the application's admin interface.

### Move Participant to Different Group

```sql
-- Find group IDs
SELECT id, group_name FROM groups;

-- Update participant's group
UPDATE user_groups
SET group_id = 2  -- New group ID
WHERE user_id = (SELECT id FROM users WHERE username = 'SM001');
```

### Add Participant to Additional Group

```sql
-- Add to second group (participant can be in multiple groups)
INSERT INTO user_groups (user_id, group_id)
SELECT u.id, g.id
FROM users u, groups g
WHERE u.username = 'SM001'
  AND g.group_name = 'Squad Bravo';
```

### Disable Participant

```sql
-- Add an 'active' flag or delete user
DELETE FROM users WHERE username = 'SM001';

-- Or soft delete (add 'active' column to schema first)
UPDATE users SET active = false WHERE username = 'SM001';
```

## Security Best Practices

### 1. Secure Password Generation

The generator uses `secrets.token_urlsafe(12)` which creates cryptographically secure random passwords.

### 2. Protect Seed Files

```bash
# Set restrictive permissions
chmod 600 config/seed-data/*.yml

# Add to .gitignore (should already be there)
echo "config/seed-data/*_seed.yml" >> .gitignore

# Store in secure vault for production
ansible-vault encrypt config/seed-data/production_seed.yml
```

### 3. Password Distribution

Distribute passwords securely:
- Use encrypted email
- Hand deliver printed copies
- Use password management system
- Never send passwords in plain text

### 4. Force Password Change

Implement password change on first login (in application code):
```python
if user.first_login:
    redirect('/change-password')
```

## Troubleshooting

### Issue: "Database connection failed"

**Problem:** Can't connect to database

**Solution:**
```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check DATABASE_URL is correct
echo $DATABASE_URL

# Verify database is running
ssh user@server 'sudo systemctl status postgresql'
```

### Issue: "Group does not exist"

**Problem:** Participant references non-existent group

**Solution:**
The script automatically creates groups. If you see this error, check:
```bash
# Verify seed file format
cat config/seed-data/production_seed.yml | grep -A 2 "groups:"

# Ensure groups are defined before participants
```

### Issue: "Participant already exists"

**Problem:** Trying to add duplicate participant

**Solution:**
This is not an error - the script skips existing participants. If you need to update:
```sql
-- Delete and re-add
DELETE FROM users WHERE username = 'SM001';
-- Then run add_participants.py again
```

### Issue: "Permission denied"

**Problem:** Database user lacks permissions

**Solution:**
```sql
-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fitonduty_march;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fitonduty_march;
```

## Complete Example

```bash
# 1. Create participant list
cat > participants.csv << EOF
participant_id,group
A001,Squad Alpha
A002,Squad Alpha
A003,Squad Alpha
B001,Squad Bravo
B002,Squad Bravo
C001,Squad Charlie
EOF

# 2. Generate seed configuration
python scripts/generate_march_seed.py --csv participants.csv campaign_2025

# 3. Review and save credentials
cat config/seed-data/campaign_2025_seed.yml
# Copy to password manager or secure location

# 4. Dry run to preview
export DATABASE_URL="postgresql://fitonduty_march:password@server:5432/fitonduty_march"
python scripts/add_participants.py \
  --seed-file config/seed-data/campaign_2025_seed.yml \
  --dry-run

# 5. Add to database
python scripts/add_participants.py \
  --seed-file config/seed-data/campaign_2025_seed.yml

# 6. Verify
psql $DATABASE_URL -c "SELECT username, role FROM users WHERE role='participant'"

# 7. Secure the seed file
chmod 600 config/seed-data/campaign_2025_seed.yml
```

## Next Steps

After adding participants:
1. [Create March Events](./guide-march-events.md) - Define your marches
2. [Load March Data](./guide-loading-data.md) - Load march performance data
3. Access dashboard and verify participant logins

## See Also

- [Database Setup](./setup-database.md) - Set up database infrastructure
- [Managing March Events](./guide-march-events.md) - Create marches and assign participants
- [Scripts Reference](./reference-scripts.md) - Complete script documentation
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions