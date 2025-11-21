# GPS Route Visualization for March Dashboard

This document describes the GPS route tracking and visualization features added to the march dashboard.

## Overview

The march dashboard now supports displaying GPS routes from watch data (GPX files), allowing you to visualize:
- Individual participant routes on an interactive map
- Multiple participant routes for comparison
- Elevation profiles with ascent/descent statistics
- Speed variation along the route

## Database Schema

A new table `march_gps_positions` has been added to store GPS track data:

```sql
CREATE TABLE march_gps_positions (
    id SERIAL PRIMARY KEY,
    march_id INTEGER REFERENCES march_events(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    timestamp_minutes NUMERIC(8,2) NOT NULL,  -- Minutes from march start
    latitude NUMERIC(10,7) NOT NULL,          -- Decimal degrees
    longitude NUMERIC(10,7) NOT NULL,         -- Decimal degrees
    elevation NUMERIC(6,2),                   -- Meters
    speed_kmh NUMERIC(4,2),                   -- km/h from GPS
    bearing NUMERIC(5,2),                     -- Direction in degrees
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Processing Watch Data with GPS

### Script Updates

The `process_watch_data.py` script has been updated to:
1. Parse GPX files for GPS coordinates
2. Calculate distance and speed from GPS tracks using Haversine formula
3. Extract elevation data
4. Save GPS positions to a separate CSV file for database import

### Usage

```bash
cd fitonduty-dashboard-march/scripts

# Process watch data including GPS
python process_watch_data.py \
  --data-dir /path/to/watch/data \
  --march-id 1 \
  --march-start-time 2024-07-21T08:00:00 \
  --output ./output
```

### Output Files

The script generates these CSV files:
- `march_health_metrics.csv` - Aggregate metrics
- `march_hr_zones.csv` - Heart rate zones
- `march_timeseries_data.csv` - Time-series physiological data
- **`march_gps_positions.csv`** - GPS track coordinates (new)

### CSV Format for GPS Positions

```csv
march_id,user_id,timestamp_minutes,latitude,longitude,elevation,speed_kmh
1,SM001,0.0,40.712776,-74.005974,10.5,0.0
1,SM001,0.02,40.712856,-74.006054,10.8,4.2
1,SM001,0.04,40.712936,-74.006134,11.1,4.5
...
```

## Database Query Functions

New functions in `utils/database.py`:

### Get Single Participant Route

```python
from utils.database import get_march_gps_track

gps_data = get_march_gps_track(march_id=1, user_id=123)
# Returns DataFrame with: timestamp_minutes, latitude, longitude, elevation, speed_kmh, bearing
```

### Get All Participant Routes

```python
from utils.database import get_march_all_gps_tracks

all_routes = get_march_all_gps_tracks(march_id=1)
# Returns DataFrame with: user_id, username, timestamp_minutes, latitude, longitude, elevation, speed_kmh
```

## Visualization Components

New module: `utils/visualization/march_route_map.py`

### Individual Route Map

```python
from utils.visualization.march_route_map import create_march_route_map
from utils.database import get_march_gps_track

# Get GPS data
gps_data = get_march_gps_track(march_id=1, user_id=123)

# Create map
fig = create_march_route_map(gps_data, participant_name="John Doe")
```

**Features:**
- Interactive OpenStreetMap with zoom/pan
- Color gradient showing speed or time
- Start marker (green) and finish marker (red)
- Hover info showing lat/lon, elevation, speed, time
- Auto-zoom to fit route

### Multi-Participant Route Map

```python
from utils.visualization.march_route_map import create_multi_participant_route_map
from utils.database import get_march_all_gps_tracks

# Get all GPS tracks
all_routes = get_march_all_gps_tracks(march_id=1)

# Create comparison map
fig = create_multi_participant_route_map(all_routes)
```

**Features:**
- Different color for each participant
- All routes on same map for comparison
- Start markers for each route
- Legend with participant names

### Elevation Profile

```python
from utils.visualization.march_route_map import create_elevation_profile
from utils.database import get_march_gps_track

# Get GPS data
gps_data = get_march_gps_track(march_id=1, user_id=123)

# Create elevation profile
fig = create_elevation_profile(gps_data, participant_name="John Doe")
```

**Features:**
- Elevation vs distance (or time if distance unavailable)
- Area chart with gradient
- Statistics: max elevation, min elevation, total ascent, total descent
- Hover tooltips

## Integration with Dashboard

### Adding Map to Participant Detail View

Update `components/march/participant_detail.py`:

```python
from utils.database import get_march_gps_track
from utils.visualization.march_route_map import create_march_route_map, create_elevation_profile

