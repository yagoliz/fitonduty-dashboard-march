"""Authentication utilities for March Dashboard"""

import logging

from werkzeug.security import check_password_hash, generate_password_hash

from utils.database import get_db_manager, get_user_by_username

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Hash a password using Werkzeug (compatible with database)"""
    return generate_password_hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash using Werkzeug"""
    try:
        return check_password_hash(hashed, password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate user credentials against database"""
    try:
        user_data = get_user_by_username(username)
        if not user_data:
            logger.warning(f"User not found: {username}")
            return None

        if not user_data.get('is_active', False):
            logger.warning(f"Inactive user attempted login: {username}")
            return None

        password_hash = user_data.get('password_hash', '')
        if verify_password(password, password_hash):
            # Update last login timestamp
            update_last_login(user_data['id'])
            logger.info(f"Successful login: {username}")
            return user_data
        else:
            logger.warning(f"Invalid password for user: {username}")
            return None

    except Exception as e:
        logger.error(f"Authentication error for user {username}: {e}")
        return None


def update_last_login(user_id: int):
    """Update user's last login timestamp"""
    try:
        manager = get_db_manager()
        query = """
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP 
            WHERE id = :user_id
        """
        manager.execute_raw(query, {'user_id': user_id})
    except Exception as e:
        logger.warning(f"Database manager not initialized, skipping last login update: {e}")


def get_user_marches(user_id: int):
    """Get marches that a user participated in"""
    try:
        manager = get_db_manager()
        query = """
            SELECT 
                me.id,
                me.name,
                me.date,
                me.status,
                mp.completed
            FROM march_events me
            JOIN march_participants mp ON me.id = mp.march_id
            WHERE mp.user_id = :user_id
            ORDER BY me.date DESC
        """
        return manager.execute_query(query, {'user_id': user_id})
    except Exception as e:
        logger.error(f"Error fetching user marches: {e}")
        return None


def user_can_view_march(user_id: int, march_id: int, user_role: str) -> bool:
    """Check if user can view a specific march"""
    try:
        manager = get_db_manager()

        # Admins can view all marches
        if user_role == 'admin':
            return True

        # Supervisors can view all marches in their groups
        if user_role == 'supervisor':
            return True  # For now, allow supervisors to view all marches

        # Participants can only view marches they participated in
        if user_role == 'participant':
            query = """
                SELECT 1 FROM march_participants 
                WHERE user_id = :user_id AND march_id = :march_id
            """

            result = manager.execute_query(query, {'user_id': user_id, 'march_id': march_id})
            return not result.empty

        return False
    except Exception as e:
        logger.error(f"Error checking march access: {e}")
        return False


def user_can_view_participant(user_id: int, target_user_id: int, user_role: str) -> bool:
    """Check if user can view another participant's details"""
    # Users can always view their own data
    if user_id == target_user_id:
        return True

    # Admins can view all participants
    if user_role == 'admin':
        return True

    # Supervisors can view participants in their groups
    if user_role == 'supervisor':
        return True  # For now, allow supervisors to view all participants

    # Participants cannot view other participants' details
    return False


def get_accessible_marches(user_id: int, user_role: str):
    """Get marches accessible to the user based on their role"""
    try:
        manager = get_db_manager()

        if user_role == 'admin':
            # Admins see all marches
            query = """
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
                GROUP BY me.id, me.name, me.date, me.duration_hours, me.distance_km, 
                         me.route_description, me.status, g.group_name
                ORDER BY me.date DESC
            """
            params = {}

        elif user_role == 'supervisor':
            # Supervisors see all marches (for now - could be restricted to their groups later)
            query = """
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
                GROUP BY me.id, me.name, me.date, me.duration_hours, me.distance_km, 
                         me.route_description, me.status, g.group_name
                ORDER BY me.date DESC
            """
            params = {}

        else:
            # Participants only see marches they participated in
            query = """
                SELECT 
                    me.id,
                    me.name,
                    me.date,
                    me.duration_hours,
                    me.distance_km,
                    me.route_description,
                    me.status,
                    g.group_name,
                    COUNT(mp_all.user_id) as participant_count,
                    COUNT(CASE WHEN mp_all.completed THEN 1 END) as completed_count,
                    mp_user.completed as user_completed
                FROM march_events me
                LEFT JOIN groups g ON me.group_id = g.id
                LEFT JOIN march_participants mp_all ON me.id = mp_all.march_id
                JOIN march_participants mp_user ON me.id = mp_user.march_id AND mp_user.user_id = :user_id
                GROUP BY me.id, me.name, me.date, me.duration_hours, me.distance_km, 
                         me.route_description, me.status, g.group_name, mp_user.completed
                ORDER BY me.date DESC
            """
            params = {'user_id': user_id}

        return manager.execute_query(query, params)
    except Exception as e:
        logger.error(f"Error fetching accessible marches: {e}")
        return None


def create_user(username: str, password: str, role: str = 'participant') -> bool:
    """Create a new user (admin function)"""
    if role not in ['admin', 'participant', 'supervisor']:
        logger.error(f"Invalid role: {role}")
        return False

    try:
        manager = get_db_manager()
        password_hash = hash_password(password)

        query = """
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES (:username, :password_hash, :role, true)
        """

        manager.execute_raw(query, {
            'username': username,
            'password_hash': password_hash,
            'role': role
        })
        logger.info(f"Created user: {username} with role: {role}")
        return True
    except Exception as e:
        logger.error(f"Failed to create user {username}: {e}")
        return False
