"""Database utilities for FitonDuty March Dashboard"""

import logging
import os
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

# Set up logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection and query manager"""

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.environ.get(
            'DATABASE_URL',
            'postgresql://postgres:password@localhost:5432/fitonduty_march'
        )
        self.engine = None
        self.SessionLocal = None
        self._connect()

    def _connect(self):
        """Initialize database connection"""
        try:
            self.engine = create_engine(self.database_url)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def get_connection(self):
        """Get database connection"""
        return self.engine.connect()

    def execute_query(self, query: str, params: dict | None = None) -> pd.DataFrame:
        """Execute query and return pandas DataFrame"""
        try:
            with self.get_connection() as conn:
                result = pd.read_sql(text(query), conn, params=params or {})
                return result
        except SQLAlchemyError as e:
            logger.error(f"Database query error: {e}")
            raise

    def execute_raw(self, query: str, params: dict | None = None) -> Any:
        """Execute raw query and return result"""
        try:
            with self.get_connection() as conn:
                result = conn.execute(text(query), params or {})
                return result
        except SQLAlchemyError as e:
            logger.error(f"Database execution error: {e}")
            raise


# Global database manager instance - will be initialized from config
db_manager = None


def init_database_manager(database_url: str):
    """Initialize the global database manager with configuration"""
    global db_manager
    try:
        db_manager = DatabaseManager(database_url)
        logger.info("Database manager initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database manager: {e}")
        db_manager = None
        return False


def get_db_manager():
    """Get the database manager, ensuring it's initialized"""
    if db_manager is None:
        logger.error("Database manager not initialized. Call init_database_manager() first.")
        raise RuntimeError("Database manager not initialized")
    return db_manager


def get_user_by_username(username: str) -> dict | None:
    """Get user by username"""
    if db_manager is None:
        logger.error("Database manager not initialized")
        return None

    query = """
        SELECT id, username, password_hash, role, is_active, last_login
        FROM users 
        WHERE username = :username AND is_active = true
    """

    try:
        result = db_manager.execute_query(query, {'username': username})
        if result.empty:
            return None
        return result.iloc[0].to_dict()
    except Exception as e:
        logger.error(f"Error fetching user {username}: {e}")
        return None


def get_user_by_id(user_id: int) -> dict | None:
    """Get user by ID"""
    if db_manager is None:
        logger.error("Database manager not initialized")
        return None

    query = """
        SELECT id, username, password_hash, role, is_active, last_login
        FROM users 
        WHERE id = :user_id AND is_active = true
    """

    try:
        result = db_manager.execute_query(query, {'user_id': user_id})
        if result.empty:
            return None
        return result.iloc[0].to_dict()
    except Exception as e:
        logger.error(f"Error fetching user ID {user_id}: {e}")
        return None


def get_march_events(status: str | None = None) -> pd.DataFrame:
    """Get march events, optionally filtered by status"""
    base_query = """
        SELECT 
            me.id,
            me.name,
            me.date,
            me.duration_hours,
            me.distance_km,
            me.route_description,
            me.status,
            g.group_name,
            COUNT(mp.user_id) as participant_count,
            COUNT(CASE WHEN mp.completed THEN 1 END) as completed_count
        FROM march_events me
        LEFT JOIN groups g ON me.group_id = g.id
        LEFT JOIN march_participants mp ON me.id = mp.march_id
    """

    if status:
        query = base_query + " WHERE me.status = :status"
        params = {'status': status}
    else:
        query = base_query
        params = {}

    query += """
        GROUP BY me.id, me.name, me.date, me.duration_hours, me.distance_km, 
                 me.route_description, me.status, g.group_name
        ORDER BY me.date DESC
    """

    try:
        return db_manager.execute_query(query, params)
    except Exception as e:
        logger.error(f"Error fetching march events: {e}")
        return pd.DataFrame()


def get_march_participants(march_id: int) -> pd.DataFrame:
    """Get participants for a specific march"""
    query = """
        SELECT
            mp.march_id,
            mp.user_id,
            u.username,
            mp.completed,
            mp.start_offset_minutes,
            mp.finish_time_minutes,
            mhm.avg_hr,
            mhm.max_hr,
            mhm.total_steps,
            mhm.estimated_distance_km,
            mhm.avg_pace_kmh,
            mhm.effort_score
        FROM march_participants mp
        JOIN users u ON mp.user_id = u.id
        LEFT JOIN march_health_metrics mhm ON mp.march_id = mhm.march_id AND mp.user_id = mhm.user_id
        WHERE mp.march_id = :march_id
        ORDER BY u.username
    """

    try:
        return db_manager.execute_query(query, {'march_id': march_id})
    except Exception as e:
        logger.error(f"Error fetching march participants: {e}")
        return pd.DataFrame()


def get_participant_march_summary(march_id: int, user_id: int) -> dict | None:
    """Get detailed march summary for a specific participant"""
    query = """
        SELECT
            me.name as march_name,
            me.date as march_date,
            me.distance_km as march_distance,
            mp.completed,
            mp.finish_time_minutes,
            mhm.avg_hr,
            mhm.max_hr,
            mhm.total_steps,
            mhm.march_duration_minutes,
            mhm.estimated_distance_km,
            mhm.avg_pace_kmh,
            mhm.effort_score,
            mhm.recovery_hr,
            mhm.avg_core_temp,
            mhm.data_completeness
        FROM march_events me
        JOIN march_participants mp ON me.id = mp.march_id
        LEFT JOIN march_health_metrics mhm ON mp.march_id = mhm.march_id AND mp.user_id = mhm.user_id
        WHERE me.id = :march_id AND mp.user_id = :user_id
    """

    try:
        result = db_manager.execute_query(query, {'march_id': march_id, 'user_id': user_id})
        if result.empty:
            return None
        return result.iloc[0].to_dict()
    except Exception as e:
        logger.error(f"Error fetching participant summary: {e}")
        return None


