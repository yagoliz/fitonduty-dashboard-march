#!/usr/bin/env python3
"""
Manage March Events in Live Database

This script allows you to create, update, and manage march events in the database.

Usage:
    # Create a new march event:
    python manage_march_events.py create --name "Training March Alpha" --date 2025-03-15 --distance 8.2 --duration 2.5 --group "Squad A"

    # Create march event interactively:
    python manage_march_events.py create --interactive

    # List all march events:
    python manage_march_events.py list

    # Update march event status:
    python manage_march_events.py update-status --march-id 1 --status completed

    # Add participants to a march:
    python manage_march_events.py add-participants --march-id 1 --group "Squad A"

    # With custom database URL:
    python manage_march_events.py create --db-url postgresql://user:pass@host:port/db --interactive
"""

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, text


def get_database_url(args):
    """Get database URL from arguments or environment"""
    if hasattr(args, 'db_url') and args.db_url:
        return args.db_url

    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        print("Using DATABASE_URL from environment")
        return db_url

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


def get_groups(engine):
    """Get all groups from database"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, group_name, description FROM groups ORDER BY group_name
            """))
            return [{'id': row[0], 'name': row[1], 'description': row[2]} for row in result]
    except Exception as e:
        print(f"Error fetching groups: {e}")
        return []


def get_admin_user_id(engine):
    """Get admin user ID for created_by field"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id FROM users WHERE role = 'admin' LIMIT 1
            """))
            row = result.fetchone()
            if row:
                return row[0]
            return None
    except Exception as e:
        print(f"Error fetching admin user: {e}")
        return None


def create_march_interactive(engine):
    """Create a march event interactively"""
    print("\n=== Create New March Event ===\n")

    # Get groups
    groups = get_groups(engine)
    if not groups:
        print("Error: No groups found in database. Please create groups first.")
        return False

    print("Available groups:")
    for i, group in enumerate(groups, 1):
        print(f"  {i}. {group['name']} - {group['description']}")

    # Get march details from user
    name = input("\nMarch event name: ").strip()
    if not name:
        print("Error: March name is required")
        return False

    date_str = input("March date (YYYY-MM-DD): ").strip()
    try:
        march_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        print("Error: Invalid date format. Use YYYY-MM-DD")
        return False

    distance_str = input("Distance (km): ").strip()
    try:
        distance_km = float(distance_str) if distance_str else None
    except ValueError:
        print("Error: Invalid distance")
        return False

    duration_str = input("Duration (hours): ").strip()
    try:
        duration_hours = float(duration_str) if duration_str else None
    except ValueError:
        print("Error: Invalid duration")
        return False

    route_description = input("Route description (optional): ").strip() or None

    group_idx_str = input(f"\nSelect group (1-{len(groups)}): ").strip()
    try:
        group_idx = int(group_idx_str) - 1
        if group_idx < 0 or group_idx >= len(groups):
            print("Error: Invalid group selection")
            return False
        group_id = groups[group_idx]['id']
    except ValueError:
        print("Error: Invalid group number")
        return False

    status = input("Status (planned/completed/processing/published) [planned]: ").strip() or 'planned'
    if status not in ['planned', 'completed', 'processing', 'published']:
        print("Error: Invalid status")
        return False

    # Confirm
    print(f"\n📋 March Event Summary:")
    print(f"  Name: {name}")
    print(f"  Date: {march_date}")
    print(f"  Distance: {distance_km} km")
    print(f"  Duration: {duration_hours} hours")
    print(f"  Route: {route_description or 'N/A'}")
    print(f"  Group: {groups[group_idx]['name']}")
    print(f"  Status: {status}")

    confirm = input("\nCreate this march event? (y/N): ").lower()
    if confirm != 'y':
        print("Cancelled")
        return False

    # Create march
    return create_march(
        engine, name, march_date, distance_km, duration_hours,
        route_description, group_id, status
    )


