"""March Overview Component - Shows basic march information and participant list"""

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html, dcc

from utils.database import get_march_events, get_march_leaderboard, get_march_participants


def create_march_overview(march_id: int | None = None):
    """Create march overview component showing march details and participants"""

    if march_id is None:
        # Show march selection if no specific march
        return create_march_selector()

    try:
        # Get march data
        march_events = get_march_events()
        march_data = march_events[march_events['id'] == march_id]

        if march_data.empty:
            return create_error_message("March not found")

        march_info = march_data.iloc[0]
        participants = get_march_participants(march_id)
        leaderboard = get_march_leaderboard(march_id, 'effort_score')

        return create_march_detail_view(march_info, participants, leaderboard)

    except Exception as e:
        return create_error_message(f"Error loading march data: {str(e)}")


def create_march_selector():
    """Create march selection interface"""

    try:
        march_events = get_march_events(status='published')

        if march_events.empty:
            return dbc.Alert(
                "No completed marches available. Please check that the database has been seeded.",
                color="warning"
            )

        march_cards = []
        for _, march in march_events.iterrows():
            href = f"/march/{march['id']}"
            card = dbc.Card([
                dbc.CardBody([
                    html.H5(march['name'], className="card-title text-professional mb-2"),
                    html.P([
                        html.I(className="fas fa-calendar me-2"), html.Strong("Date: "), f"{march['date']}", html.Br(),
                        html.I(className="fas fa-route me-2"), html.Strong("Distance: "), f"{march['distance_km']} km" if pd.notna(march['distance_km']) else "TBD", html.Br(),
                        html.I(className="fas fa-clock me-2"), html.Strong("Duration: "), f"{march['duration_hours']} hours" if pd.notna(march['duration_hours']) else "TBD", html.Br(),
                        html.I(className="fas fa-users me-2"), html.Strong("Participants: "), f"{march['completed_count']}/{march['participant_count']} completed"
                    ], className="card-text mb-0"),
                    html.Div([
                        html.Span(["View results ", html.I(className="fas fa-chevron-right")], className="link-subtle small")
                    ], className="mt-2")
                ])
            ], className="mb-3 performance-card card-clickable")
            march_cards.append(dcc.Link(card, href=href, className="card-link-wrapper"))

        return html.Div([
            html.H4([
                html.I(className="fas fa-list-alt me-2"),
                "Available March Results"
            ], className="section-title"),
            html.P("Select a march to view detailed results and participant performance.", className="text-muted mb-4"),
            html.Div(march_cards)
        ])

    except Exception as e:
        return create_error_message(f"Error loading marches: {str(e)}")


def create_march_detail_view(march_info, participants_df, leaderboard_df):
    """Create detailed march view with participants and leaderboard"""

    # Back to all marches button
    back_button = dbc.Row([
        dbc.Col([
            dbc.Button(
                [
                    html.I(className="fas fa-arrow-left me-2"),
                    "Back to All Marches"
                ],
                id="back-to-all-marches-btn",
                color="outline-secondary",
                size="sm"
            )
        ], width="auto")
    ], className="mb-3")

    # March header
    march_header = dbc.Card([
        dbc.CardBody([
            html.H3(march_info['name'], className="card-title text-gradient mb-3"),
            dbc.Row([
                dbc.Col([
                    html.P([
                        html.I(className="fas fa-calendar me-2"), html.Strong("Date: "), str(march_info['date']), html.Br(),
                        html.I(className="fas fa-route me-2"), html.Strong("Distance: "), f"{march_info['distance_km']} km" if pd.notna(march_info['distance_km']) else "TBD", html.Br(),
                        html.I(className="fas fa-clock me-2"), html.Strong("Duration: "), f"{march_info['duration_hours']} hours" if pd.notna(march_info['duration_hours']) else "TBD"
                    ])
                ], md=6),
                dbc.Col([
                    html.P([
                        html.I(className="fas fa-users me-2"), html.Strong("Group: "), march_info['group_name'], html.Br(),
                        html.I(className="fas fa-check-circle me-2"), html.Strong("Completed: "), f"{march_info['completed_count']}/{march_info['participant_count']}", html.Br(),
                        html.I(className="fas fa-info-circle me-2"), html.Strong("Status: "), march_info['status'].title()
                    ])
                ], md=6)
            ]),
            html.Hr(),
            html.P(march_info['route_description'], className="text-muted fst-italic")
        ])
    ], className="mb-4 card-professional")

    # Leaderboard
    leaderboard_component = create_leaderboard_table(leaderboard_df)

    # Participants list
    participants_component = create_participants_table(participants_df)

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
                "All Participants"
            ], className="section-title"),
                participants_component
            ], md=6)
        ])
    ])


