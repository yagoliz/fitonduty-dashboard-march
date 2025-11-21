#!/usr/bin/env python3
"""
March Dashboard Seed Data Generator

This script generates seed data configuration files for march dashboard
based on either:
1. CSV file with columns: participant_id, group
2. Interactive input

Usage:
    # From CSV file:
    python generate_march_seed.py --csv participants.csv march_2025

    # With custom output path:
    python generate_march_seed.py --csv participants.csv march_2025 --output config/seed-data/march_2025.yml

    # Interactive mode:
    python generate_march_seed.py march_2025 --interactive
"""

import argparse
import csv
import secrets
import string
import sys
from datetime import datetime
from pathlib import Path

import yaml


def generate_password(length=12):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def generate_admin_password(length=16):
    """Generate a secure admin password"""
    return generate_password(length)


def scan_csv_file(csv_path):
    """
    Read participants and groups from CSV file

    Args:
        csv_path (str): Path to CSV file with columns: participant_id, group

    Returns:
        dict: Dictionary with groups and their participants
    """
    csv_file = Path(csv_path)

    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")

    structure = {}

    try:
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            sample = file.read(1024)
            file.seek(0)

            sniffer = csv.Sniffer()
            has_header = sniffer.has_header(sample)

            reader = csv.reader(file)

            if has_header:
                header = next(reader)
                print(f"📋 Detected CSV header: {header}")

            for row_num, row in enumerate(reader, start=2 if has_header else 1):
                if len(row) < 2:
                    print(f"Warning: Row {row_num} has insufficient columns, skipping: {row}")
                    continue

                participant_id = row[0].strip()
                group_name = row[1].strip()

                if not participant_id or not group_name:
                    print(f"Warning: Row {row_num} has empty values, skipping: {row}")
                    continue

                if group_name not in structure:
                    structure[group_name] = []

                if participant_id not in structure[group_name]:
                    structure[group_name].append(participant_id)
                else:
                    print(f"Warning: Duplicate participant '{participant_id}' in group '{group_name}', skipping")

    except Exception as e:
        raise Exception(f"Error reading CSV file: {e}")

    return structure


def interactive_input():
    """Get participants and groups interactively from user"""
    print("\n=== Interactive Seed Data Configuration ===\n")
    structure = {}

    while True:
        group_name = input("\nEnter group name (or press Enter to finish): ").strip()
        if not group_name:
            break

        if group_name in structure:
            print(f"Group '{group_name}' already exists. Adding more participants to it.")
        else:
            structure[group_name] = []

        print(f"\nAdding participants to group '{group_name}':")
        print("Enter participant IDs one per line (press Enter with empty line to finish group)")

        while True:
            participant_id = input("  Participant ID: ").strip()
            if not participant_id:
                break

            if participant_id in structure[group_name]:
                print(f"  Warning: Participant '{participant_id}' already in this group")
            else:
                structure[group_name].append(participant_id)
                print(f"  ✓ Added {participant_id}")

    return structure


def create_seed_config(campaign_name, directory_structure, admin_username="admin"):
    """
    Create the seed configuration dictionary

    Args:
        campaign_name (str): Name of the campaign (e.g., 'march_2025')
        directory_structure (dict): Groups and participants from scanning
        admin_username (str): Username for the admin user

    Returns:
        dict: Complete seed configuration
    """

    admin_password = generate_admin_password()

    config = {
        'database': {
            'name': f'fitonduty_march_{campaign_name}'
        },
        'admins': [
            {
                'username': admin_username,
                'password': admin_password
            }
        ],
        'groups': [],
        'participants': []
    }

    # Add groups
    for group_name in directory_structure.keys():
        group_config = {
            'name': group_name,
            'description': f'March participant group for {group_name}',
            'created_by': admin_username
        }
        config['groups'].append(group_config)

    # Add participants
    for group_name, participants in directory_structure.items():
        for participant_name in participants:
            participant_password = generate_password()

            participant_config = {
                'username': participant_name,
                'password': participant_password,
                'groups': group_name,
                'role': 'participant'
            }
            config['participants'].append(participant_config)

    return config


