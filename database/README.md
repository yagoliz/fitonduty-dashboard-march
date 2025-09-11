# Database Setup

This directory contains scripts for setting up the FitonDuty March Dashboard database.

## Quick Setup

### Option 1: Automatic Setup (Recommended)

```bash
# Create database and run schema
python database/create_database.py --host localhost --admin-user postgres --db-name fitonduty_march

# Seed with sample data
python database/seed_database.py

# Set environment variable
export DATABASE_URL='postgresql://postgres:PASSWORD@localhost:5432/fitonduty_march'
```

### Option 2: Manual Setup

```bash
# 1. Create database manually in PostgreSQL
createdb -h localhost -U postgres fitonduty_march

# 2. Run schema
psql -h localhost -U postgres -d fitonduty_march -f database/schema.sql

# 3. Seed data
python database/seed_database.py

# 4. Set environment variable
export DATABASE_URL='postgresql://postgres:PASSWORD@localhost:5432/fitonduty_march'
```

## Files

- **`schema.sql`**: Database schema with all tables and indexes
- **`create_database.py`**: Automated database creation script
- **`seed_database.py`**: Sample data seeding script
- **`README.md`**: This file

## Database Schema Overview

### Core Tables
- `users` - User accounts (admin, participants)
- `groups` - User groups
- `user_groups` - User-group relationships
- `sessions` - Authentication sessions

### March Tables  
- `march_events` - March events with basic info
- `march_participants` - Participants in each march
- `march_health_metrics` - Summary physiological metrics
- `march_hr_zones` - Heart rate zone distributions
- `march_movement_speeds` - Movement speed breakdowns
- `march_timeseries_data` - Time-series HR/speed data during march

## Configuration

The database connection is configured via the `DATABASE_URL` environment variable:

```bash
export DATABASE_URL='postgresql://username:password@host:port/database_name'
```

Default: `postgresql://postgres:password@localhost:5432/fitonduty_march`

## Sample Data

The seeding script creates:
- 1 admin user, 4 participant users
- 1 training group
- 1 completed march with realistic time-series data
- 4 participants with different performance levels

### Test Credentials
- **Admin**: `admin` / `test123`
- **Participants**: `participant1-4` / `test123`

## Troubleshooting

### Connection Issues
- Ensure PostgreSQL is running
- Check host, port, username, and password
- Verify database exists and user has access

### Permission Issues
- Ensure user has CREATE DATABASE privileges for setup
- Ensure user has SELECT/INSERT/UPDATE privileges for operation

### Schema Issues
- Drop and recreate database if schema changes
- Check for conflicting table names in existing database