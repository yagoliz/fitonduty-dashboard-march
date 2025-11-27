#!/usr/bin/env python3
"""
Add New Participants to Live March Dashboard Database

This script reads participants from a seed YAML file and adds only those
that don't already exist in the database, preserving existing data.

Usage:
    # With seed file:
    python add_participants.py --seed-file config/seed-data/march_2025_seed.yml

    # With direct database URL:
    python add_participants.py --seed-file config/seed-data/march_2025_seed.yml --db-url postgresql://user:pass@host:port/db

    # Dry run to see what would be added:
    python add_participants.py --seed-file config/seed-data/march_2025_seed.yml --dry-run
"""

import argparse
import os
import sys

import yaml
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash


def load_seed_file(seed_file_path):
    """Load seed file and extract participants and groups"""
    try:
        with open(seed_file_path, 'r') as f:
            seed_data = yaml.safe_load(f)

        if 'participants' not in seed_data:
            print("Error: No participants section found in seed file")
            return None, None

        participants = seed_data['participants']
        groups_data = seed_data.get('groups', [])
        admins_data = seed_data.get('admins', [])

        return participants, groups_data, admins_data

    except FileNotFoundError:
        print(f"Error: Seed file not found: {seed_file_path}")
        return None, None, None
    except yaml.YAMLError as e:
        print(f"Error parsing seed file: {e}")
        return None, None, None


def get_database_url(args):
    """Get database URL from arguments or environment"""
    if args.db_url:
        return args.db_url

    # Try environment variable
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        print("Using DATABASE_URL from environment")
        return db_url

    # Default to local development database
    default_url = "postgresql://postgres:password@localhost:5432/fitonduty_march"
    print(f"Using default database URL: {default_url}")
    return default_url


def create_db_engine(db_url):
    """Create database engine"""
    try:
        return create_engine(db_url)
    except Exception as e:
        print(f"Error creating database engine: {e}")
        sys.exit(1)


def get_existing_data(engine):
    """Get existing participants, groups, and admins from database"""
    try:
        with engine.connect() as conn:
            # Get existing participant usernames
            result = conn.execute(text("""
                SELECT username FROM users WHERE role = 'participant'
            """))
            existing_participants = {row[0] for row in result}

            # Get existing admin usernames
            result = conn.execute(text("""
                SELECT username FROM users WHERE role = 'admin'
            """))
            existing_admins = {row[0] for row in result}

            # Get existing groups with their IDs
            result = conn.execute(text("""
                SELECT id, group_name FROM groups
            """))
            existing_groups = {row[1]: row[0] for row in result}

            return existing_participants, existing_admins, existing_groups

    except Exception as e:
        print(f"Error querying database: {e}")
        sys.exit(1)


def filter_new_participants(seed_participants, existing_participants):
    """Filter out participants that already exist in database"""
    new_participants = []
    existing_count = 0

    for participant in seed_participants:
        username = participant['username']
        if username in existing_participants:
            existing_count += 1
            print(f"  ⏭️  Skipping {username} (already exists)")
        else:
            new_participants.append(participant)

    print(f"\nFound {len(seed_participants)} participants in seed file")
    print(f"Skipping {existing_count} existing participants")
    print(f"Will add {len(new_participants)} new participants")

    return new_participants


def filter_new_admins(seed_admins, existing_admins):
    """Filter out admins that already exist in database"""
    new_admins = []
    existing_count = 0

    for admin in seed_admins:
        username = admin['username']
        if username in existing_admins:
            existing_count += 1
            print(f"  ⏭️  Skipping admin {username} (already exists)")
        else:
            new_admins.append(admin)

    if seed_admins:
        print(f"\nFound {len(seed_admins)} admins in seed file")
        print(f"Skipping {existing_count} existing admins")
        print(f"Will add {len(new_admins)} new admins")

    return new_admins


def create_missing_groups(engine, seed_groups_data, existing_groups):
    """Create any missing groups from seed file"""
    if not seed_groups_data:
        return existing_groups

    missing_groups = []
    for group_data in seed_groups_data:
        group_name = group_data['name']
        if group_name not in existing_groups:
            missing_groups.append(group_data)

    if not missing_groups:
        return existing_groups

    print(f"\nCreating {len(missing_groups)} missing groups...")

    try:
        with engine.begin() as conn:
            # Get or create default admin user for created_by field
            admin_result = conn.execute(text("""
                SELECT id FROM users WHERE role = 'admin' LIMIT 1
            """))
            admin_row = admin_result.fetchone()

            if not admin_row:
                # Create a default admin if none exists
                print("No admin user found, creating default admin...")
                password_hash = generate_password_hash('admin')
                admin_result = conn.execute(text("""
                    INSERT INTO users (username, password_hash, role, is_active)
                    VALUES ('admin', :password_hash, 'admin', TRUE)
                    RETURNING id
                """), {'password_hash': password_hash})
                admin_id = admin_result.scalar()
                print("  ✓ Created default admin user")
            else:
                admin_id = admin_row[0]

            for group_data in missing_groups:
                group_name = group_data['name']
                description = group_data.get('description', f'March participant group for {group_name}')

                result = conn.execute(text("""
                    INSERT INTO groups (group_name, description, created_by)
                    VALUES (:group_name, :description, :created_by)
                    RETURNING id
                """), {
                    'group_name': group_name,
                    'description': description,
                    'created_by': admin_id
                })

                group_id = result.scalar()
                existing_groups[group_name] = group_id
                print(f"  ✓ Created group: {group_name}")

        return existing_groups

    except Exception as e:
        print(f"Error creating groups: {e}")
        sys.exit(1)


