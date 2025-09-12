"""Unit tests for authentication system"""

from unittest.mock import Mock, patch

import pandas as pd
import pytest
from werkzeug.security import generate_password_hash

from utils.auth import (
    authenticate_user,
    create_user,
    get_accessible_marches,
    get_user_marches,
    hash_password,
    update_last_login,
    user_can_view_march,
    user_can_view_participant,
    verify_password,
)


@pytest.mark.unit
class TestPasswordUtilities:
    """Test password hashing and verification utilities"""

    def test_hash_password(self):
        """Test password hashing"""
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith('scrypt:')
        assert len(hashed) > 50  # Werkzeug hash should be substantial length

    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "test_password_123"
        hashed = generate_password_hash(password)

        result = verify_password(password, hashed)

        assert result is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = generate_password_hash(password)

        result = verify_password(wrong_password, hashed)

        assert result is False

    def test_verify_password_exception(self):
        """Test password verification with invalid hash"""
        result = verify_password("password", "invalid_hash")
        assert result is False


@pytest.mark.unit
class TestUserAuthentication:
    """Test user authentication functions"""

    @patch('utils.auth.get_user_by_username')
    @patch('utils.auth.verify_password')
    @patch('utils.auth.update_last_login')
    def test_authenticate_user_success(self, mock_update_login, mock_verify, mock_get_user, sample_user_data):
        """Test successful user authentication"""
        mock_get_user.return_value = sample_user_data
        mock_verify.return_value = True

        result = authenticate_user('test_user', 'correct_password')

        assert result == sample_user_data
        mock_get_user.assert_called_once_with('test_user')
        mock_verify.assert_called_once_with('correct_password', sample_user_data['password_hash'])
        mock_update_login.assert_called_once_with(sample_user_data['id'])

    @patch('utils.auth.get_user_by_username')
    def test_authenticate_user_not_found(self, mock_get_user):
        """Test authentication with user not found"""
        mock_get_user.return_value = None

        result = authenticate_user('nonexistent_user', 'password')

        assert result is None
        mock_get_user.assert_called_once_with('nonexistent_user')

    @patch('utils.auth.get_user_by_username')
    def test_authenticate_user_inactive(self, mock_get_user, sample_user_data):
        """Test authentication with inactive user"""
        inactive_user = sample_user_data.copy()
        inactive_user['is_active'] = False
        mock_get_user.return_value = inactive_user

        result = authenticate_user('test_user', 'password')

        assert result is None

    @patch('utils.auth.get_user_by_username')
    @patch('utils.auth.verify_password')
    def test_authenticate_user_wrong_password(self, mock_verify, mock_get_user, sample_user_data):
        """Test authentication with wrong password"""
        mock_get_user.return_value = sample_user_data
        mock_verify.return_value = False

        result = authenticate_user('test_user', 'wrong_password')

        assert result is None
        mock_verify.assert_called_once_with('wrong_password', sample_user_data['password_hash'])

    @patch('utils.auth.get_user_by_username')
    def test_authenticate_user_exception(self, mock_get_user):
        """Test authentication with exception"""
        mock_get_user.side_effect = Exception("Database error")

        result = authenticate_user('test_user', 'password')

        assert result is None

    @patch('utils.auth.get_db_manager')
    def test_update_last_login_success(self, mock_get_db):
        """Test successful last login update"""
        mock_manager = Mock()
        mock_get_db.return_value = mock_manager

        update_last_login(123)

        mock_manager.execute_raw.assert_called_once()
        # Check the call was made with correct parameters
        args, kwargs = mock_manager.execute_raw.call_args
        assert 'UPDATE users' in args[0]
        assert kwargs == {'user_id': 123}

    @patch('utils.auth.get_db_manager')
    def test_update_last_login_exception(self, mock_get_db):
        """Test last login update with exception"""
        mock_get_db.side_effect = Exception("Database error")

        # Should not raise exception, just log warning
        update_last_login(123)


