"""Test configuration and fixtures for FitonDuty March Dashboard"""

import os
import sys
from unittest.mock import Mock

import pandas as pd
import pytest
from faker import Faker

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import DatabaseManager


@pytest.fixture
def fake():
    """Faker instance for generating test data"""
    return Faker()


@pytest.fixture
def mock_db_manager():
    """Mock database manager for testing without database"""
    mock = Mock(spec=DatabaseManager)
    mock.execute_query = Mock(return_value=pd.DataFrame())
    mock.execute_raw = Mock(return_value=Mock())
    mock.get_connection = Mock(return_value=Mock())
    return mock


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        'id': 1,
        'username': 'test_user',
        'password_hash': 'scrypt:32768:8:1$test$hash',
        'role': 'participant',
        'is_active': True,
        'last_login': None
    }


@pytest.fixture
def sample_admin_user():
    """Sample admin user data"""
    return {
        'id': 2,
        'username': 'admin_user',
        'password_hash': 'scrypt:32768:8:1$test$hash',
        'role': 'admin',
        'is_active': True,
        'last_login': None
    }


@pytest.fixture
def sample_march_events():
    """Sample march events data"""
    return pd.DataFrame([
        {
            'id': 1,
            'name': 'Training March Alpha',
            'date': '2024-01-15',
            'duration_hours': 4.5,
            'distance_km': 20.0,
            'route_description': 'Woodland trail circuit',
            'status': 'published',
            'group_name': 'Alpha Squad',
            'participant_count': 4,
            'completed_count': 3
        },
        {
            'id': 2,
            'name': 'Endurance March Beta',
            'date': '2024-01-20',
            'duration_hours': 6.0,
            'distance_km': 25.0,
            'route_description': 'Mountain terrain',
            'status': 'published',
            'group_name': 'Beta Squad',
            'participant_count': 3,
            'completed_count': 2
        }
    ])


@pytest.fixture
def sample_march_participants():
    """Sample march participants data"""
    return pd.DataFrame([
        {
            'march_id': 1,
            'user_id': 1,
            'username': 'participant_1',
            'completed': True,
            'start_offset_minutes': 0,
            'finish_time_minutes': 240,
            'avg_hr': 145,
            'max_hr': 180,
            'total_steps': 18500,
            'estimated_distance_km': 19.2,
            'avg_pace_kmh': 4.8,
            'effort_score': 87.5
        },
        {
            'march_id': 1,
            'user_id': 2,
            'username': 'participant_2',
            'completed': True,
            'start_offset_minutes': 0,
            'finish_time_minutes': 265,
            'avg_hr': 152,
            'max_hr': 175,
            'total_steps': 19200,
            'estimated_distance_km': 18.8,
            'avg_pace_kmh': 4.3,
            'effort_score': 82.1
        }
    ])


@pytest.fixture
def sample_timeseries_data():
    """Sample march timeseries data"""
    return pd.DataFrame([
        {
            'timestamp_minutes': 0,
            'heart_rate': 85,
            'step_rate': 0,
            'estimated_speed_kmh': 0.0,
            'cumulative_steps': 0,
            'cumulative_distance_km': 0.0
        },
        {
            'timestamp_minutes': 5,
            'heart_rate': 120,
            'step_rate': 110,
            'estimated_speed_kmh': 4.5,
            'cumulative_steps': 550,
            'cumulative_distance_km': 0.375
        },
        {
            'timestamp_minutes': 10,
            'heart_rate': 135,
            'step_rate': 115,
            'estimated_speed_kmh': 5.2,
            'cumulative_steps': 1125,
            'cumulative_distance_km': 0.81
        }
    ])


@pytest.fixture
def sample_hr_zones():
    """Sample HR zones data"""
    return {
        'very_light_percent': 15.2,
        'light_percent': 28.6,
        'moderate_percent': 35.4,
        'intense_percent': 18.1,
        'beast_mode_percent': 2.7
    }


@pytest.fixture
def sample_movement_speeds():
    """Sample movement speeds data"""
    return {
        'walking_minutes': 45,
        'walking_fast_minutes': 120,
        'jogging_minutes': 60,
        'running_minutes': 15,
        'stationary_minutes': 0
    }


@pytest.fixture
def mock_environment_variables(monkeypatch):
    """Mock environment variables for testing"""
    test_env_vars = {
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_fitonduty_march',
        'SECRET_KEY': 'test-secret-key',
        'DEBUG': 'True'
    }

    for key, value in test_env_vars.items():
        monkeypatch.setenv(key, value)

    return test_env_vars


@pytest.fixture
def dash_duo(dash_duo):
    """Enhanced dash_duo fixture with additional setup"""
    # Set up any common dashboard configurations here
    return dash_duo