def add_admins_to_database(engine, new_admins):
    """Add new admin users to the database"""
    if not new_admins:
        return

    print(f"\nAdding {len(new_admins)} admin users to database...")

    try:
        with engine.begin() as conn:
            for admin in new_admins:
                username = admin['username']
                password = admin['password']

                password_hash = generate_password_hash(password)

                conn.execute(text("""
                    INSERT INTO users (username, password_hash, role, is_active)
                    VALUES (:username, :password_hash, 'admin', TRUE)
                """), {
                    'username': username,
                    'password_hash': password_hash
                })

                print(f"  ✓ Added admin: {username}")

        print(f"\n✅ Successfully added {len(new_admins)} admin users!")

    except Exception as e:
        print(f"Error adding admins: {e}")
        sys.exit(1)


def add_participants_to_database(engine, new_participants, existing_groups):
    """Add new participants to the database using passwords from seed file"""
    if not new_participants:
        print("\nNo new participants to add")
        return

    print(f"\nAdding {len(new_participants)} participants to database...")

    try:
        with engine.begin() as conn:
            for participant in new_participants:
                username = participant['username']
                password = participant['password']
                group_name = participant['groups']

                password_hash = generate_password_hash(password)

                # Get group ID
                if group_name not in existing_groups:
                    print(f"Error: Group '{group_name}' not found for participant {username}")
                    continue

                group_id = existing_groups[group_name]

                # Insert user
                user_result = conn.execute(text("""
                    INSERT INTO users (username, password_hash, role, is_active)
                    VALUES (:username, :password_hash, 'participant', TRUE)
                    RETURNING id
                """), {
                    'username': username,
                    'password_hash': password_hash
                })

                user_id = user_result.scalar()

                # Add to group
                conn.execute(text("""
                    INSERT INTO user_groups (user_id, group_id)
                    VALUES (:user_id, :group_id)
                """), {
                    'user_id': user_id,
                    'group_id': group_id
                })

                print(f"  ✓ Added {username} -> {group_name}")

        print(f"\n✅ Successfully added {len(new_participants)} participants!")

    except Exception as e:
        print(f"Error adding participants: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Add new participants to live march dashboard database from seed file')
    parser.add_argument('--seed-file', required=True, help='Path to seed YAML file')
    parser.add_argument('--db-url', help='Database connection URL (default: DATABASE_URL env var or local default)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')

    args = parser.parse_args()

    # Load seed file
    print(f"Loading seed file: {args.seed_file}")
    seed_participants, seed_groups, seed_admins = load_seed_file(args.seed_file)
    if seed_participants is None:
        sys.exit(1)

    # Get database URL and create engine
    db_url = get_database_url(args)
    engine = create_db_engine(db_url)

    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection successful\n")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # Get existing data
    existing_participants, existing_admins, existing_groups = get_existing_data(engine)
    print(f"Found {len(existing_participants)} existing participants in database")
    print(f"Found {len(existing_admins)} existing admins in database")
    print(f"Found {len(existing_groups)} existing groups: {', '.join(existing_groups.keys())}\n")

    # Filter out existing data
    new_participants = filter_new_participants(seed_participants, existing_participants)
    new_admins = filter_new_admins(seed_admins or [], existing_admins)

    if not new_participants and not new_admins:
        print("\n✅ All users from seed file already exist in database")
        sys.exit(0)

    # Show what will be added
    if new_admins:
        print(f"\nNew admins to add:")
        for a in new_admins:
            print(f"  - {a['username']}")

    if new_participants:
        print(f"\nNew participants to add:")
        for p in new_participants:
            print(f"  - {p['username']} -> {p['groups']}")

    if args.dry_run:
        print("\n🔍 DRY RUN - No changes will be made")
        print("Would create missing groups and add users as shown above")
        sys.exit(0)

    # Confirm before proceeding
    total_new = len(new_participants) + len(new_admins)
    response = input(f"\nProceed with adding {total_new} users to the live database? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled")
        sys.exit(0)

    # Create missing groups from seed file
    updated_groups = create_missing_groups(engine, seed_groups, existing_groups)

    # Add admins first
    add_admins_to_database(engine, new_admins)

    # Add participants
    add_participants_to_database(engine, new_participants, updated_groups)

    print("\n🎉 Database seeding completed successfully!")


if __name__ == '__main__':
    main()