@pytest.mark.unit
class TestUserMarches:
    """Test user march access functions"""

    @patch('utils.auth.get_db_manager')
    def test_get_user_marches_success(self, mock_get_db):
        """Test successful user marches retrieval"""
        mock_manager = Mock()
        march_data = pd.DataFrame([
            {'id': 1, 'name': 'March 1', 'date': '2024-01-15', 'completed': True},
            {'id': 2, 'name': 'March 2', 'date': '2024-01-20', 'completed': False}
        ])
        mock_manager.execute_query.return_value = march_data
        mock_get_db.return_value = mock_manager

        result = get_user_marches(123)

        assert result.equals(march_data)
        mock_manager.execute_query.assert_called_once()

    @patch('utils.auth.get_db_manager')
    def test_get_user_marches_exception(self, mock_get_db):
        """Test user marches retrieval with exception"""
        mock_get_db.side_effect = Exception("Database error")

        result = get_user_marches(123)

        assert result is None


@pytest.mark.unit
class TestPermissions:
    """Test permission checking functions"""

    @patch('utils.auth.get_db_manager')
    def test_user_can_view_march_admin(self, mock_get_db):
        """Test admin can view any march"""
        mock_manager = Mock()
        mock_get_db.return_value = mock_manager

        result = user_can_view_march(1, 999, 'admin')
        assert result is True
        # Admin access calls get_db_manager but doesn't use the database query
        mock_get_db.assert_called_once()

    @patch('utils.auth.get_db_manager')
    def test_user_can_view_march_supervisor(self, mock_get_db):
        """Test supervisor can view any march"""
        mock_manager = Mock()
        mock_get_db.return_value = mock_manager

        result = user_can_view_march(1, 999, 'supervisor')
        assert result is True
        # Supervisor access calls get_db_manager but doesn't use the database query
        mock_get_db.assert_called_once()

    @patch('utils.auth.get_db_manager')
    def test_user_can_view_march_participant_allowed(self, mock_get_db):
        """Test participant can view march they participated in"""
        mock_manager = Mock()
        mock_manager.execute_query.return_value = pd.DataFrame([{'user_id': 1}])  # Non-empty = found
        mock_get_db.return_value = mock_manager

        result = user_can_view_march(1, 123, 'participant')

        assert result is True
        mock_manager.execute_query.assert_called_once()

    @patch('utils.auth.get_db_manager')
    def test_user_can_view_march_participant_denied(self, mock_get_db):
        """Test participant cannot view march they didn't participate in"""
        mock_manager = Mock()
        mock_manager.execute_query.return_value = pd.DataFrame()  # Empty = not found
        mock_get_db.return_value = mock_manager

        result = user_can_view_march(1, 123, 'participant')

        assert result is False

    @patch('utils.auth.get_db_manager')
    def test_user_can_view_march_invalid_role(self, mock_get_db):
        """Test invalid role cannot view march"""
        result = user_can_view_march(1, 123, 'invalid_role')
        assert result is False

    @patch('utils.auth.get_db_manager')
    def test_user_can_view_march_exception(self, mock_get_db):
        """Test march permission check with exception"""
        mock_get_db.side_effect = Exception("Database error")

        result = user_can_view_march(1, 123, 'participant')

        assert result is False

    def test_user_can_view_participant_self(self):
        """Test user can view their own participant details"""
        result = user_can_view_participant(1, 1, 'participant')
        assert result is True

    def test_user_can_view_participant_admin(self):
        """Test admin can view any participant"""
        result = user_can_view_participant(1, 2, 'admin')
        assert result is True

    def test_user_can_view_participant_supervisor(self):
        """Test supervisor can view any participant"""
        result = user_can_view_participant(1, 2, 'supervisor')
        assert result is True

    def test_user_can_view_participant_denied(self):
        """Test participant cannot view other participants"""
        result = user_can_view_participant(1, 2, 'participant')
        assert result is False


