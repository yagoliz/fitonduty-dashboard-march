-- FitonDuty March Dashboard Database Schema
-- Self-contained schema for march dashboard

-- Core tables (simplified from main FitonDuty system for self-contained operation)

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'participant', 'supervisor')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Groups Table
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    group_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id)
);

-- User-Group Relationship Table
CREATE TABLE IF NOT EXISTS user_groups (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, group_id)
);

-- Sessions Table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- March Events Table
CREATE TABLE IF NOT EXISTS march_events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    duration_hours NUMERIC(4,2), -- Actual march duration
    distance_km NUMERIC(5,2), -- If available from pace estimation
    route_description TEXT,
    group_id INTEGER REFERENCES groups(id),
    status VARCHAR(20) DEFAULT 'planned' CHECK (status IN ('planned', 'completed', 'processing', 'published')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id)
);

-- March Participants
CREATE TABLE IF NOT EXISTS march_participants (
    march_id INTEGER REFERENCES march_events(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    completed BOOLEAN DEFAULT false,
    start_offset_minutes INTEGER DEFAULT 0, -- If participants started at different times
    finish_time_minutes INTEGER, -- Minutes from march start to finish
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (march_id, user_id)
);

-- March Health Metrics (aggregate march performance)
CREATE TABLE IF NOT EXISTS march_health_metrics (
    id SERIAL PRIMARY KEY,
    march_id INTEGER REFERENCES march_events(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    -- Overall march stats
    avg_hr INTEGER,
    max_hr INTEGER,
    total_steps INTEGER,
    march_duration_minutes INTEGER,
    -- March-specific metrics
    estimated_distance_km NUMERIC(5,2), -- From pace algorithms
    avg_pace_kmh NUMERIC(4,2), -- Average pace during march
    effort_score NUMERIC(5,2), -- Calculated effort metric
    recovery_hr INTEGER, -- HR 10 mins post-march
    data_completeness NUMERIC(3,2), -- % of march with valid data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (march_id, user_id)
);

-- March Heart Rate Zones (for entire march duration)
CREATE TABLE IF NOT EXISTS march_hr_zones (
    id SERIAL PRIMARY KEY,
    march_health_metric_id INTEGER REFERENCES march_health_metrics(id) ON DELETE CASCADE UNIQUE,
    very_light_percent NUMERIC(5,2),
    light_percent NUMERIC(5,2),
    moderate_percent NUMERIC(5,2),
    intense_percent NUMERIC(5,2),
    beast_mode_percent NUMERIC(5,2),
    CHECK (
        (very_light_percent + light_percent + moderate_percent + intense_percent + 
        beast_mode_percent) BETWEEN 99.0 AND 101.0
    )
);

-- March Movement Speeds (time spent in different movement categories)
CREATE TABLE IF NOT EXISTS march_movement_speeds (
    id SERIAL PRIMARY KEY,
    march_health_metric_id INTEGER REFERENCES march_health_metrics(id) ON DELETE CASCADE UNIQUE,
    walking_minutes INTEGER DEFAULT 0,
    walking_fast_minutes INTEGER DEFAULT 0,
    jogging_minutes INTEGER DEFAULT 0,
    running_minutes INTEGER DEFAULT 0,
    stationary_minutes INTEGER DEFAULT 0 -- Rest periods
);

-- March Time-Series Data (physiological data during march progression)
CREATE TABLE IF NOT EXISTS march_timeseries_data (
    id SERIAL PRIMARY KEY,
    march_id INTEGER REFERENCES march_events(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    timestamp_minutes INTEGER NOT NULL, -- Minutes from march start
    heart_rate INTEGER,
    step_rate INTEGER, -- Steps per minute
    estimated_speed_kmh NUMERIC(4,2), -- Estimated speed from movement algorithms
    cumulative_steps INTEGER,
    cumulative_distance_km NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (march_id, user_id, timestamp_minutes)
);

-- March GPS Positions (GPS track data from watch exports)
CREATE TABLE IF NOT EXISTS march_gps_positions (
    id SERIAL PRIMARY KEY,
    march_id INTEGER REFERENCES march_events(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    timestamp_minutes NUMERIC(8,2) NOT NULL, -- Minutes from march start (can be fractional)
    latitude NUMERIC(10,7) NOT NULL, -- Latitude in decimal degrees
    longitude NUMERIC(10,7) NOT NULL, -- Longitude in decimal degrees
    elevation NUMERIC(6,2), -- Elevation in meters
    speed_kmh NUMERIC(4,2), -- Instantaneous speed from GPS
    bearing NUMERIC(5,2), -- Direction of travel in degrees (0-360)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_march_events_group_date ON march_events(group_id, date);
CREATE INDEX IF NOT EXISTS idx_march_events_status ON march_events(status);
CREATE INDEX IF NOT EXISTS idx_march_participants_march ON march_participants(march_id);
CREATE INDEX IF NOT EXISTS idx_march_participants_user ON march_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_march_health_metrics_march_user ON march_health_metrics(march_id, user_id);
CREATE INDEX IF NOT EXISTS idx_march_timeseries_march_user ON march_timeseries_data(march_id, user_id);
CREATE INDEX IF NOT EXISTS idx_march_timeseries_timestamp ON march_timeseries_data(march_id, user_id, timestamp_minutes);
CREATE INDEX IF NOT EXISTS idx_march_gps_march_user ON march_gps_positions(march_id, user_id);
CREATE INDEX IF NOT EXISTS idx_march_gps_timestamp ON march_gps_positions(march_id, user_id, timestamp_minutes);

-- Comments for documentation
COMMENT ON TABLE users IS 'User accounts with role-based access';
COMMENT ON TABLE groups IS 'User groups for organizing participants';
COMMENT ON TABLE march_events IS 'March events with basic information and status';
COMMENT ON TABLE march_participants IS 'Participants assigned to march events';
COMMENT ON TABLE march_health_metrics IS 'Aggregate physiological metrics for each participant per march';
COMMENT ON TABLE march_hr_zones IS 'Heart rate zone distribution during march';
COMMENT ON TABLE march_movement_speeds IS 'Time spent in different movement speed categories';

COMMENT ON COLUMN march_events.status IS 'planned: event created, completed: march finished, processing: data being processed, published: results available';
COMMENT ON COLUMN march_participants.start_offset_minutes IS 'Minutes delay from official march start time';
COMMENT ON COLUMN march_participants.finish_time_minutes IS 'Total time from march start to finish';
COMMENT ON COLUMN march_health_metrics.effort_score IS 'Calculated effort metric similar to Strava suffer score';
COMMENT ON COLUMN march_health_metrics.data_completeness IS 'Percentage of march duration with valid sensor data';

COMMENT ON TABLE march_timeseries_data IS 'Time-series physiological data during march for progress visualization';
COMMENT ON COLUMN march_timeseries_data.timestamp_minutes IS 'Minutes elapsed from march start (0 = start time)';
COMMENT ON COLUMN march_timeseries_data.step_rate IS 'Steps per minute at this timestamp';
COMMENT ON COLUMN march_timeseries_data.estimated_speed_kmh IS 'Estimated movement speed from pace algorithms';

COMMENT ON TABLE march_gps_positions IS 'GPS track data from watch exports for route visualization';
COMMENT ON COLUMN march_gps_positions.timestamp_minutes IS 'Minutes elapsed from march start (fractional for high-frequency GPS data)';
COMMENT ON COLUMN march_gps_positions.latitude IS 'Latitude coordinate in decimal degrees (WGS84)';
COMMENT ON COLUMN march_gps_positions.longitude IS 'Longitude coordinate in decimal degrees (WGS84)';
COMMENT ON COLUMN march_gps_positions.bearing IS 'Direction of travel in degrees where 0/360=North, 90=East, 180=South, 270=West';