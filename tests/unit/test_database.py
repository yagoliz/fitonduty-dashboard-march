"""Unit tests for database utilities"""

from unittest.mock import Mock, patch

import pandas as pd
import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.database.utils import (
    DatabaseManager,
    get_db_manager,
    get_march_events,
    get_march_leaderboard,
    get_march_participants,
    get_march_timeseries_data,
    get_participant_hr_zones,
    get_participant_march_summary,
    get_participant_movement_speeds,
    get_user_by_id,
    get_user_by_username,
    init_database_manager,
)


@pytest.mark.unit
class TestDatabaseManager:
    """Test DatabaseManager class"""

    def test_init_with_default_url(self, mock_environment_variables):
        """Test DatabaseManager initialization with default URL"""
        with patch('utils.database.create_engine') as mock_engine:
            mock_engine.return_value = Mock()
            db_manager = DatabaseManager()
            assert db_manager.database_url == mock_environment_variables['DATABASE_URL']
            mock_engine.assert_called_once()

    def test_init_with_custom_url(self):
        """Test DatabaseManager initialization with custom URL"""
        custom_url = 'postgresql://custom:pass@localhost:5432/custom_db'
        with patch('utils.database.create_engine') as mock_engine:
            mock_engine.return_value = Mock()
            db_manager = DatabaseManager(custom_url)
            assert db_manager.database_url == custom_url
            mock_engine.assert_called_once()

    def test_connect_failure(self):
        """Test database connection failure"""
        with patch('utils.database.create_engine', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception, match="Connection failed"):
                DatabaseManager()

    def test_execute_query_success(self):
        """Test successful query execution"""
        with patch('utils.database.create_engine') as mock_engine:
            mock_connection = Mock()
            mock_engine.return_value.connect.return_value.__enter__.return_value = mock_connection

            db_manager = DatabaseManager('test://url')

            expected_df = pd.DataFrame({'id': [1, 2], 'name': ['test1', 'test2']})

            with patch('pandas.read_sql', return_value=expected_df) as mock_read_sql:
                result = db_manager.execute_query("SELECT * FROM test", {'param': 'value'})

                assert result.equals(expected_df)
                mock_read_sql.assert_called_once()

    def test_execute_query_error(self):
        """Test query execution with SQLAlchemy error"""
        with patch('utils.database.create_engine') as mock_engine:
            mock_connection = Mock()
            mock_engine.return_value.connect.return_value.__enter__.return_value = mock_connection

            db_manager = DatabaseManager('test://url')

            with patch('pandas.read_sql', side_effect=SQLAlchemyError("Query failed")):
                with pytest.raises(SQLAlchemyError):
                    db_manager.execute_query("SELECT * FROM test")

    def test_execute_raw_success(self):
        """Test successful raw query execution"""
        with patch('utils.database.create_engine') as mock_engine:
            mock_connection = Mock()
            mock_result = Mock()
            mock_connection.execute.return_value = mock_result
            mock_engine.return_value.connect.return_value.__enter__.return_value = mock_connection

            db_manager = DatabaseManager('test://url')
            result = db_manager.execute_raw("UPDATE test SET name = :name", {'name': 'updated'})

            assert result == mock_result
            mock_connection.execute.assert_called_once()

    def test_execute_raw_error(self):
        """Test raw query execution with error"""
        with patch('utils.database.create_engine') as mock_engine:
            mock_connection = Mock()
            mock_connection.execute.side_effect = SQLAlchemyError("Update failed")
            mock_engine.return_value.connect.return_value.__enter__.return_value = mock_connection

            db_manager = DatabaseManager('test://url')

            with pytest.raises(SQLAlchemyError):
                db_manager.execute_raw("UPDATE test SET name = :name", {'name': 'updated'})


