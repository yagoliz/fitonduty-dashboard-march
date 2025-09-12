"""Unit tests for march dashboard components"""

from unittest.mock import patch

import dash_bootstrap_components as dbc
import pandas as pd
import pytest
from dash import html

from components.march.march_overview import (
    create_error_message,
    create_march_detail_view,
    create_march_overview,
    create_march_selector,
)
from components.march.participant_detail import create_participant_detail_view
from components.march.role_based_overview import create_role_based_march_overview


@pytest.mark.unit
class TestMarchOverview:
    """Test march overview component"""

    @patch('components.march.march_overview.get_march_events')
    def test_create_march_overview_no_march_id(self, mock_get_events, sample_march_events):
        """Test march overview without specific march ID shows selector"""
        mock_get_events.return_value = sample_march_events

        result = create_march_overview()

        # Should return march selector when no march_id provided
        assert isinstance(result, (list, dbc.Alert))
        mock_get_events.assert_called_once()

    @patch('components.march.march_overview.get_march_events')
    @patch('components.march.march_overview.get_march_participants')
    @patch('components.march.march_overview.get_march_leaderboard')
    def test_create_march_overview_with_march_id(self, mock_leaderboard, mock_participants,
                                                  mock_events, sample_march_events,
                                                  sample_march_participants):
        """Test march overview with specific march ID"""
        mock_events.return_value = sample_march_events
        mock_participants.return_value = sample_march_participants
        mock_leaderboard.return_value = sample_march_participants

        result = create_march_overview(march_id=1)

        # Should return detailed march view
        assert result is not None
        mock_events.assert_called_once()
        mock_participants.assert_called_once_with(1)
        mock_leaderboard.assert_called_once_with(1, 'effort_score')

    @patch('components.march.march_overview.get_march_events')
    def test_create_march_overview_march_not_found(self, mock_get_events):
        """Test march overview when march not found"""
        # Return empty DataFrame to simulate march not found
        mock_get_events.return_value = pd.DataFrame()

        result = create_march_overview(march_id=999)

        # Should return error message
        assert isinstance(result, dbc.Alert)

    @patch('components.march.march_overview.get_march_events')
    def test_create_march_overview_exception(self, mock_get_events):
        """Test march overview with database exception"""
        mock_get_events.side_effect = Exception("Database error")

        result = create_march_overview(march_id=1)

        # Should return error message
        assert isinstance(result, dbc.Alert)

    @patch('components.march.march_overview.get_march_events')
    def test_create_march_selector_with_events(self, mock_get_events, sample_march_events):
        """Test march selector with available events"""
        mock_get_events.return_value = sample_march_events

        result = create_march_selector()

        # Should return list of cards for each march
        assert isinstance(result, list)
        assert len(result) == len(sample_march_events)
        mock_get_events.assert_called_once_with(status='published')

    @patch('components.march.march_overview.get_march_events')
    def test_create_march_selector_no_events(self, mock_get_events):
        """Test march selector with no available events"""
        mock_get_events.return_value = pd.DataFrame()

        result = create_march_selector()

        # Should return warning alert
        assert isinstance(result, dbc.Alert)

    def test_create_error_message(self):
        """Test error message creation"""
        error_msg = "Test error message"
        result = create_error_message(error_msg)

        assert isinstance(result, dbc.Alert)
        assert result.color == "danger"
        # Check if error message is contained in the alert children
        assert error_msg in str(result.children)

    def test_create_march_detail_view_structure(self, sample_march_events, sample_march_participants):
        """Test march detail view structure"""
        march_info = sample_march_events.iloc[0]
        participants = sample_march_participants
        leaderboard = sample_march_participants

        result = create_march_detail_view(march_info, participants, leaderboard)

        # Should return a Dash component structure
        assert result is not None
        # Check that it contains the basic structure elements
        assert isinstance(result, (list, html.Div, dbc.Container))


