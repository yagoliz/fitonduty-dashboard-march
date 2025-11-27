"""Role-based March Overview Component"""

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html, dcc
from flask_login import current_user

from components.auth import create_access_denied
from utils.auth import get_accessible_marches, user_can_view_march
from utils.database import (
    get_march_leaderboard,
    get_march_participants,
    get_participant_march_summary,
)


def create_role_based_march_overview(march_id: int | None = None):
    """Create role-based march overview that respects user permissions"""

    if not current_user.is_authenticated:
        return create_access_denied("Please log in to view march data.")

    if march_id is None:
        # Show march selection based on user role
        return create_accessible_march_selector()

    # Check if user can view this specific march
    if not user_can_view_march(current_user.id, march_id, current_user.role):
        return create_access_denied("You don't have permission to view this march.")

    try:
        # Get march data based on user role
        accessible_marches = get_accessible_marches(current_user.id, current_user.role)
        march_data = accessible_marches[accessible_marches['id'] == march_id]

        if march_data.empty:
            return create_access_denied("March not found or you don't have access.")

        march_info = march_data.iloc[0]

        # Different views for different roles
        if current_user.role == 'admin':
            return create_admin_march_view(march_id, march_info)
        elif current_user.role == 'supervisor':
            return create_supervisor_march_view(march_id, march_info)
        else:  # participant
            return create_participant_march_view(march_id, march_info)

    except Exception as e:
        return dbc.Alert(
            f"Error loading march data: {str(e)}",
            color="danger",
            className="mt-3"
        )


def create_accessible_march_selector():
    """Create march selection interface based on user role"""

    try:
        accessible_marches = get_accessible_marches(current_user.id, current_user.role)

        if accessible_marches is None or accessible_marches.empty:
            if current_user.role == 'participant':
                message = "You haven't participated in any marches yet."
            else:
                message = "No marches available."

            return dbc.Alert(message, color="info", className="mt-3")

        # Create march cards
        march_cards = []
        for _, march in accessible_marches.iterrows():
            # Different card styling based on user role and march status
            card_color = "light"
            if hasattr(march, 'user_completed') and march['user_completed']:
                card_color = "success"
            elif current_user.role == 'admin':
                card_color = "primary" if march['status'] == 'published' else "secondary"

            href = f"/march/{march['id']}"
            card = dbc.Card([
                dbc.CardBody([
                    html.H5([
                        march['name'],
                        _get_status_badge(march, current_user.role)
                    ], className="card-title mb-2"),
                    html.P([
                        html.I(className="fas fa-calendar me-2"), html.Strong("Date: "), f"{march['date']}", html.Br(),
                        html.I(className="fas fa-route me-2"), html.Strong("Distance: "), f"{march['distance_km']} km" if pd.notna(march['distance_km']) else "TBD", html.Br(),
                        html.I(className="fas fa-users me-2"), html.Strong("Participants: "), f"{march['completed_count']}/{march['participant_count']} completed"
                    ], className="card-text mb-0"),
                    html.Div([
                        html.Span([_get_view_button_text(march, current_user.role), " ", html.I(className="fas fa-chevron-right")], className="link-subtle small")
                    ], className="mt-2")
                ])
            ], color=card_color, outline=True, className="mb-3 card-clickable")
            march_cards.append(dcc.Link(card, href=href, className="card-link-wrapper"))

        title_text = _get_selector_title(current_user.role)

        role_icon = {
            'admin': 'fas fa-cogs',
            'supervisor': 'fas fa-user-shield',
            'participant': 'fas fa-running'
        }.get(current_user.role, 'fas fa-list')
        return html.Div([
            html.H4([
                html.I(className=f"{role_icon} me-2"),
                title_text
            ], className="section-title"),
            html.P(_get_selector_description(current_user.role), className="text-muted mb-4"),
            html.Div(march_cards)
        ])

    except Exception as e:
        return dbc.Alert(f"Error loading marches: {str(e)}", color="danger")


def create_admin_march_view(march_id: int, march_info):
    """Create admin view with full access to all participants and data"""

    participants = get_march_participants(march_id)

    # Back button
    back_button = _create_back_button()

    # March header with admin controls
    march_header = _create_march_header(march_info, show_admin_controls=True)

    # Full participant table with all data
    participants_component = _create_admin_participants_table(participants)

    return html.Div([
        back_button,
        march_header,
        dbc.Row([
            dbc.Col([
                html.H5([
                    html.I(className="fas fa-users me-2 text-info"),
                    "All Participants"
                ], className="section-title"),
                participants_component
            ], md=12)
        ])
    ])