def create_march(engine, name, date, distance_km, duration_hours, route_description, group_id, status='planned'):
    """Create a march event in the database"""
    try:
        admin_id = get_admin_user_id(engine)
        if not admin_id:
            print("Error: No admin user found in database")
            return False

        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO march_events
                (name, date, distance_km, duration_hours, route_description, group_id, status, created_by)
                VALUES (:name, :date, :distance_km, :duration_hours, :route_description, :group_id, :status, :created_by)
                RETURNING id
            """), {
                'name': name,
                'date': date,
                'distance_km': distance_km,
                'duration_hours': duration_hours,
                'route_description': route_description,
                'group_id': group_id,
                'status': status,
                'created_by': admin_id
            })

            march_id = result.scalar()
            print(f"\n✅ Successfully created march event (ID: {march_id})")
            return True

    except Exception as e:
        print(f"Error creating march event: {e}")
        return False


def list_marches(engine):
    """List all march events"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    me.id,
                    me.name,
                    me.date,
                    me.distance_km,
                    me.duration_hours,
                    me.status,
                    g.group_name,
                    COUNT(mp.user_id) as participant_count
                FROM march_events me
                LEFT JOIN groups g ON me.group_id = g.id
                LEFT JOIN march_participants mp ON me.id = mp.march_id
                GROUP BY me.id, me.name, me.date, me.distance_km, me.duration_hours, me.status, g.group_name
                ORDER BY me.date DESC
            """))

            marches = result.fetchall()

            if not marches:
                print("\nNo march events found in database")
                return

            print("\n📋 March Events:\n")
            print(f"{'ID':<5} {'Name':<30} {'Date':<12} {'Distance':<10} {'Duration':<10} {'Status':<12} {'Group':<20} {'Participants':<12}")
            print("-" * 120)

            for march in marches:
                march_id, name, date, distance, duration, status, group_name, participant_count = march
                distance_str = f"{distance} km" if distance else "N/A"
                duration_str = f"{duration} hrs" if duration else "N/A"
                group_str = group_name or "N/A"

                print(f"{march_id:<5} {name:<30} {str(date):<12} {distance_str:<10} {duration_str:<10} {status:<12} {group_str:<20} {participant_count:<12}")

    except Exception as e:
        print(f"Error listing march events: {e}")


def update_march_status(engine, march_id, new_status):
    """Update the status of a march event"""
    valid_statuses = ['planned', 'completed', 'processing', 'published']
    if new_status not in valid_statuses:
        print(f"Error: Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return False

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE march_events
                SET status = :status
                WHERE id = :march_id
                RETURNING id, name
            """), {
                'march_id': march_id,
                'status': new_status
            })

            row = result.fetchone()
            if not row:
                print(f"Error: March event with ID {march_id} not found")
                return False

            print(f"✅ Updated march '{row[1]}' status to '{new_status}'")
            return True

    except Exception as e:
        print(f"Error updating march status: {e}")
        return False


