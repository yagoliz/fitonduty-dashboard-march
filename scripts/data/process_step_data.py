#!/usr/bin/env python3
"""Backward-compatible wrapper for step processor.

This script maintains compatibility with the old path. The actual implementation
has been moved to src/processing/step_processor.py.

Usage:
    python scripts/data/process_step_data.py --data-dir /path --march-id 1

Or use the new CLI command directly:
    fitonduty-process-steps --data-dir /path --march-id 1
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.processing.step_processor import main

if __name__ == "__main__":
    main()