def create_supervisor_march_view(march_id: int, march_info):
    """Create supervisor view with access to group participants"""

    participants = get_march_participants(march_id)
    leaderboard = get_march_leaderboard(march_id, 'effort_score')

    # Back button
    back_button = _create_back_button()

    # March header
    march_header = _create_march_header(march_info, show_admin_controls=False)

    # Participant table (similar to admin but maybe with some restrictions)
    participants_component = _create_supervisor_participants_table(participants)
    leaderboard_component = _create_leaderboard_table(leaderboard)

    return html.Div([
        back_button,
        march_header,
        dbc.Row([
            dbc.Col([
                html.H5([
                    html.I(className="fas fa-trophy me-2 text-warning"),
                    "Leaderboard"
                ], className="section-title"),
                leaderboard_component
            ], md=6),
            dbc.Col([
                html.H5([
                    html.I(className="fas fa-users me-2 text-info"),
                    "Participants in Your Groups"
                ], className="section-title"),
                participants_component
            ], md=6)
        ])
    ])


def create_participant_march_view(march_id: int, march_info):
    """Create participant view with personal data and limited group leaderboard"""

    # Get participant's own march data
    user_summary = get_participant_march_summary(march_id, current_user.id)

    if not user_summary:
        return dbc.Alert(
            "No march data found for your participation.",
            color="warning"
        )

    # Get leaderboard (participants can see overall rankings but not detailed personal data of others)
    leaderboard = get_march_leaderboard(march_id, 'effort_score')

    # Back button
    back_button = _create_back_button()

    # March header
    march_header = _create_march_header(march_info, show_admin_controls=False)

    # Personal performance card
    personal_card = _create_personal_performance_card(
        user_summary,
        leaderboard,
        detail_href=f"/march/{march_id}/participant/{current_user.id}"
    )

    # Limited leaderboard (just rankings, no detailed metrics)
    leaderboard_component = _create_participant_leaderboard_table(leaderboard, current_user.username)

    return html.Div([
        back_button,
        march_header,
        dbc.Row([
            dbc.Col([
                html.H5([
                    html.I(className="fas fa-chart-bar me-2 text-success"),
                    "Your Performance"
                ], className="section-title"),
                personal_card
            ], md=12)
        ], className="mb-4")
    ])


# Helper functions
def _get_status_badge(march, user_role):
    """Get appropriate status badge for march"""
    if user_role == 'participant' and hasattr(march, 'user_completed'):
        if march['user_completed']:
            return dbc.Badge("✅ Completed", color="success", className="ms-2")
        else:
            return dbc.Badge("❌ DNF", color="danger", className="ms-2")
    elif user_role in ['admin', 'supervisor']:
        status_colors = {
            'draft': 'secondary',
            'published': 'primary',
            'completed': 'success',
            'cancelled': 'danger'
        }
        return dbc.Badge(
            march['status'].title(),
            color=status_colors.get(march['status'], 'light'),
            className="ms-2"
        )
    return html.Span()


def _get_view_button_text(march, user_role):
    """Get appropriate button text based on role and march status"""
    if user_role == 'participant':
        return "View My Results"
    else:
        return "View Results"


def _get_selector_title(user_role):
    """Get appropriate title for march selector"""
    titles = {
        'admin': 'All March Events',
        'supervisor': 'March Events - Supervisor View',
        'participant': 'My March Participation'
    }
    return titles.get(user_role, 'March Events')


def _get_selector_description(user_role):
    """Get appropriate description for march selector"""
    descriptions = {
        'admin': 'Manage and view all march events and participant data.',
        'supervisor': 'View march events and monitor participant performance in your groups.',
        'participant': 'View your march participation history and performance results.'
    }
    return descriptions.get(user_role, 'Select a march to view details.')


def _create_back_button():
    """Create back to marches button"""
    return dbc.Row([
        dbc.Col([
            dbc.Button([
                html.I(className="fas fa-arrow-left me-2"),
                "Back to All Marches"
            ],
            id="back-to-all-marches-btn",
            color="outline-secondary",
            size="sm")
        ], width="auto")
    ], className="mb-3")


