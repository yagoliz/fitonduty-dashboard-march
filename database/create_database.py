#!/usr/bin/env python3
"""
Database creation script for FitonDuty March Dashboard
Creates database and runs schema on existing PostgreSQL instance
"""

import argparse
import os
import sys

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def create_database(host, port, admin_user, admin_password, db_name):
    """Create database on PostgreSQL instance"""

    print(f"Creating database '{db_name}' on {host}:{port}...")

    try:
        # Connect to PostgreSQL instance (using postgres database)
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=admin_user,
            password=admin_password,
            database="postgres",  # Connect to default postgres db to create new db
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        cursor = conn.cursor()

        # Check if database already exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone()

        if exists:
            print(f"⚠️  Database '{db_name}' already exists")
            response = input(
                "Do you want to recreate it? This will delete all existing data! (y/N): "
            )
            if response.lower() != "y":
                print("❌ Aborted")
                return False

            # Drop existing database
            cursor.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))
            print(f"🗑️  Dropped existing database '{db_name}'")

        # Create new database
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        print(f"✅ Created database '{db_name}'")

        cursor.close()
        conn.close()

        return True

    except psycopg2.Error as e:
        print(f"❌ Error creating database: {e}")
        return False


def run_schema(host, port, user, password, db_name):
    """Run schema.sql on the created database"""

    print(f"Running schema on database '{db_name}'...")

    try:
        # Connect to the new database
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password, database=db_name
        )

        cursor = conn.cursor()

        # Read and execute schema file
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r") as f:
            schema_sql = f.read()

        # Execute schema (split by semicolon and filter empty statements)
        statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]
        for statement in statements:
            if statement and not statement.startswith("--"):
                cursor.execute(statement)

        conn.commit()
        cursor.close()
        conn.close()

        print("✅ Schema applied successfully")
        return True

    except psycopg2.Error as e:
        print(f"❌ Error running schema: {e}")
        return False
    except FileNotFoundError:
        print("❌ Schema file not found. Make sure 'schema.sql' exists in the database/ directory")
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Create FitonDuty March Dashboard database")
    parser.add_argument("--host", default="localhost", help="PostgreSQL host (default: localhost)")
    parser.add_argument("--port", default="5432", help="PostgreSQL port (default: 5432)")
    parser.add_argument(
        "--admin-user", default="postgres", help="Admin username (default: postgres)"
    )
    parser.add_argument("--admin-password", help="Admin password (will prompt if not provided)")
    parser.add_argument(
        "--db-name", default="fitonduty_march", help="Database name (default: fitonduty_march)"
    )
    parser.add_argument("--db-user", help="Database user (defaults to admin-user)")
    parser.add_argument("--db-password", help="Database password (defaults to admin-password)")

    args = parser.parse_args()

    # Prompt for admin password if not provided
    if not args.admin_password:
        import getpass

        args.admin_password = getpass.getpass(f"Enter password for {args.admin_user}@{args.host}: ")

    # Default database user/password to admin credentials if not specified
    db_user = args.db_user or args.admin_user
    db_password = args.db_password or args.admin_password

    print("🚀 FitonDuty March Dashboard Database Setup")
    print(f"Host: {args.host}:{args.port}")
    print(f"Database: {args.db_name}")
    print(f"User: {db_user}")
    print()

    # Create database
    if not create_database(
        args.host, args.port, args.admin_user, args.admin_password, args.db_name
    ):
        sys.exit(1)

    # Run schema
    if not run_schema(args.host, args.port, db_user, db_password, args.db_name):
        sys.exit(1)

    print("\n✅ Database setup complete!")
    print(
        "\nDatabase URL: postgresql://{db_user}:{db_password}@{args.host}:{args.port}/{args.db_name}"
    )
    print("\nNext steps:")
    print("1. Set DATABASE_URL environment variable:")
    print(
        "   export DATABASE_URL='postgresql://{db_user}:PASSWORD@{args.host}:{args.port}/{args.db_name}'"
    )
    print("2. Run seeding script: python database/seed_database.py")
    print("3. Start dashboard: python app.py")


if __name__ == "__main__":
    main()
