#!/usr/bin/env python3
"""
Simplified database seeding script for FitonDuty March Dashboard
Creates one completed march with time-series data for development testing
"""

import math
import os
import random
from datetime import date

from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash


def get_database_url():
    """Get database URL from environment or use default"""
    return os.environ.get(
        "DATABASE_URL", "postgresql://postgres:password@localhost:5432/fitonduty_march"
    )


def create_tables(engine):
    """Create all tables from schema"""
    print("Creating database tables...")

    # Read and execute schema file
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        schema_sql = f.read()

    with engine.connect() as conn:
        # Execute entire schema as one transaction first
        try:
            conn.execute(text(schema_sql))
            conn.commit()
            print("✓ Schema executed as single transaction")
        except Exception as e:
            print(f"Error executing schema as single block: {e}")
            print("Trying statement-by-statement execution...")

            # Rollback any partial transaction
            conn.rollback()

            # Fallback: execute statements individually, skip on error
            statements = [stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()]
            successful_statements = 0
            skipped_statements = 0

            for statement in statements:
                if statement and not statement.startswith("--"):
                    try:
                        conn.execute(text(statement))
                        successful_statements += 1
                    except Exception as stmt_error:
                        if ("already exists" in str(stmt_error) or
                            "does not exist" in str(stmt_error) or
                            ("INDEX" in statement.upper() and "does not exist" in str(stmt_error))):
                            print(f"Skipping (expected): {stmt_error}")
                            skipped_statements += 1
                            continue
                        else:
                            print(f"Failed statement: {statement[:100]}...")
                            raise stmt_error

            conn.commit()
            print(f"✓ Executed {successful_statements} statements, skipped {skipped_statements}")

    print("✓ Tables created successfully")


def seed_basic_data(conn):
    """Create test users, group, and single march event"""
    print("Seeding basic data...")

    # Create password hash for all test users (password: test123)
    password_hash = generate_password_hash("test123")

    # Insert users - keep it simple
    users_data = [
        {"username": "admin", "role": "admin"},
        {"username": "participant1", "role": "participant"},
        {"username": "participant2", "role": "participant"},
        {"username": "participant3", "role": "participant"},
        {"username": "participant4", "role": "participant"},
    ]

    # Insert users first
    for user_data in users_data:
        conn.execute(
            text("""
            INSERT INTO users (username, password_hash, role) 
            VALUES (:username, :password_hash, :role)
            ON CONFLICT (username) DO NOTHING
        """),
            {**user_data, "password_hash": password_hash},
        )

    # Commit users before creating groups to ensure foreign key constraint is satisfied
    conn.commit()

    # Get the admin user ID to use as created_by
    result = conn.execute(
        text("SELECT id FROM users WHERE username = 'admin'")
    )
    admin_user_id = result.fetchone()[0]

    # Create one group with the correct admin user ID
    conn.execute(
        text("""
        INSERT INTO groups (group_name, description, created_by) 
        VALUES ('Training Squad', 'Main training group for march testing', :admin_id)
        ON CONFLICT (group_name) DO NOTHING
    """),
        {"admin_id": admin_user_id}
    )

    # Commit the group creation before proceeding
    conn.commit()

    # Get the group ID dynamically
    result = conn.execute(
        text("SELECT id FROM groups WHERE group_name = 'Training Squad'")
    )
    group_id = result.fetchone()[0]

    # Get participant user IDs dynamically
    result = conn.execute(
        text("SELECT id FROM users WHERE role = 'participant' ORDER BY id")
    )
    participant_ids = [row[0] for row in result.fetchall()]

    # Assign participants to group using dynamic group_id
    for user_id in participant_ids:
        conn.execute(
            text("""
            INSERT INTO user_groups (user_id, group_id) 
            VALUES (:user_id, :group_id)
            ON CONFLICT (user_id, group_id) DO NOTHING
        """),
            {"user_id": user_id, "group_id": group_id},
        )

    # Create one completed march using dynamic group_id and admin_user_id
    conn.execute(
        text("""
        INSERT INTO march_events (name, date, duration_hours, distance_km, route_description, group_id, status, created_by)
        VALUES ('Training March Alpha', :march_date, 2.5, 8.2, 'Forest trail with moderate elevation - completed march', :group_id, 'published', :admin_id)
    """),
        {"march_date": date(2024, 3, 15), "group_id": group_id, "admin_id": admin_user_id},
    )

    print("✓ Basic data seeded")