def create_participant_detail_view(march_id: int, user_id: int) -> html.Div:
    # ... existing code ...

    # Get GPS track data
    gps_data = get_march_gps_track(march_id, user_id)

    # Create map and elevation profile
    if not gps_data.empty:
        route_map = create_march_route_map(gps_data, summary_data.get('username', 'Participant'))
        elevation_chart = create_elevation_profile(gps_data, summary_data.get('username', 'Participant'))

        # Add to layout
        map_row = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5([
                            html.I(className="fas fa-map me-2"),
                            "Route Map"
                        ], className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Graph(figure=route_map, config={'displayModeBar': False})
                    ])
                ])
            ], width=12, lg=8),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5([
                            html.I(className="fas fa-mountain me-2"),
                            "Elevation Profile"
                        ], className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Graph(figure=elevation_chart, config={'displayModeBar': False})
                    ])
                ])
            ], width=12, lg=4)
        ], className="mb-4")
```

## Data Import Process

### 1. Process Watch Data

```bash
python scripts/process_watch_data.py \
  --data-dir /path/to/watch_data \
  --march-id 1 \
  --march-start-time "2024-07-21T08:00:00" \
  --output ./march_output
```

### 2. Import to Database

Using PostgreSQL `COPY` command:

```bash
# Import GPS positions
psql -h localhost -U postgres -d fitonduty_march -c "\
  COPY march_gps_positions (march_id, user_id, timestamp_minutes, latitude, longitude, elevation, speed_kmh) \
  FROM '/path/to/march_output/march_gps_positions.csv' \
  DELIMITER ',' CSV HEADER;"
```

Or use a Python import script:

```python
import pandas as pd
from sqlalchemy import create_engine

# Read CSV
gps_df = pd.read_csv('march_output/march_gps_positions.csv')

# Map participant IDs to user IDs (you need this mapping)
user_mapping = {
    'SM001': 10,
    'SM002': 11,
    # ...
}
gps_df['user_id'] = gps_df['user_id'].map(user_mapping)

# Import to database
engine = create_engine('postgresql://postgres:password@localhost:5432/fitonduty_march')
gps_df.to_sql('march_gps_positions', engine, if_exists='append', index=False)
```

## Requirements

### Python Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies ...
    "gpxpy>=1.5.0",  # For GPX file parsing
]
```

Install:

```bash
uv pip install gpxpy
```

### Database Migration

If you already have an existing database, run this migration:

```sql
-- Add GPS positions table
CREATE TABLE IF NOT EXISTS march_gps_positions (
    id SERIAL PRIMARY KEY,
    march_id INTEGER REFERENCES march_events(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    timestamp_minutes NUMERIC(8,2) NOT NULL,
    latitude NUMERIC(10,7) NOT NULL,
    longitude NUMERIC(10,7) NOT NULL,
    elevation NUMERIC(6,2),
    speed_kmh NUMERIC(4,2),
    bearing NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_march_gps_march_user
  ON march_gps_positions(march_id, user_id);
CREATE INDEX IF NOT EXISTS idx_march_gps_timestamp
  ON march_gps_positions(march_id, user_id, timestamp_minutes);

-- Add comments
COMMENT ON TABLE march_gps_positions
  IS 'GPS track data from watch exports for route visualization';
COMMENT ON COLUMN march_gps_positions.timestamp_minutes
  IS 'Minutes elapsed from march start (fractional for high-frequency GPS data)';
```

## Features Summary

- **Interactive Maps**: Pan, zoom, and explore routes on OpenStreetMap
- **Speed Visualization**: Color-coded routes showing speed variation
- **Elevation Profiles**: See terrain challenges with ascent/descent stats
- **Multi-Participant Comparison**: Overlay multiple routes to compare paths
- **Start/Finish Markers**: Clear indication of route endpoints
- **Data Quality**: GPS data at original sampling rate (typically 1 Hz)
- **Responsive Design**: Maps work on desktop and mobile devices

## Performance Considerations

- GPS data can be large (1 point per second = 14,400 points for 4-hour march)
- Consider downsampling for display if needed:
  ```python
  # Downsample to 1 point every 10 seconds
  gps_data_display = gps_data.iloc[::10]
  ```
- Database indexes optimize queries for march_id and user_id
- Use map zoom limits to prevent excessive data loading

## Troubleshooting

### No GPS data showing

1. Check if GPX files exist in watch data folder
2. Verify `gpxpy` is installed: `pip list | grep gpxpy`
3. Check processing script logs for GPX parsing errors
4. Verify GPS data was imported to database:
   ```sql
   SELECT COUNT(*) FROM march_gps_positions WHERE march_id = 1;
   ```

### Map not displaying

1. Ensure Plotly is installed and up to date
2. Check browser console for JavaScript errors
3. Verify internet connection (needed for OpenStreetMap tiles)

### Participant ID mapping issues

- Create a mapping file to convert watch IDs (SM001) to database user IDs
- Update import script to use this mapping before database insert

## Next Steps

1. **Update schema.sql** if you're creating a fresh database
2. **Run migration** if you have an existing database
3. **Install gpxpy**: `uv pip install gpxpy`
4. **Process watch data** with the updated script
5. **Import GPS data** to database
6. **Add map component** to participant detail view
7. **Test visualization** with real march data

## Example Integration

See the complete example in `components/march/participant_detail.py` showing how to:
- Fetch GPS data from database
- Create route map and elevation profile
- Add maps to the dashboard layout
- Handle cases where GPS data is not available