def add_participants_to_march(engine, march_id, group_name=None):
    """Add participants from a group to a march event"""
    try:
        with engine.begin() as conn:
            # Verify march exists
            march_result = conn.execute(text("""
                SELECT me.id, me.name, g.id as group_id, g.group_name
                FROM march_events me
                LEFT JOIN groups g ON me.group_id = g.id
                WHERE me.id = :march_id
            """), {'march_id': march_id})

            march_row = march_result.fetchone()
            if not march_row:
                print(f"Error: March event with ID {march_id} not found")
                return False

            march_name = march_row[1]
            march_group_id = march_row[2]
            march_group_name = march_row[3]

            # Determine which group to use
            if group_name:
                group_result = conn.execute(text("""
                    SELECT id FROM groups WHERE group_name = :group_name
                """), {'group_name': group_name})
                group_row = group_result.fetchone()
                if not group_row:
                    print(f"Error: Group '{group_name}' not found")
                    return False
                target_group_id = group_row[0]
                target_group_name = group_name
            elif march_group_id:
                target_group_id = march_group_id
                target_group_name = march_group_name
            else:
                print("Error: No group specified and march has no associated group")
                return False

            # Get participants from group
            participants_result = conn.execute(text("""
                SELECT u.id, u.username
                FROM users u
                JOIN user_groups ug ON u.id = ug.user_id
                WHERE ug.group_id = :group_id AND u.role = 'participant'
                ORDER BY u.username
            """), {'group_id': target_group_id})

            participants = participants_result.fetchall()

            if not participants:
                print(f"No participants found in group '{target_group_name}'")
                return False

            print(f"\nAdding {len(participants)} participants from group '{target_group_name}' to march '{march_name}':")

            added_count = 0
            skipped_count = 0

            for user_id, username in participants:
                # Check if already added
                check_result = conn.execute(text("""
                    SELECT 1 FROM march_participants
                    WHERE march_id = :march_id AND user_id = :user_id
                """), {'march_id': march_id, 'user_id': user_id})

                if check_result.fetchone():
                    print(f"  ⏭️  Skipping {username} (already added)")
                    skipped_count += 1
                    continue

                # Add participant
                conn.execute(text("""
                    INSERT INTO march_participants (march_id, user_id, completed, start_offset_minutes)
                    VALUES (:march_id, :user_id, false, 0)
                """), {'march_id': march_id, 'user_id': user_id})

                print(f"  ✓ Added {username}")
                added_count += 1

            print(f"\n✅ Added {added_count} participants, skipped {skipped_count} existing")
            return True

    except Exception as e:
        print(f"Error adding participants to march: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Manage march events in the database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--db-url', help='Database connection URL')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create march
    create_parser = subparsers.add_parser('create', help='Create a new march event')
    create_parser.add_argument('--interactive', action='store_true', help='Interactive mode')
    create_parser.add_argument('--name', help='March event name')
    create_parser.add_argument('--date', help='March date (YYYY-MM-DD)')
    create_parser.add_argument('--distance', type=float, help='Distance in km')
    create_parser.add_argument('--duration', type=float, help='Duration in hours')
    create_parser.add_argument('--route', help='Route description')
    create_parser.add_argument('--group', help='Group name')
    create_parser.add_argument('--status', default='planned', choices=['planned', 'completed', 'processing', 'published'])

    # List marches
    list_parser = subparsers.add_parser('list', help='List all march events')

    # Update status
    status_parser = subparsers.add_parser('update-status', help='Update march event status')
    status_parser.add_argument('--march-id', type=int, required=True, help='March event ID')
    status_parser.add_argument('--status', required=True, choices=['planned', 'completed', 'processing', 'published'])

    # Add participants
    participants_parser = subparsers.add_parser('add-participants', help='Add participants to a march')
    participants_parser.add_argument('--march-id', type=int, required=True, help='March event ID')
    participants_parser.add_argument('--group', help='Group name (optional, uses march group if not specified)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Get database connection
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

    # Execute command
    if args.command == 'create':
        if args.interactive:
            create_march_interactive(engine)
        else:
            if not all([args.name, args.date, args.group]):
                print("Error: --name, --date, and --group are required for non-interactive mode")
                sys.exit(1)

            try:
                march_date = datetime.strptime(args.date, '%Y-%m-%d').date()
            except ValueError:
                print("Error: Invalid date format. Use YYYY-MM-DD")
                sys.exit(1)

            # Get group ID
            groups = get_groups(engine)
            group = next((g for g in groups if g['name'] == args.group), None)
            if not group:
                print(f"Error: Group '{args.group}' not found")
                sys.exit(1)

            create_march(
                engine, args.name, march_date, args.distance, args.duration,
                args.route, group['id'], args.status
            )

    elif args.command == 'list':
        list_marches(engine)

    elif args.command == 'update-status':
        update_march_status(engine, args.march_id, args.status)

    elif args.command == 'add-participants':
        add_participants_to_march(engine, args.march_id, args.group)


if __name__ == '__main__':
    main()