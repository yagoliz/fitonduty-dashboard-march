#!/usr/bin/env python3
"""
Create Database Schema Only (No Seed Data)

This script creates the database schema without seeding any test/mock data.
Use this for production environments where you will load real data separately.

Usage:
    export DATABASE_URL="postgresql://user:password@host:5432/dbname"
    python create_schema.py
"""

import os
import sys

from sqlalchemy import create_engine, text


def get_database_url():
    """Get database URL from environment or use default"""
    return os.environ.get(
        "DATABASE_URL", "postgresql://postgres:password@localhost:5432/fitonduty_march"
    )


def create_tables(engine):
    """Create all tables from schema"""
    print("Creating database tables...")

    # Read and execute schema file
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        schema_sql = f.read()

    with engine.connect() as conn:
        # Execute entire schema as one transaction first
        try:
            conn.execute(text(schema_sql))
            conn.commit()
            print("✓ Schema executed as single transaction")
        except Exception as e:
            print(f"Error executing schema as single block: {e}")
            print("Trying statement-by-statement execution...")

            # Rollback any partial transaction
            conn.rollback()

            # Fallback: execute statements individually, skip on error
            statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]
            successful_statements = 0
            skipped_statements = 0

            for statement in statements:
                if statement and not statement.startswith("--"):
                    try:
                        conn.execute(text(statement))
                        successful_statements += 1
                    except Exception as stmt_error:
                        if ("already exists" in str(stmt_error) or
                            "does not exist" in str(stmt_error) or
                            ("INDEX" in statement.upper() and "does not exist" in str(stmt_error))):
                            print(f"Skipping (expected): {stmt_error}")
                            skipped_statements += 1
                            continue
                        else:
                            print(f"Failed statement: {statement[:100]}...")
                            raise stmt_error

            conn.commit()
            print(f"✓ Executed {successful_statements} statements, skipped {skipped_statements}")

    print("✓ Tables created successfully")


def main():
    """Main schema creation function"""
    print("🚀 Creating database schema (no seed data)...")
    print(f"Database URL: {get_database_url()}")

    try:
        # Create engine and connect
        engine = create_engine(get_database_url())

        # Create tables only
        create_tables(engine)

        print("\n✅ Database schema created successfully!")
        print("\nNext steps:")
        print("  1. Add participants: python scripts/add_participants.py --seed-file config/seed-data/your_seed.yml")
        print("  2. Create march events: python scripts/manage_march_events.py create --interactive")
        print("  3. Load real march data: python scripts/load_march_data.py --data-dir ./output --march-id 1")

    except Exception as e:
        print(f"\n❌ Error creating schema: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()