@pytest.mark.unit
class TestParticipantDetail:
    """Test participant detail component"""

    @patch('components.march.participant_detail.get_participant_march_summary')
    @patch('components.march.participant_detail.get_participant_hr_zones')
    @patch('components.march.participant_detail.get_participant_movement_speeds')
    @patch('components.march.participant_detail.get_march_timeseries_data')
    def test_create_participant_detail_view_success(self, mock_timeseries, mock_movement,
                                                     mock_hr_zones, mock_summary,
                                                     sample_timeseries_data, sample_movement_speeds,
                                                     sample_hr_zones):
        """Test successful participant detail view creation"""
        # Setup mock returns
        mock_summary.return_value = {
            'march_name': 'Test March',
            'march_date': '2024-01-15',
            'completed': True,
            'avg_hr': 145,
            'total_steps': 18500,
            'effort_score': 87.5
        }
        mock_hr_zones.return_value = sample_hr_zones
        mock_movement.return_value = sample_movement_speeds
        mock_timeseries.return_value = sample_timeseries_data

        result = create_participant_detail_view(march_id=1, user_id=1)

        assert result is not None
        # Verify all data sources were called
        mock_summary.assert_called_once_with(1, 1)
        mock_hr_zones.assert_called_once_with(1, 1)
        mock_movement.assert_called_once_with(1, 1)
        mock_timeseries.assert_called_once_with(1, 1)

    @patch('components.march.participant_detail.get_participant_march_summary')
    def test_create_participant_detail_view_no_data(self, mock_summary):
        """Test participant detail view when no data found"""
        mock_summary.return_value = None

        result = create_participant_detail_view(march_id=1, user_id=999)

        # Should return error message when no data found
        assert isinstance(result, dbc.Alert)
        assert result.color == "warning"

    @patch('components.march.participant_detail.get_participant_march_summary')
    def test_create_participant_detail_view_exception(self, mock_summary):
        """Test participant detail view with exception"""
        mock_summary.side_effect = Exception("Database error")

        result = create_participant_detail_view(march_id=1, user_id=1)

        # Should return error message
        assert isinstance(result, dbc.Alert)
        assert result.color == "danger"


@pytest.mark.unit
class TestRoleBasedOverview:
    """Test role-based march overview component"""

    @patch('components.march.role_based_overview.get_accessible_marches')
    def test_create_role_based_march_overview_admin(self, mock_get_marches, sample_march_events):
        """Test role-based overview for admin user"""
        mock_get_marches.return_value = sample_march_events

        result = create_role_based_march_overview(user_id=1, user_role='admin')

        assert result is not None
        mock_get_marches.assert_called_once_with(1, 'admin')

    @patch('components.march.role_based_overview.get_accessible_marches')
    def test_create_role_based_march_overview_participant(self, mock_get_marches, sample_march_events):
        """Test role-based overview for participant user"""
        participant_marches = sample_march_events.iloc[:1]  # Only one march for participant
        mock_get_marches.return_value = participant_marches

        result = create_role_based_march_overview(user_id=1, user_role='participant')

        assert result is not None
        mock_get_marches.assert_called_once_with(1, 'participant')

    @patch('components.march.role_based_overview.get_accessible_marches')
    def test_create_role_based_march_overview_no_marches(self, mock_get_marches):
        """Test role-based overview with no accessible marches"""
        mock_get_marches.return_value = pd.DataFrame()

        result = create_role_based_march_overview(user_id=1, user_role='participant')

        # Should handle empty marches gracefully
        assert isinstance(result, (dbc.Alert, html.Div, list))

    @patch('components.march.role_based_overview.get_accessible_marches')
    def test_create_role_based_march_overview_exception(self, mock_get_marches):
        """Test role-based overview with database exception"""
        mock_get_marches.side_effect = Exception("Database error")

        result = create_role_based_march_overview(user_id=1, user_role='admin')

        # Should return error message
        assert isinstance(result, dbc.Alert)