def create_leaderboard_table(leaderboard_df):
    """Create leaderboard table component"""

    if leaderboard_df.empty:
        return dbc.Alert("No leaderboard data available", color="info")

    table_rows = []
    for _, row in leaderboard_df.iterrows():
        # Medal styling for top 3
        rank_display = row['rank']
        if rank_display == 1:
            rank_display = dbc.Badge("1st", color="warning", className="rank-badge rank-1")
        elif rank_display == 2:
            rank_display = dbc.Badge("2nd", color="secondary", className="rank-badge rank-2")
        elif rank_display == 3:
            rank_display = dbc.Badge("3rd", color="warning", className="rank-badge rank-3")
        else:
            rank_display = dbc.Badge(f"{rank_display}th", color="light", className="rank-badge")

        # Row accent for top 3
        row_class = ""
        try:
            r = int(row['rank'])
            if r in (1, 2, 3):
                row_class = f"row-top-{r}"
        except Exception:
            pass

        table_row = html.Tr([
            html.Td(rank_display),
            html.Td(row['username']),
            html.Td(f"{row['avg_hr']} bpm" if pd.notna(row['avg_hr']) else "-", className="numeric"),
            html.Td(f"{row['finish_time_minutes']} min" if pd.notna(row['finish_time_minutes']) else "-", className="numeric"),
            html.Td(f"{row['avg_pace_kmh']:.1f} km/h" if pd.notna(row['avg_pace_kmh']) else "-", className="numeric")
        ], className=row_class)
        table_rows.append(table_row)

    table = dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Rank"),
                html.Th("Participant"),
                html.Th("Avg HR"),
                html.Th("Time"),
                html.Th("Avg Pace")
            ])
        ]),
        html.Tbody(table_rows)
    ], striped=True, hover=True, size="sm", className="table-professional table-compact")
    # Wrap table for horizontal responsiveness on small screens
    return html.Div(table, className="table-responsive")


def create_participants_table(participants_df):
    """Create participants table component"""

    if participants_df.empty:
        return dbc.Alert("No participant data available", color="info")

    table_rows = []
    for _, row in participants_df.iterrows():
        # Status indicator
        status_badge = dbc.Badge([
            html.I(className="fas fa-check me-1" if row['completed'] else "fas fa-times me-1"),
            "Completed" if row['completed'] else "Did not finish"
        ],
            color="success" if row['completed'] else "danger",
            className="me-2 status-completed" if row['completed'] else "me-2 status-failed"
        )

        row_class = "row-completed" if row['completed'] else "row-dnf"

        # Create clickable participant name if completed
        if row['completed']:
            participant_link = dcc.Link(
                [status_badge, row['username']],
                href=f"/march/{row['march_id']}/participant/{row['user_id']}",
                className="text-decoration-none"
            )
        else:
            participant_link = html.Span([status_badge, row['username']])

        table_row = html.Tr([
            html.Td(participant_link),
            html.Td(f"{row['avg_hr']:.0f}" if pd.notna(row['avg_hr']) else "-", className="text-center"),
            html.Td(f"{row['max_hr']:.0f}" if pd.notna(row['max_hr']) else "-", className="text-center"),
            html.Td(f"{row['avg_core_temp']:.1f}" if pd.notna(row['avg_core_temp']) else "-", className="text-center"),
            html.Td(f"{row['finish_time_minutes']:.0f}" if pd.notna(row['finish_time_minutes']) else "-", className="text-center"),
            html.Td(f"{row['total_steps']:,}" if pd.notna(row['total_steps']) else "-", className="text-center"),
            html.Td(f"{row['estimated_distance_km']:.2f}" if pd.notna(row['estimated_distance_km']) else "-", className="text-center"),
            html.Td(f"{row['avg_pace_kmh']:.2f}" if pd.notna(row['avg_pace_kmh']) else "-", className="text-center")
        ], className=row_class)
        table_rows.append(table_row)

    table = dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Participant"),
                html.Th("Avg HR (bpm)", className="text-center"),
                html.Th("Max HR (bpm)", className="text-center"),
                html.Th("Avg Core Temp (°C)", className="text-center"),
                html.Th("Finish Time (min)", className="text-center"),
                html.Th("Total Steps", className="text-center"),
                html.Th("Distance (km)", className="text-center"),
                html.Th("Avg Pace (km/h)", className="text-center")
            ])
        ]),
        html.Tbody(table_rows)
    ], striped=True, hover=True, size="sm", className="table-professional table-compact")
    # Wrap table for horizontal responsiveness on small screens
    return html.Div(table, className="table-responsive")


def create_error_message(message: str):
    """Create error message component"""
    return dbc.Alert([
        html.H5([
            html.I(className="fas fa-exclamation-triangle me-2"),
            "Error"
        ], className="alert-heading"),
        html.P(message),
        html.P("Please check the database connection and ensure the data has been seeded.", className="mb-0")
    ], color="danger")