def generate_gps_track(user_id, duration_minutes, distance_km):
    """Generate realistic GPS track data for a participant"""

    # Starting position (example location - adjust to your needs)
    # These coordinates are for a forest area, adjust to your actual march location
    base_lat = 40.7128 + (user_id % 4) * 0.001  # Slightly different start for each participant
    base_lon = -74.0060 + (user_id % 4) * 0.001

    gps_data = []

    # Set random seed for consistent routes per user
    random.seed(user_id * 100)

    # Calculate points (every 30 seconds for smoother routes)
    num_points = duration_minutes * 2  # 2 points per minute

    # Route parameters
    bearing = random.uniform(0, 360)  # Initial direction
    elevation = 100 + random.uniform(-10, 10)  # Starting elevation

    for i in range(num_points):
        progress = i / num_points

        # Time in minutes (fractional)
        timestamp_minutes = (i * 0.5)  # 0.5 minutes = 30 seconds

        # Calculate movement
        # Distance per point (km)
        point_distance = (distance_km / num_points) * (1.0 + random.uniform(-0.1, 0.1))

        # Bearing changes (simulate turns and terrain following)
        bearing_change = random.uniform(-15, 15) + 5 * math.sin(progress * 8 * math.pi)
        bearing = (bearing + bearing_change) % 360

        # Convert bearing and distance to lat/lon change
        # Approximate: 1 degree lat ≈ 111 km, 1 degree lon ≈ 111 km * cos(lat)
        lat_change = point_distance * math.cos(math.radians(bearing)) / 111.0
        lon_change = point_distance * math.sin(math.radians(bearing)) / (111.0 * math.cos(math.radians(base_lat)))

        base_lat += lat_change
        base_lon += lon_change

        # Elevation changes (simulate terrain)
        elevation_change = random.uniform(-2, 2) + 3 * math.sin(progress * 6 * math.pi)
        elevation += elevation_change
        elevation = max(50, min(300, elevation))  # Keep elevation reasonable

        # Calculate speed (km/h) from distance and time
        speed_kmh = (point_distance / (0.5 / 60))  # distance / time_in_hours
        speed_kmh = max(0.5, min(8.0, speed_kmh))  # Reasonable marching speed

        gps_data.append({
            'timestamp_minutes': round(timestamp_minutes, 2),
            'latitude': round(base_lat, 7),
            'longitude': round(base_lon, 7),
            'elevation': round(elevation, 2),
            'speed_kmh': round(speed_kmh, 2),
            'bearing': round(bearing, 2)
        })

    return gps_data