def save_seed_config(config, output_path):
    """
    Save the seed configuration to a YAML file

    Args:
        config (dict): The seed configuration
        output_path (str): Path where to save the file
    """
    output_file = Path(output_path)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    header_comment = f"""# March Dashboard Seed Data Configuration
# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Campaign: {config.get('database', {}).get('name', 'unknown')}
#
# IMPORTANT SECURITY NOTES:
# 1. All passwords in this file are auto-generated
# 2. Change admin password before production use
# 3. Keep this file secure and never commit to public repositories
# 4. Consider using encryption for production environments
#
"""

    with open(output_file, 'w') as f:
        f.write(header_comment)
        yaml.dump(config, f, default_flow_style=False, indent=2, sort_keys=False)

    print(f"✓ Seed configuration saved to: {output_file}")


def print_summary(config, campaign_name):
    """Print a summary of the generated configuration"""

    total_groups = len(config['groups'])
    total_participants = len(config['participants'])

    print(f"\n📊 Configuration Summary for {campaign_name}:")
    print(f"   └── Admin users: {len(config['admins'])}")
    print(f"   └── Groups: {total_groups}")
    print(f"   └── Participants: {total_participants}")

    print("\n🔐 Generated Credentials:")
    for admin in config['admins']:
        print(f"   Admin '{admin['username']}': {admin['password']}")

    print("\n📁 Group Structure:")
    for group in config['groups']:
        group_name = group['name']
        group_participants = [p['username'] for p in config['participants'] if p['groups'] == group_name]
        print(f"   📂 {group_name} ({len(group_participants)} participants)")
        for participant in group_participants[:3]:
            print(f"      └── {participant}")
        if len(group_participants) > 3:
            print(f"      └── ... and {len(group_participants) - 3} more")

    print("\n⚠️  SECURITY REMINDER:")
    print("   • Change the admin password before production use")
    print("   • Keep this configuration file secure")
    print("   • Store securely and never commit passwords to version control")


def main():
    parser = argparse.ArgumentParser(
        description="Generate march dashboard seed data from CSV or interactive input",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
INPUT SOURCES:
  --csv FILE          CSV file with columns: participant_id, group
  --interactive       Interactive input mode

CSV FORMAT:
  participant_id,group
  p1,Group A
  p2,Group A
  p3,Group B

Examples:
  %(prog)s --csv participants.csv march_2025
  %(prog)s --interactive march_2025
  %(prog)s --csv participants.csv march_2025 --output config/seed-data/march_2025.yml
        """
    )

    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        '--csv', '-c',
        help='CSV file with participant_id,group columns'
    )
    input_group.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Interactive input mode'
    )

    parser.add_argument(
        'campaign_name',
        help='Name of the campaign (e.g., march_2025)'
    )

    parser.add_argument(
        '--output', '-o',
        help='Output file path (default: ./config/seed-data/{campaign_name}_seed.yml)',
        default=None
    )

    parser.add_argument(
        '--admin-user',
        help='Admin username (default: admin)',
        default='admin'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be generated without creating files'
    )

    args = parser.parse_args()

    try:
        if args.output:
            output_path = args.output
        else:
            script_dir = Path(__file__).parent
            config_dir = script_dir.parent / 'config' / 'seed-data'
            output_path = config_dir / f'{args.campaign_name}_seed.yml'

        # Get directory structure
        if args.csv:
            print(f"📊 Reading participants from CSV file: {args.csv}")
            directory_structure = scan_csv_file(args.csv)
        elif args.interactive:
            directory_structure = interactive_input()
        else:
            print("Error: Must specify either --csv or --interactive")
            sys.exit(1)

        if not directory_structure:
            print("❌ No groups with participants found")
            sys.exit(1)

        print(f"✓ Found {len(directory_structure)} groups")

        print(f"🏗️  Generating seed configuration for {args.campaign_name}")
        config = create_seed_config(
            args.campaign_name,
            directory_structure,
            args.admin_user
        )

        print_summary(config, args.campaign_name)

        if args.dry_run:
            print(f"\n🔍 DRY RUN - Configuration would be saved to: {output_path}")
            print("\nTo actually generate the file, run without --dry-run")
        else:
            print("\n💾 Saving configuration...")
            save_seed_config(config, output_path)
            print("\n✅ March seed data generated successfully!")
            print(f"\nNext steps:")
            print(f"1. Review the generated file: {output_path}")
            print(f"2. Customize passwords and settings as needed")
            print(f"3. Use with: python scripts/add_participants.py --seed-file {output_path}")

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()