def _create_march_header(march_info, show_admin_controls=False):
    """Create march header with optional admin controls"""

    header_content = [
        html.H3(march_info['name'], className="card-title"),
        dbc.Row([
            dbc.Col([
                html.P([
                    html.Strong("📅 Date: "), str(march_info['date']), html.Br(),
                    html.Strong("📏 Distance: "), f"{march_info['distance_km']} km" if pd.notna(march_info['distance_km']) else "TBD", html.Br(),
                    html.Strong("⏱️ Duration: "), f"{march_info['duration_hours']} hours" if pd.notna(march_info['duration_hours']) else "TBD"
                ])
            ], md=6),
            dbc.Col([
                html.P([
                    html.Strong("👥 Group: "), march_info['group_name'], html.Br(),
                    html.Strong("✅ Completed: "), f"{march_info['completed_count']}/{march_info['participant_count']}", html.Br(),
                    html.Strong("📊 Status: "), march_info['status'].title()
                ])
            ], md=6)
        ]),
        html.P(march_info.get('route_description', ''), className="text-muted")
    ]

    if show_admin_controls:
        admin_controls = dbc.Row([
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button("📝 Edit March", size="sm", color="outline-primary"),
                    dbc.Button("📊 Export Data", size="sm", color="outline-success"),
                    dbc.Button("📧 Send Report", size="sm", color="outline-info")
                ])
            ])
        ], className="mt-3")
        header_content.append(admin_controls)

    return dbc.Card([
        dbc.CardBody(header_content)
    ], className="mb-4")


def _create_admin_participants_table(participants_df):
    """Create full participants table for admin"""
    # Reuse existing function but with admin permissions
    from components.march.march_overview import create_participants_table
    return create_participants_table(participants_df)


def _create_supervisor_participants_table(participants_df):
    """Create participants table for supervisor"""
    # Similar to admin but maybe filtered to their groups
    from components.march.march_overview import create_participants_table
    return create_participants_table(participants_df)


def _create_leaderboard_table(leaderboard_df):
    """Create leaderboard table"""
    from components.march.march_overview import create_leaderboard_table
    return create_leaderboard_table(leaderboard_df)


def _create_participant_leaderboard_table(leaderboard_df, current_username):
    """Create limited leaderboard for participants (highlight current user)"""
    if leaderboard_df.empty:
        return dbc.Alert("No leaderboard data available", color="info")

    table_rows = []
    for _, row in leaderboard_df.iterrows():
        # Highlight current user and accent top ranks
        classes = []
        if row['username'] == current_username:
            classes.append("table-success")
        try:
            r = int(row['rank'])
            if r in (1, 2, 3):
                classes.append(f"row-top-{r}")
        except Exception:
            pass
        row_class = " ".join(classes)

        # Medal emoji for top 3
        rank_display = row['rank']
        if rank_display == 1:
            rank_display = "🥇 1st"
        elif rank_display == 2:
            rank_display = "🥈 2nd"
        elif rank_display == 3:
            rank_display = "🥉 3rd"
        else:
            rank_display = f"{rank_display}th"

        username_display = row['username']
        if row['username'] == current_username:
            username_display = html.Strong([username_display, " (You)"])

        table_row = html.Tr([
            html.Td(rank_display),
            html.Td(username_display),
            html.Td(f"{row['avg_hr']} bpm" if pd.notna(row['avg_hr']) else "-", className="numeric"),
            html.Td(f"{row['finish_time_minutes']} min" if pd.notna(row['finish_time_minutes']) else "-", className="numeric")
        ], className=row_class)
        table_rows.append(table_row)

    table = dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Rank"),
                html.Th("Participant"),
                html.Th("Avg HR"),
                html.Th("Finish Time")
            ])
        ]),
        html.Tbody(table_rows)
    ], striped=True, hover=True, size="sm", className="table-professional table-compact")

    return html.Div(table, className="table-responsive")