@pytest.mark.unit
class TestDatabaseFunctions:
    """Test database utility functions"""

    def test_init_database_manager_success(self):
        """Test successful database manager initialization"""
        with patch('utils.database.DatabaseManager') as mock_db_class:
            mock_instance = Mock()
            mock_db_class.return_value = mock_instance

            result = init_database_manager('test://url')

            assert result is True
            mock_db_class.assert_called_once_with('test://url')

    def test_init_database_manager_failure(self):
        """Test failed database manager initialization"""
        with patch('utils.database.DatabaseManager', side_effect=Exception("Init failed")):
            result = init_database_manager('test://url')
            assert result is False

    def test_get_db_manager_success(self, mock_db_manager):
        """Test successful database manager retrieval"""
        with patch('utils.database.db_manager', mock_db_manager):
            result = get_db_manager()
            assert result == mock_db_manager

    def test_get_db_manager_not_initialized(self):
        """Test database manager retrieval when not initialized"""
        with patch('utils.database.db_manager', None):
            with pytest.raises(RuntimeError, match="Database manager not initialized"):
                get_db_manager()

    @patch('utils.database.db_manager')
    def test_get_user_by_username_success(self, mock_db, sample_user_data):
        """Test successful user retrieval by username"""
        mock_db.execute_query.return_value = pd.DataFrame([sample_user_data])

        result = get_user_by_username('test_user')

        assert result == sample_user_data
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_user_by_username_not_found(self, mock_db):
        """Test user retrieval when user not found"""
        mock_db.execute_query.return_value = pd.DataFrame()

        result = get_user_by_username('nonexistent')

        assert result is None

    @patch('utils.database.db_manager', None)
    def test_get_user_by_username_no_manager(self):
        """Test user retrieval when database manager not initialized"""
        result = get_user_by_username('test_user')
        assert result is None

    @patch('utils.database.db_manager')
    def test_get_user_by_username_exception(self, mock_db):
        """Test user retrieval with database exception"""
        mock_db.execute_query.side_effect = Exception("Database error")

        result = get_user_by_username('test_user')

        assert result is None

    @patch('utils.database.db_manager')
    def test_get_user_by_id_success(self, mock_db, sample_user_data):
        """Test successful user retrieval by ID"""
        mock_db.execute_query.return_value = pd.DataFrame([sample_user_data])

        result = get_user_by_id(1)

        assert result == sample_user_data
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_march_events_success(self, mock_db, sample_march_events):
        """Test successful march events retrieval"""
        mock_db.execute_query.return_value = sample_march_events

        result = get_march_events()

        assert result.equals(sample_march_events)
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_march_events_with_status(self, mock_db, sample_march_events):
        """Test march events retrieval with status filter"""
        filtered_events = sample_march_events[sample_march_events['status'] == 'published']
        mock_db.execute_query.return_value = filtered_events

        result = get_march_events(status='published')

        assert result.equals(filtered_events)
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_march_events_exception(self, mock_db):
        """Test march events retrieval with exception"""
        mock_db.execute_query.side_effect = Exception("Database error")

        result = get_march_events()

        assert result.empty
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_march_participants_success(self, mock_db, sample_march_participants):
        """Test successful march participants retrieval"""
        mock_db.execute_query.return_value = sample_march_participants

        result = get_march_participants(1)

        assert result.equals(sample_march_participants)
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_participant_march_summary_success(self, mock_db):
        """Test successful participant march summary retrieval"""
        summary_data = {
            'march_name': 'Test March',
            'march_date': '2024-01-15',
            'completed': True,
            'effort_score': 85.5
        }
        mock_db.execute_query.return_value = pd.DataFrame([summary_data])

        result = get_participant_march_summary(1, 1)

        assert result == summary_data
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_participant_march_summary_not_found(self, mock_db):
        """Test participant march summary when not found"""
        mock_db.execute_query.return_value = pd.DataFrame()

        result = get_participant_march_summary(1, 999)

        assert result is None

    @patch('utils.database.db_manager')
    def test_get_participant_hr_zones_success(self, mock_db, sample_hr_zones):
        """Test successful HR zones retrieval"""
        mock_db.execute_query.return_value = pd.DataFrame([sample_hr_zones])

        result = get_participant_hr_zones(1, 1)

        assert result == sample_hr_zones
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_participant_movement_speeds_success(self, mock_db, sample_movement_speeds):
        """Test successful movement speeds retrieval"""
        mock_db.execute_query.return_value = pd.DataFrame([sample_movement_speeds])

        result = get_participant_movement_speeds(1, 1)

        assert result == sample_movement_speeds
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_march_timeseries_data_success(self, mock_db, sample_timeseries_data):
        """Test successful timeseries data retrieval"""
        mock_db.execute_query.return_value = sample_timeseries_data

        result = get_march_timeseries_data(1, 1)

        assert result.equals(sample_timeseries_data)
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_march_leaderboard_success(self, mock_db):
        """Test successful march leaderboard retrieval"""
        leaderboard_data = pd.DataFrame([
            {'rank': 1, 'username': 'user1', 'effort_score': 95.5},
            {'rank': 2, 'username': 'user2', 'effort_score': 88.2}
        ])
        mock_db.execute_query.return_value = leaderboard_data

        result = get_march_leaderboard(1, 'effort_score')

        assert result.equals(leaderboard_data)
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_march_leaderboard_invalid_sort(self, mock_db):
        """Test march leaderboard with invalid sort parameter"""
        leaderboard_data = pd.DataFrame([
            {'rank': 1, 'username': 'user1', 'effort_score': 95.5}
        ])
        mock_db.execute_query.return_value = leaderboard_data

        # Should default to effort_score when invalid sort provided
        result = get_march_leaderboard(1, 'invalid_sort')

        assert result.equals(leaderboard_data)
        mock_db.execute_query.assert_called_once()

    @patch('utils.database.db_manager')
    def test_get_march_leaderboard_exception(self, mock_db):
        """Test march leaderboard with exception"""
        mock_db.execute_query.side_effect = Exception("Database error")

        result = get_march_leaderboard(1)

        assert result.empty
        mock_db.execute_query.assert_called_once()


@pytest.mark.unit
@pytest.mark.parametrize("sort_by,expected_order", [
    ('effort_score', 'mhm.effort_score DESC'),
    ('finish_time', 'mp.finish_time_minutes ASC'),
    ('avg_pace', 'mhm.avg_pace_kmh DESC'),
    ('distance', 'mhm.estimated_distance_km DESC'),
    ('invalid', 'mhm.effort_score DESC')  # Should default to effort_score
])
def test_leaderboard_sort_parameters(sort_by, expected_order):
    """Test leaderboard sort parameter validation"""
    with patch('utils.database.db_manager') as mock_db:
        mock_db.execute_query.return_value = pd.DataFrame()

        get_march_leaderboard(1, sort_by)

        # Verify the SQL query contains the expected ORDER BY clause
        call_args = mock_db.execute_query.call_args
        query = call_args[0][0]
        assert expected_order in query
