#!/usr/bin/env python3
"""Backward-compatible wrapper for data merger.

This script maintains compatibility with the old path. The actual implementation
has been moved to src/processing/data_merger.py.

Usage:
    python scripts/data/merge_march_data.py --input-dir /path

Or use the new CLI command directly:
    fitonduty-merge-data --input-dir /path
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.processing.data_merger import main

if __name__ == "__main__":
    main()
