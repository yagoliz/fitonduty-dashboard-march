#!/usr/bin/env python3
"""Backward-compatible wrapper for squad filler.

The actual implementation lives in src/processing/squad_filler.py.

Usage:
    python scripts/data/fill_non_watch_data.py \
        --output-dir ./.output/20260413 \
        --station-dir /data/20260410_march/admin_march_2026_04_10/station_march_2026_04_10 \
        --participants-csv config/seed-data/participants_2026.csv \
        --march-id 1
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.processing.squad_filler import main

if __name__ == "__main__":
    main()