def generate_march_timeseries(user_id, duration_minutes, distance_km):
    """Generate realistic time-series data for a participant during march"""

    # Participant characteristics (based on user_id for consistency)
    random.seed(user_id * 42)  # Consistent randomness per user
    base_fitness = 0.7 + (user_id % 4) * 0.1  # 0.7 to 1.0
    base_hr = 60 + random.randint(5, 15)  # Resting HR
    max_hr = 200 - (user_id * 5)  # Age-based max HR
    base_core_temp = 36.5 + random.uniform(-0.2, 0.2)  # Normal resting core temp

    timeseries_data = []

    # Generate data points every 5 minutes
    for minute in range(0, duration_minutes + 1, 5):
        progress = minute / duration_minutes if duration_minutes > 0 else 0

        # Heart rate progression (starts moderate, peaks in middle, recovers slightly at end)
        hr_intensity = 0.5 + 0.3 * math.sin(progress * math.pi) + 0.1 * random.random()
        hr_intensity = max(0.4, min(0.9, hr_intensity))  # Keep in reasonable range
        heart_rate = int(base_hr + (max_hr - base_hr) * hr_intensity * (1.1 - base_fitness * 0.2))

        # Core body temperature (increases with exertion, influenced by HR and duration)
        # Temperature rises gradually during march, peaks mid-way, slight decrease at end
        temp_increase = 1.5 * hr_intensity * (1.0 - base_fitness * 0.3)  # Fitter people regulate better
        temp_variation = 0.15 * math.sin(progress * 2 * math.pi) + random.uniform(-0.1, 0.1)
        core_temp = base_core_temp + temp_increase + temp_variation
        core_temp = max(36.0, min(39.5, core_temp))  # Keep in physiological range

        # Step rate (varies with terrain and fatigue)
        terrain_factor = 1.0 + 0.2 * math.sin(progress * 4 * math.pi)  # Terrain variations
        fatigue_factor = 1.0 - 0.15 * progress  # Gradual slowdown
        base_step_rate = 110 + random.randint(-10, 10)
        step_rate = int(base_step_rate * terrain_factor * fatigue_factor * base_fitness)

        # Estimated speed (correlated with step rate and HR)
        speed_base = 3.0 + base_fitness * 1.5  # Base speed 3-4.5 km/h
        speed_variation = 0.5 * math.sin(progress * 3 * math.pi) * terrain_factor
        estimated_speed = max(
            0.5, speed_base + speed_variation - 0.8 * progress
        )  # Slow down over time

        # Cumulative metrics
        if minute == 0:
            cumulative_steps = 0
            cumulative_distance = 0.0
        else:
            steps_this_interval = step_rate * 5  # 5 minutes
            distance_this_interval = estimated_speed * (5 / 60)  # 5 minutes in hours
            cumulative_steps = cumulative_steps + steps_this_interval
            cumulative_distance = cumulative_distance + distance_this_interval

        timeseries_data.append(
            {
                "timestamp_minutes": minute,
                "heart_rate": heart_rate,
                "step_rate": step_rate,
                "estimated_speed_kmh": round(estimated_speed, 2),
                "cumulative_steps": int(cumulative_steps),
                "cumulative_distance_km": round(cumulative_distance, 2),
                "core_temp": round(core_temp, 2),
            }
        )

    return timeseries_data


