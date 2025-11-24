# Managing March Events Guide

Complete guide for creating and managing march events in the database.

## Overview

March events are the core organizational unit - each event represents a physical march with metadata like date, distance, duration, and participating group. This guide covers:
- Creating march events
- Adding participants to marches
- Updating march status
- Listing and viewing marches

## Prerequisites

- Database is set up and running
- Participants have been added to the database
- Groups exist in the database

## Understanding March Events

### March Event Properties

- **Name**: Descriptive name (e.g., "Training March Alpha", "Endurance Test 2025-03")
- **Date**: March date (YYYY-MM-DD)
- **Distance**: Planned distance in kilometers
- **Duration**: Estimated duration in hours
- **Route**: Optional route description
- **Group**: Primary group for this march
- **Status**: Current march status

### March Status Flow

```
planned → completed → processing → published
```

- **planned**: March is scheduled but not yet conducted
- **completed**: March has been completed by participants
- **processing**: Data is being processed (optional intermediate state)
- **published**: Results are published and visible to participants

## Creating a March Event

### Method 1: Interactive Mode (Recommended)

```bash
python scripts/manage_march_events.py create --interactive
```

The script will prompt you for:

```
=== Create New March Event ===

Available groups:
  1. Squad Alpha - Alpha squad members
  2. Squad Bravo - Bravo squad members
  3. Squad Charlie - Charlie squad members

Select group (1-3): 1

March name: Training March Alpha
Date (YYYY-MM-DD): 2025-03-15
Planned distance (km): 8.2
Estimated duration (hours): 2.5
Route description (optional): Forest trail with moderate elevation
Status (planned/completed/processing/published) [planned]: planned

Confirm creation? (y/N): y

Creating march event...
Successfully created march event ID: 1

March Event: Training March Alpha
  ID: 1
  Date: 2025-03-15
  Distance: 8.2 km
  Duration: 2.5 hours
  Group: Squad Alpha
  Status: planned
  Route: Forest trail with moderate elevation
```

### Method 2: Command Line

Specify all parameters directly:

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

### With Custom Database

```bash
python scripts/manage_march_events.py create --interactive \
  --db-url postgresql://user:password@host:5432/dbname
```

## Adding Participants to March

After creating a march event, add participants:

### Add All Participants from March's Group

```bash
python scripts/manage_march_events.py add-participants --march-id 1
```

This adds all participants from the march's primary group.

### Add Participants from Specific Group

```bash
python scripts/manage_march_events.py add-participants \
  --march-id 1 \
  --group "Squad Bravo"
```

This adds all participants from the specified group (useful for cross-group marches).

### Example Output

```
Adding participants to march ID: 1

March: Training March Alpha (2025-03-15)
Group: Squad Alpha

Found participants:
  - SM001 (Squad Alpha)
  - SM002 (Squad Alpha)
  - SM003 (Squad Alpha)

Add these 3 participants? (y/N): y

Adding participants...
  Added SM001 to march
  Added SM002 to march
  Added SM003 to march

Successfully added 3 participants!
```

## Listing March Events

View all march events:

```bash
python scripts/manage_march_events.py list
```

Example output:

```
March Events:

ID: 1
  Name: Training March Alpha
  Date: 2025-03-15
  Distance: 8.2 km
  Duration: 2.5 hours
  Group: Squad Alpha
  Status: planned
  Participants: 3
  Route: Forest trail with moderate elevation

ID: 2
  Name: Endurance March
  Date: 2025-04-20
  Distance: 12.0 km
  Duration: 3.5 hours
  Group: Squad Bravo
  Status: completed
  Participants: 4
  Route: Hilly terrain route

Total: 2 march events
```

## Updating March Status

Update status after march completion or data processing:

### Mark as Completed

After the physical march is completed:

```bash
python scripts/manage_march_events.py update-status \
  --march-id 1 \
  --status completed
```

### Mark as Processing

While processing watch data:

```bash
python scripts/manage_march_events.py update-status \
  --march-id 1 \
  --status processing
```

### Publish Results

Make results visible to participants:

```bash
python scripts/manage_march_events.py update-status \
  --march-id 1 \
  --status published
```

## Typical Workflow

### Before March

```bash
# 1. Create march event
python scripts/manage_march_events.py create --interactive

# Example values:
#   Name: "Training March Alpha"
#   Date: 2025-03-15
#   Distance: 8.2 km
#   Duration: 2.5 hours
#   Group: Squad Alpha
#   Status: planned

# 2. Add participants
python scripts/manage_march_events.py add-participants --march-id 1

# 3. Verify
python scripts/manage_march_events.py list
```

### After March

```bash
# 1. Mark march as completed
python scripts/manage_march_events.py update-status --march-id 1 --status completed

# 2. Process watch data (see Loading March Data Guide)
python scripts/process_watch_data.py \
  --data-dir ./watch_exports \
  --march-id 1 \
  --march-start-time 2025-03-15T08:00:00 \
  --output ./output

# 3. Load processed data
python scripts/load_march_data.py \
  --data-dir ./output \
  --march-id 1

# 4. Publish results
python scripts/manage_march_events.py update-status --march-id 1 --status published
```

## Viewing March Details in Database

Connect to database and query march information:

```sql
-- List all march events
SELECT
  id,
  name,
  date,
  distance_km,
  duration_hours,
  status,
  g.group_name
FROM march_events me
LEFT JOIN groups g ON me.group_id = g.id
ORDER BY date DESC;

-- View participants for a specific march
SELECT
  me.name as march_name,
  u.username,
  mp.completed,
  mp.finish_time_minutes
FROM march_participants mp
JOIN march_events me ON mp.march_id = me.id
JOIN users u ON mp.user_id = u.id
WHERE mp.march_id = 1
ORDER BY u.username;

-- Count participants per march
SELECT
  me.id,
  me.name,
  me.date,
  COUNT(mp.user_id) as participant_count,
  SUM(CASE WHEN mp.completed THEN 1 ELSE 0 END) as completed_count
FROM march_events me
LEFT JOIN march_participants mp ON me.id = mp.march_id
GROUP BY me.id, me.name, me.date
ORDER BY me.date DESC;
```

## Advanced Operations

### Update March Details

```sql
-- Connect to database
psql $DATABASE_URL

-- Update march distance
UPDATE march_events
SET distance_km = 9.5
WHERE id = 1;

-- Update march date
UPDATE march_events
SET date = '2025-03-20'
WHERE id = 1;

-- Update route description
UPDATE march_events
SET route_description = 'Modified route with additional checkpoint'
WHERE id = 1;
```

### Remove Participant from March

```sql
-- Remove specific participant
DELETE FROM march_participants
WHERE march_id = 1
  AND user_id = (SELECT id FROM users WHERE username = 'SM001');
```

### Delete March Event

**WARNING:** This will delete all associated data (participants, metrics, timeseries, GPS data).

```sql
-- Delete march event (CASCADE will delete all related data)
DELETE FROM march_events WHERE id = 1;
```

### Clone March Event

Create a new march with same parameters:

```sql
INSERT INTO march_events (name, date, distance_km, duration_hours, group_id, status, route_description, created_by)
SELECT
  name || ' - Copy',
  '2025-04-15',  -- New date
  distance_km,
  duration_hours,
  group_id,
  'planned',  -- Reset status
  route_description,
  created_by
FROM march_events
WHERE id = 1;
```

## Environment Variables

Set database connection:

```bash
# Set environment variable
export DATABASE_URL="postgresql://fitonduty_march:password@host:5432/fitonduty_march"

# Or specify in each command
python scripts/manage_march_events.py create --interactive \
  --db-url postgresql://user:password@host:5432/dbname
```

## Troubleshooting

### Issue: "Group not found"

**Problem:** Specified group doesn't exist in database

**Solution:**
```bash
# List available groups
psql $DATABASE_URL -c "SELECT id, group_name FROM groups"

# Create missing group
psql $DATABASE_URL << EOF
INSERT INTO groups (group_name, description)
VALUES ('Squad Delta', 'Delta squad members');
EOF
```

### Issue: "No participants found"

**Problem:** No participants in specified group

**Solution:**
```bash
# Check participants in group
psql $DATABASE_URL << EOF
SELECT u.username, g.group_name
FROM users u
JOIN user_groups ug ON u.id = ug.user_id
JOIN groups g ON ug.group_id = g.id
WHERE g.group_name = 'Squad Alpha'
  AND u.role = 'participant';
EOF

# Add participants to group if needed
# See Managing Participants Guide
```

### Issue: "Participant already in march"

**Problem:** Trying to add duplicate participant to march

**Solution:**
This is not an error - the add-participants command is idempotent and skips existing assignments.

```sql
-- Check existing participants
SELECT u.username
FROM march_participants mp
JOIN users u ON mp.user_id = u.id
WHERE mp.march_id = 1;
```

### Issue: "Invalid date format"

**Problem:** Date not in correct format

**Solution:**
Use ISO 8601 format: `YYYY-MM-DD`

```bash
# Correct
--date 2025-03-15

# Incorrect
--date 03/15/2025  # Wrong
--date 15-03-2025  # Wrong
```

## Complete Example

```bash
# Set database connection
export DATABASE_URL="postgresql://fitonduty_march:password@server:5432/fitonduty_march"

# 1. List existing marches
python scripts/manage_march_events.py list

# 2. Create new march (interactive)
python scripts/manage_march_events.py create --interactive
# Enter:
#   Name: Spring Training March
#   Date: 2025-05-10
#   Distance: 10.5
#   Duration: 3.0
#   Group: Squad Alpha
#   Route: Cross-country route with elevation gain
#   Status: planned

# 3. Add participants from march's group
python scripts/manage_march_events.py add-participants --march-id 3

# 4. Add additional participants from another group
python scripts/manage_march_events.py add-participants --march-id 3 --group "Squad Bravo"

# 5. Verify march setup
psql $DATABASE_URL << EOF
SELECT
  me.name,
  COUNT(mp.user_id) as participants
FROM march_events me
LEFT JOIN march_participants mp ON me.id = mp.march_id
WHERE me.id = 3
GROUP BY me.name;
EOF

# 6. After march completion
python scripts/manage_march_events.py update-status --march-id 3 --status completed

# 7. After data processing
python scripts/manage_march_events.py update-status --march-id 3 --status published
```

## Next Steps

After creating march events:
1. **Before March:** Participants are ready, march is scheduled
2. **After March:** [Load March Data](./guide-loading-data.md) - Process and load watch data
3. **View Results:** Access dashboard to view performance analysis

## See Also

- [Managing Participants](./guide-participants.md) - Add participants and groups
- [Loading March Data](./guide-loading-data.md) - Process and load march data
- [Database Setup](./setup-database.md) - Database infrastructure
- [Scripts Reference](./reference-scripts.md) - Complete script documentation
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions