#!/usr/bin/env python3
"""Backward-compatible wrapper for watch data processor.

This script maintains compatibility with the old path. The actual implementation
has been moved to src/processing/watch_processor.py.

Usage:
    python scripts/data/process_watch_data.py --data-dir /path --march-id 1

Or use the new CLI command directly:
    fitonduty-process-watch --data-dir /path --march-id 1
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.processing.watch_processor import main

if __name__ == "__main__":
    main()
