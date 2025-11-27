#!/usr/bin/env python3
"""FitonDuty March Dashboard - Main Entry Point

This is a wrapper that imports and runs the dashboard from its new location
at src/app/main.py. The actual application code has been reorganized into
a proper package structure.

Usage:
    python app.py                          # Development mode
    gunicorn -b 0.0.0.0:8050 app:server    # Production mode
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the Dash app, Flask server, and User class from new location
from src.app.main import app, server, User

# For gunicorn and imports: expose the server and User class
__all__ = ['app', 'server', 'User']

if __name__ == "__main__":
    app.run(debug=True)