def calculate_summary_metrics(timeseries_data, duration_minutes):
    """Calculate summary metrics from time-series data"""

    if not timeseries_data:
        return None

    # Heart rate metrics
    hr_values = [d["heart_rate"] for d in timeseries_data if d["heart_rate"]]
    avg_hr = int(sum(hr_values) / len(hr_values)) if hr_values else 0
    max_hr = max(hr_values) if hr_values else 0

    # Core temperature metrics
    temp_values = [d["core_temp"] for d in timeseries_data if d.get("core_temp")]
    avg_core_temp = round(sum(temp_values) / len(temp_values), 2) if temp_values else 37.0

    # Final cumulative values
    final_data = timeseries_data[-1]
    total_steps = final_data["cumulative_steps"]
    estimated_distance = final_data["cumulative_distance_km"]
    avg_pace = (estimated_distance / (duration_minutes / 60.0)) if duration_minutes > 0 else 0

    # Effort score (simple calculation based on HR intensity and duration)
    effort_score = (avg_hr / 180.0) * (duration_minutes / 60.0) * 100 * random.uniform(0.9, 1.1)

    # Recovery HR (estimate)
    recovery_hr = int(avg_hr * random.uniform(0.7, 0.85))

    # HR zones (simplified distribution based on avg HR)
    hr_max_est = max_hr * 1.05  # Estimate max HR
    zone_thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]  # Zone boundaries as % of max HR

    zone_counts = [0] * 5
    for data_point in timeseries_data:
        hr = data_point["heart_rate"]
        hr_percent = hr / hr_max_est if hr_max_est > 0 else 0

        zone_idx = 0
        for i, threshold in enumerate(zone_thresholds):
            if hr_percent >= threshold:
                zone_idx = i
        zone_counts[zone_idx] += 1

    # Convert to percentages
    total_points = sum(zone_counts)
    hr_zones = [count / total_points * 100 if total_points > 0 else 0 for count in zone_counts]

    # Movement speed analysis (simplified)
    avg_speed = sum(d["estimated_speed_kmh"] for d in timeseries_data) / len(timeseries_data)
    walking_ratio = 0.6 if avg_speed < 3.5 else 0.4
    walking_fast_ratio = 0.3 if avg_speed < 4.0 else 0.5
    jogging_ratio = 0.1 if avg_speed > 4.0 else 0.05

    movement_speeds = {
        "walking_minutes": int(duration_minutes * walking_ratio),
        "walking_fast_minutes": int(duration_minutes * walking_fast_ratio),
        "jogging_minutes": int(duration_minutes * jogging_ratio),
        "running_minutes": int(duration_minutes * 0.05),
        "stationary_minutes": int(duration_minutes * 0.05),
    }

    return {
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "avg_core_temp": avg_core_temp,
        "total_steps": total_steps,
        "estimated_distance_km": round(estimated_distance, 2),
        "avg_pace_kmh": round(avg_pace, 2),
        "effort_score": round(effort_score, 1),
        "recovery_hr": recovery_hr,
        "data_completeness": 0.95,  # Assume good data quality
        "hr_zones": hr_zones,
        "movement_speeds": movement_speeds,
    }