def _create_personal_performance_card(user_summary, leaderboard_df=None, detail_href: str | None = None):
    """Create personal performance summary card with KPIs and effort bar"""

    completed = bool(user_summary.get('completed'))
    finish_time = user_summary.get('finish_time_minutes')
    avg_hr = user_summary.get('avg_hr')
    max_hr = user_summary.get('max_hr')
    steps = user_summary.get('total_steps')
    pace = user_summary.get('avg_pace_kmh')

    # Header badges: completion + rank/percentile
    completion_badge = dbc.Badge(
        "Completed" if completed else "Did Not Finish",
        color="success" if completed else "danger",
        className="me-2"
    )

    # Rank / percentile badge
    # rank_badge = html.Span()
    # if leaderboard_df is not None and not leaderboard_df.empty:
    #     try:
    #         total = len(leaderboard_df)
    #         row = leaderboard_df[leaderboard_df['username'] == current_user.username]
    #         if not row.empty and 'rank' in row.columns:
    #             rank_val = int(row.iloc[0]['rank'])
    #             pct = rank_val / total if total else 1
    #             if pct <= 0.1:
    #                 rank_badge = dbc.Badge("Top 10%", color="warning", className="me-2")
    #             elif pct <= 0.25:
    #                 rank_badge = dbc.Badge("Top 25%", color="info", className="me-2")
    #             else:
    #                 rank_badge = dbc.Badge(f"Rank {rank_val}/{total}", color="light", className="me-2")
    #     except Exception:
    #         pass

    # KPI chips
    def fmt(v, fmt_str, na="N/A"):
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return na
            return fmt_str.format(v)
        except Exception:
            return na

    avg_core_temp = user_summary.get('avg_core_temp')

    kpis = dbc.Row([
        dbc.Col(html.Div([
            html.I(className="fas fa-tachometer-alt me-2"),
            html.Span(fmt(pace, "{:.1f} km/h"), className="kpi-value"),
            html.Div("Avg Pace", className="kpi-label")
        ], className="kpi-chip")),
        dbc.Col(html.Div([
            html.I(className="fas fa-heartbeat me-2"),
            html.Span(fmt(avg_hr, "{} bpm"), className="kpi-value"),
            html.Div("Avg HR", className="kpi-label")
        ], className="kpi-chip")),
        dbc.Col(html.Div([
            html.I(className="fas fa-walking me-2"),
            html.Span(fmt(steps, "{:,.0f}"), className="kpi-value"),
            html.Div("Steps", className="kpi-label")
        ], className="kpi-chip")),
        dbc.Col(html.Div([
            html.I(className="fas fa-clock me-2"),
            html.Span(fmt(finish_time, "{} min"), className="kpi-value"),
            html.Div("Finish Time", className="kpi-label")
        ], className="kpi-chip")),
        dbc.Col(html.Div([
            html.I(className="fas fa-thermometer-half me-2"),
            html.Span(fmt(avg_core_temp, "{:.1f} °C"), className="kpi-value"),
            html.Div("Avg Core Temp", className="kpi-label")
        ], className="kpi-chip"))
    ], className="g-2 mb-2 row-cols-2 row-cols-sm-3 row-cols-md-5")

    # Group deltas (optional, if leaderboard has fields)
    deltas_row = html.Div()
    if leaderboard_df is not None and not leaderboard_df.empty:
        try:
            avg_group_pace = leaderboard_df['avg_pace_kmh'].dropna().mean() if 'avg_pace_kmh' in leaderboard_df.columns else None
            avg_group_hr = leaderboard_df['avg_hr'].dropna().mean() if 'avg_hr' in leaderboard_df.columns else None
            delta_pace = None if avg_group_pace is None or pace is None or pd.isna(pace) else pace - avg_group_pace
            delta_hr = None if avg_group_hr is None or avg_hr is None or pd.isna(avg_hr) else avg_hr - avg_group_hr

            def delta_badge(val, label):
                if val is None:
                    return html.Span()
                color = "success" if val >= 0 else "danger"
                arrow = "▲" if val >= 0 else "▼"
                display = f"{label} {arrow} {abs(val):.1f} vs group"
                return dbc.Badge(display, color=color, className="me-2")

            deltas_row = html.Div([
                delta_badge(delta_pace, "Pace"),
                delta_badge(delta_hr, "HR")
            ], className="mb-2")
        except Exception:
            pass

    # Footer metrics
    footer = html.Div()
    if max_hr:
        footer = html.Div([
            html.Small([
                html.I(className="fas fa-heartbeat me-1"),
                "Max HR: ",
                fmt(max_hr, "{} bpm")
            ], className="text-muted")
        ])

    # Optional subtle inline CTA label (non-link if card is wrapped as a link)
    cta_link = html.Span()
    if detail_href:
        cta_link = html.Span([
            html.Span("View detailed analysis", className="me-1"),
            html.I(className="fas fa-chevron-right")
        ], className="link-subtle float-end")

    card_inner = dbc.Card([
        dbc.CardBody([
            html.Div([
                # html.Div([completion_badge, rank_badge], className="mb-2"),
                html.Div([completion_badge], className="mb-2"),
                cta_link
            ], className="d-flex justify-content-between align-items-start"),
            kpis,
            deltas_row,
            html.Div(footer, className="mt-2")
        ])
    ], className="card-professional card-clickable")

    if detail_href:
        return dcc.Link(card_inner, href=detail_href, className="card-link-wrapper")
    return card_inner
