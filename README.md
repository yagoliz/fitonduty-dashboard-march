# FitonDuty March Dashboard

A post-event analysis dashboard for long march physiological monitoring, focusing on pace analysis and performance comparisons.

## Overview

This dashboard provides detailed analysis of physiological data collected during military/training marches. Unlike real-time monitoring, data becomes available after participants hand in their measurement devices and the data is processed.

## Key Features

- **Individual March Analysis**: Personal performance breakdown with pace estimation
- **Group Comparisons**: Rankings and comparative analysis across participants  
- **Pace Calculator**: Speed estimation using movement algorithms (no GPS required)
- **Historical Tracking**: Performance progression over multiple marches
- **Heart Rate Analysis**: HR zones and effort scoring during marches

## Architecture

See `.claude/PLAN.md` for detailed architecture and implementation plans.

## Development

This project extends the existing FitonDuty infrastructure:
- Database: PostgreSQL (extends existing schema)
- Backend: Python + Dash (Flask-based)
- Processing: Integrates with fitonduty-processing pipeline
- Authentication: Uses existing user management system

## Getting Started

*Development setup instructions will be added as the project progresses.*