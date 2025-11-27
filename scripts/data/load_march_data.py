#!/usr/bin/env python3
"""Backward-compatible wrapper for data loader.

This script maintains compatibility with the old path. The actual implementation
has been moved to src/processing/data_loader.py.

Usage:
    python scripts/data/load_march_data.py --data-dir /path --march-id 1

Or use the new CLI command directly:
    fitonduty-load-data --data-dir /path --march-id 1
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.processing.data_loader import main

if __name__ == "__main__":
    main()