@pytest.mark.unit
class TestAccessibleMarches:
    """Test accessible marches retrieval"""

    @patch('utils.auth.get_db_manager')
    def test_get_accessible_marches_admin(self, mock_get_db, sample_march_events):
        """Test admin gets all marches"""
        mock_manager = Mock()
        mock_manager.execute_query.return_value = sample_march_events
        mock_get_db.return_value = mock_manager

        result = get_accessible_marches(1, 'admin')

        assert result.equals(sample_march_events)
        # Verify query doesn't filter by user_id for admin
        call_args = mock_manager.execute_query.call_args
        assert call_args[1] == {}  # No parameters for admin query

    @patch('utils.auth.get_db_manager')
    def test_get_accessible_marches_supervisor(self, mock_get_db, sample_march_events):
        """Test supervisor gets all marches"""
        mock_manager = Mock()
        mock_manager.execute_query.return_value = sample_march_events
        mock_get_db.return_value = mock_manager

        result = get_accessible_marches(1, 'supervisor')

        assert result.equals(sample_march_events)

    @patch('utils.auth.get_db_manager')
    def test_get_accessible_marches_participant(self, mock_get_db, sample_march_events):
        """Test participant gets only their marches"""
        mock_manager = Mock()
        participant_marches = sample_march_events.iloc[:1]  # Only first march
        mock_manager.execute_query.return_value = participant_marches
        mock_get_db.return_value = mock_manager

        result = get_accessible_marches(1, 'participant')

        assert result.equals(participant_marches)
        # Verify query includes user_id parameter for participant
        args, kwargs = mock_manager.execute_query.call_args
        assert kwargs == {'user_id': 1}

    @patch('utils.auth.get_db_manager')
    def test_get_accessible_marches_exception(self, mock_get_db):
        """Test accessible marches with exception"""
        mock_get_db.side_effect = Exception("Database error")

        result = get_accessible_marches(1, 'admin')

        assert result is None


@pytest.mark.unit
class TestUserCreation:
    """Test user creation function"""

    @patch('utils.auth.get_db_manager')
    @patch('utils.auth.hash_password')
    def test_create_user_success(self, mock_hash, mock_get_db):
        """Test successful user creation"""
        mock_manager = Mock()
        mock_get_db.return_value = mock_manager
        mock_hash.return_value = 'hashed_password'

        result = create_user('new_user', 'password123', 'participant')

        assert result is True
        mock_hash.assert_called_once_with('password123')
        mock_manager.execute_raw.assert_called_once()
        # Check the call was made with correct parameters
        args, kwargs = mock_manager.execute_raw.call_args
        assert 'INSERT INTO users' in args[0]
        assert kwargs['username'] == 'new_user'
        assert kwargs['role'] == 'participant'

    def test_create_user_invalid_role(self):
        """Test user creation with invalid role"""
        result = create_user('new_user', 'password', 'invalid_role')
        assert result is False

    @patch('utils.auth.get_db_manager')
    @patch('utils.auth.hash_password')
    def test_create_user_exception(self, mock_hash, mock_get_db):
        """Test user creation with exception"""
        mock_get_db.side_effect = Exception("Database error")

        result = create_user('new_user', 'password', 'participant')

        assert result is False


@pytest.mark.unit
@pytest.mark.parametrize("role,expected_access", [
    ('admin', True),
    ('supervisor', True),
    ('participant', False),  # Unless it's their own data
    ('invalid', False)
])
def test_role_permissions_matrix(role, expected_access):
    """Test role-based permission matrix"""
    # Test march access
    with patch('utils.auth.get_db_manager'):
        march_access = user_can_view_march(1, 123, role)
        if role in ['admin', 'supervisor']:
            assert march_access == expected_access
        # participant access depends on database query, tested separately

    # Test participant access (different user)
    participant_access = user_can_view_participant(1, 2, role)  # Different user IDs
    assert participant_access == expected_access
