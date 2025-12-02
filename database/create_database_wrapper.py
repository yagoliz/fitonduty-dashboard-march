#!/usr/bin/env python3
"""Backward-compatible wrapper for database creation script.

This script maintains compatibility with the old path. The actual implementation
has been moved to src/database/management/create_database.py.

Usage:
    python database/create_database_wrapper.py --host localhost --port 5432

Or use the new path directly:
    python src/database/management/create_database.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import and run main from new location
if __name__ == "__main__":
    from src.database.management.create_database import main
    main()