def get_participant_hr_zones(march_id: int, user_id: int) -> dict | None:
    """Get heart rate zones for a participant's march"""
    query = """
        SELECT 
            mhz.very_light_percent,
            mhz.light_percent,
            mhz.moderate_percent,
            mhz.intense_percent,
            mhz.beast_mode_percent
        FROM march_hr_zones mhz
        JOIN march_health_metrics mhm ON mhz.march_health_metric_id = mhm.id
        WHERE mhm.march_id = :march_id AND mhm.user_id = :user_id
    """

    try:
        result = db_manager.execute_query(query, {'march_id': march_id, 'user_id': user_id})
        if result.empty:
            return None
        return result.iloc[0].to_dict()
    except Exception as e:
        logger.error(f"Error fetching HR zones: {e}")
        return None


def get_participant_movement_speeds(march_id: int, user_id: int) -> dict | None:
    """Get movement speed breakdown for a participant's march"""
    query = """
        SELECT 
            mms.walking_minutes,
            mms.walking_fast_minutes,
            mms.jogging_minutes,
            mms.running_minutes,
            mms.stationary_minutes
        FROM march_movement_speeds mms
        JOIN march_health_metrics mhm ON mms.march_health_metric_id = mhm.id
        WHERE mhm.march_id = :march_id AND mhm.user_id = :user_id
    """

    try:
        result = db_manager.execute_query(query, {'march_id': march_id, 'user_id': user_id})
        if result.empty:
            return None
        return result.iloc[0].to_dict()
    except Exception as e:
        logger.error(f"Error fetching movement speeds: {e}")
        return None


def get_march_timeseries_data(march_id: int, user_id: int) -> pd.DataFrame:
    """Get time-series physiological data for a participant during march"""
    query = """
        SELECT
            timestamp_minutes,
            heart_rate,
            step_rate,
            estimated_speed_kmh,
            cumulative_steps,
            cumulative_distance_km,
            core_temp
        FROM march_timeseries_data
        WHERE march_id = :march_id AND user_id = :user_id
        ORDER BY timestamp_minutes
    """

    try:
        return db_manager.execute_query(query, {'march_id': march_id, 'user_id': user_id})
    except Exception as e:
        logger.error(f"Error fetching timeseries data: {e}")
        return pd.DataFrame()


def get_march_leaderboard(march_id: int, sort_by: str = 'effort_score') -> pd.DataFrame:
    """Get march leaderboard sorted by specified metric"""

    valid_sort_columns = {
        'effort_score': 'mhm.effort_score DESC',
        'finish_time': 'mp.finish_time_minutes ASC',
        'avg_pace': 'mhm.avg_pace_kmh DESC',
        'distance': 'mhm.estimated_distance_km DESC'
    }

    if sort_by not in valid_sort_columns:
        sort_by = 'effort_score'

    query = f"""
        SELECT
            ROW_NUMBER() OVER (ORDER BY {valid_sort_columns[sort_by]}) as rank,
            u.username,
            mp.completed,
            mp.finish_time_minutes,
            mhm.avg_hr,
            mhm.max_hr,
            mhm.total_steps,
            mhm.estimated_distance_km,
            mhm.avg_pace_kmh,
            mhm.effort_score
        FROM march_participants mp
        JOIN users u ON mp.user_id = u.id
        LEFT JOIN march_health_metrics mhm ON mp.march_id = mhm.march_id AND mp.user_id = mhm.user_id
        WHERE mp.march_id = :march_id AND mp.completed = true
        ORDER BY {valid_sort_columns[sort_by]}
    """

    try:
        return db_manager.execute_query(query, {'march_id': march_id})
    except Exception as e:
        logger.error(f"Error fetching march leaderboard: {e}")
        return pd.DataFrame()


def get_march_gps_track(march_id: int, user_id: int) -> pd.DataFrame:
    """Get GPS track data for a participant's march route"""
    query = """
        SELECT
            timestamp_minutes,
            latitude,
            longitude,
            elevation,
            speed_kmh,
            bearing
        FROM march_gps_positions
        WHERE march_id = :march_id AND user_id = :user_id
        ORDER BY timestamp_minutes
    """

    try:
        return db_manager.execute_query(query, {'march_id': march_id, 'user_id': user_id})
    except Exception as e:
        logger.error(f"Error fetching GPS track: {e}")
        return pd.DataFrame()


def get_march_all_gps_tracks(march_id: int) -> pd.DataFrame:
    """Get GPS tracks for all participants in a march"""
    query = """
        SELECT
            mgp.user_id,
            u.username,
            mgp.timestamp_minutes,
            mgp.latitude,
            mgp.longitude,
            mgp.elevation,
            mgp.speed_kmh
        FROM march_gps_positions mgp
        JOIN users u ON mgp.user_id = u.id
        WHERE mgp.march_id = :march_id
        ORDER BY mgp.user_id, mgp.timestamp_minutes
    """

    try:
        return db_manager.execute_query(query, {'march_id': march_id})
    except Exception as e:
        logger.error(f"Error fetching all GPS tracks: {e}")
        return pd.DataFrame()