def seed_march_data(conn):
    """Create march participants with realistic time-series and summary data"""
    print("Seeding march performance data...")

    # Get the march ID dynamically
    result = conn.execute(
        text("SELECT id FROM march_events WHERE name = 'Training March Alpha'")
    )
    march_id = result.fetchone()[0]

    # Get participant user IDs dynamically
    result = conn.execute(
        text("SELECT id FROM users WHERE role = 'participant' ORDER BY id")
    )
    participant_ids = [row[0] for row in result.fetchall()]

    # Create participant performance data with varying durations
    durations = [140, 155, 170, 145]  # good, average, slower, good performance
    participants = []
    for i, user_id in enumerate(participant_ids[:4]):  # Use up to 4 participants
        duration = durations[i] if i < len(durations) else 150  # Default duration
        participants.append({"user_id": user_id, "duration": duration})

    for participant in participants:
        user_id = participant["user_id"]
        duration_minutes = participant["duration"]
        distance_km = 8.2  # Fixed distance for this march

        # Add participant record
        conn.execute(
            text("""
            INSERT INTO march_participants (march_id, user_id, completed, start_offset_minutes, finish_time_minutes)
            VALUES (:march_id, :user_id, true, :start_offset, :finish_time)
        """),
            {
                "march_id": march_id,
                "user_id": user_id,
                "start_offset": random.randint(0, 3),
                "finish_time": duration_minutes,
            },
        )

        # Generate time-series data
        timeseries_data = generate_march_timeseries(user_id, duration_minutes, distance_km)

        # Calculate summary metrics
        summary_metrics = calculate_summary_metrics(timeseries_data, duration_minutes)

        # Insert summary health metrics
        conn.execute(
            text("""
            INSERT INTO march_health_metrics
            (march_id, user_id, avg_hr, max_hr, avg_core_temp, total_steps, march_duration_minutes,
             estimated_distance_km, avg_pace_kmh, effort_score, recovery_hr, data_completeness)
            VALUES (:march_id, :user_id, :avg_hr, :max_hr, :avg_core_temp, :total_steps, :march_duration_minutes,
                    :estimated_distance_km, :avg_pace_kmh, :effort_score, :recovery_hr, :data_completeness)
        """),
            {
                "march_id": march_id,
                "user_id": user_id,
                "march_duration_minutes": duration_minutes,
                **{
                    k: v
                    for k, v in summary_metrics.items()
                    if k not in ["hr_zones", "movement_speeds"]
                },
            },
        )

        # Get the health metric ID
        result = conn.execute(
            text("""
            SELECT id FROM march_health_metrics 
            WHERE march_id = :march_id AND user_id = :user_id
        """),
            {"march_id": march_id, "user_id": user_id},
        )
        metric_id = result.fetchone()[0]

        # Insert HR zones
        hr_zones = summary_metrics["hr_zones"]
        conn.execute(
            text("""
            INSERT INTO march_hr_zones 
            (march_health_metric_id, very_light_percent, light_percent, moderate_percent, intense_percent, beast_mode_percent)
            VALUES (:metric_id, :very_light, :light, :moderate, :intense, :beast_mode)
        """),
            {
                "metric_id": metric_id,
                "very_light": round(hr_zones[0], 1),
                "light": round(hr_zones[1], 1),
                "moderate": round(hr_zones[2], 1),
                "intense": round(hr_zones[3], 1),
                "beast_mode": round(hr_zones[4], 1),
            },
        )

        # Insert movement speeds
        movement = summary_metrics["movement_speeds"]
        conn.execute(
            text("""
            INSERT INTO march_movement_speeds 
            (march_health_metric_id, walking_minutes, walking_fast_minutes, jogging_minutes, running_minutes, stationary_minutes)
            VALUES (:metric_id, :walking_minutes, :walking_fast_minutes, :jogging_minutes, :running_minutes, :stationary_minutes)
        """),
            {"metric_id": metric_id, **movement},
        )

        # Insert time-series data
        for data_point in timeseries_data:
            conn.execute(
                text("""
                INSERT INTO march_timeseries_data
                (march_id, user_id, timestamp_minutes, heart_rate, step_rate, estimated_speed_kmh, cumulative_steps, cumulative_distance_km, core_temp)
                VALUES (:march_id, :user_id, :timestamp_minutes, :heart_rate, :step_rate, :estimated_speed_kmh, :cumulative_steps, :cumulative_distance_km, :core_temp)
            """),
                {"march_id": march_id, "user_id": user_id, **data_point},
            )

        # Generate and insert GPS track data
        gps_track = generate_gps_track(user_id, duration_minutes, distance_km)
        for gps_point in gps_track:
            conn.execute(
                text("""
                INSERT INTO march_gps_positions
                (march_id, user_id, timestamp_minutes, latitude, longitude, elevation, speed_kmh, bearing)
                VALUES (:march_id, :user_id, :timestamp_minutes, :latitude, :longitude, :elevation, :speed_kmh, :bearing)
            """),
                {"march_id": march_id, "user_id": user_id, **gps_point},
            )

        print(f"✓ Generated data for participant{user_id - 1} ({duration_minutes} min march, {len(gps_track)} GPS points)")

    print("✓ March performance data seeded with time-series")


def main():
    """Main seeding function"""
    print("🚀 Starting simplified database seeding...")
    print(f"Database URL: {get_database_url()}")

    try:
        # Create engine and connect
        engine = create_engine(get_database_url())

        # Create tables
        create_tables(engine)

        # Seed data
        with engine.connect() as conn:
            seed_basic_data(conn)
            seed_march_data(conn)
            conn.commit()

        print("\n✅ Database seeding completed successfully!")
        print("\nTest scenario:")
        print("  - One completed march: 'Training March Alpha' (8.2km, ~2.5 hours)")
        print("  - 4 participants with different performance levels")
        print("  - Time-series HR, core temp, and speed data every 5 minutes")
        print("  - GPS track data with lat/lon/elevation (every 30 seconds)")
        print("  - Summary metrics including avg core temperature and HR zone analysis")
        print("\nTest login credentials:")
        print("  Admin: admin / test123")
        print("  Participants: participant1-4 / test123")

    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        raise


if __name__ == "__main__":
    main()