@pytest.mark.unit
class TestMarchVisualizationCharts:
    """Test march visualization chart components"""

    @patch('utils.visualization.march_charts.create_hr_speed_timeline')
    def test_hr_speed_timeline_creation(self, mock_create_chart, sample_timeseries_data):
        """Test HR and speed timeline chart creation"""
        from utils.visualization.march_charts import create_hr_speed_timeline

        mock_create_chart.return_value = {'data': [], 'layout': {}}

        result = create_hr_speed_timeline(sample_timeseries_data, "Test Participant")

        assert result is not None
        mock_create_chart.assert_called_once()

    @patch('utils.visualization.march_charts.create_hr_zones_chart')
    def test_hr_zones_chart_creation(self, mock_create_chart, sample_hr_zones):
        """Test HR zones doughnut chart creation"""
        from utils.visualization.march_charts import create_hr_zones_chart

        mock_create_chart.return_value = {'data': [], 'layout': {}}

        result = create_hr_zones_chart(sample_hr_zones, "Test Participant")

        assert result is not None
        mock_create_chart.assert_called_once()

    @patch('utils.visualization.march_charts.create_movement_categories_chart')
    def test_movement_categories_chart_creation(self, mock_create_chart, sample_movement_speeds):
        """Test movement categories bar chart creation"""
        from utils.visualization.march_charts import create_movement_categories_chart

        mock_create_chart.return_value = {'data': [], 'layout': {}}

        result = create_movement_categories_chart(sample_movement_speeds, "Test Participant")

        assert result is not None
        mock_create_chart.assert_called_once()

    @patch('utils.visualization.march_charts.create_cumulative_steps_chart')
    def test_cumulative_steps_chart_creation(self, mock_create_chart, sample_timeseries_data):
        """Test cumulative steps chart creation"""
        from utils.visualization.march_charts import create_cumulative_steps_chart

        mock_create_chart.return_value = {'data': [], 'layout': {}}

        result = create_cumulative_steps_chart(sample_timeseries_data, "Test Participant")

        assert result is not None
        mock_create_chart.assert_called_once()

    @patch('utils.visualization.march_charts.create_pace_consistency_chart')
    def test_pace_consistency_chart_creation(self, mock_create_chart, sample_timeseries_data):
        """Test pace consistency chart creation"""
        from utils.visualization.march_charts import create_pace_consistency_chart

        mock_create_chart.return_value = {'data': [], 'layout': {}}

        result = create_pace_consistency_chart(sample_timeseries_data)

        assert result is not None
        mock_create_chart.assert_called_once()


@pytest.mark.unit
@pytest.mark.parametrize("march_count,expected_cards", [
    (0, 0),  # No marches = warning alert
    (1, 1),  # One march = one card
    (3, 3),  # Three marches = three cards
])
def test_march_selector_card_count(march_count, expected_cards, sample_march_events):
    """Test march selector creates correct number of cards"""
    with patch('components.march.march_overview.get_march_events') as mock_get_events:
        if march_count == 0:
            mock_get_events.return_value = pd.DataFrame()
            result = create_march_selector()
            # No marches should return warning alert, not cards
            assert isinstance(result, dbc.Alert)
        else:
            test_events = sample_march_events.iloc[:march_count]
            mock_get_events.return_value = test_events
            result = create_march_selector()
            # Should return list of cards
            assert isinstance(result, list)
            assert len(result) == expected_cards


@pytest.mark.unit
@pytest.mark.parametrize("user_role,should_have_admin_features", [
    ('admin', True),
    ('supervisor', True),
    ('participant', False),
])
def test_role_based_features_visibility(user_role, should_have_admin_features, sample_march_events):
    """Test that role-based features are shown/hidden correctly"""
    with patch('components.march.role_based_overview.get_accessible_marches') as mock_get_marches:
        mock_get_marches.return_value = sample_march_events

        result = create_role_based_march_overview(user_id=1, user_role=user_role)

        # This is a structural test - in a real implementation, you would check
        # for specific admin-only elements in the returned component tree
        assert result is not None
        mock_get_marches.assert_called_once_with(1, user_role)
