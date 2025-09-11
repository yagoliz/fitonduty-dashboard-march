"""March Overview Component - Shows basic march information and participant list"""

import dash_bootstrap_components as dbc
import pandas as pd
from dash import html

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
            card = dbc.Card([
                dbc.CardBody([
                    html.H5(march['name'], className="card-title"),
                    html.P([
                        html.Strong("Date: "), f"{march['date']}", html.Br(),
                        html.Strong("Distance: "), f"{march['distance_km']} km" if pd.notna(march['distance_km']) else "TBD", html.Br(),
                        html.Strong("Duration: "), f"{march['duration_hours']} hours" if pd.notna(march['duration_hours']) else "TBD", html.Br(),
                        html.Strong("Participants: "), f"{march['completed_count']}/{march['participant_count']} completed"
                    ], className="card-text"),
                    dbc.Button(
                        "View Results",
                        color="primary",
                        size="sm",
                        id={"type": "view-march-btn", "march_id": march['id']}
                    )
                ])
            ], className="mb-3")
            march_cards.append(card)

        return html.Div([
            html.H4("Available March Results"),
            html.P("Select a march to view detailed results and participant performance."),
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
            html.P(march_info['route_description'], className="text-muted")
        ])
    ], className="mb-4")

    # Leaderboard
    leaderboard_component = create_leaderboard_table(leaderboard_df)

    # Participants list
    participants_component = create_participants_table(participants_df)

    return html.Div([
        back_button,
        march_header,
        dbc.Row([
            dbc.Col([
                html.H5("🏆 Leaderboard"),
                leaderboard_component
            ], md=6),
            dbc.Col([
                html.H5("👥 All Participants"),
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

        table_row = html.Tr([
            html.Td(rank_display),
            html.Td(row['username']),
            html.Td(f"{row['effort_score']:.1f}" if pd.notna(row['effort_score']) else "-"),
            html.Td(f"{row['finish_time_minutes']} min" if pd.notna(row['finish_time_minutes']) else "-"),
            html.Td(f"{row['avg_pace_kmh']:.1f} km/h" if pd.notna(row['avg_pace_kmh']) else "-")
        ])
        table_rows.append(table_row)

    table = dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Rank"),
                html.Th("Participant"),
                html.Th("Effort Score"),
                html.Th("Time"),
                html.Th("Avg Pace")
            ])
        ]),
        html.Tbody(table_rows)
    ], striped=True, hover=True, size="sm")

    return table


def create_participants_table(participants_df):
    """Create participants table component"""

    if participants_df.empty:
        return dbc.Alert("No participant data available", color="info")

    table_rows = []
    for _, row in participants_df.iterrows():
        # Status indicator
        status_badge = dbc.Badge(
            "✅ Completed" if row['completed'] else "❌ Did not finish",
            color="success" if row['completed'] else "danger",
            className="me-2"
        )

        table_row = html.Tr([
            html.Td([status_badge, row['username']]),
            html.Td(f"{row['avg_hr']} bpm" if pd.notna(row['avg_hr']) else "-"),
            html.Td(f"{row['total_steps']:,}" if pd.notna(row['total_steps']) else "-"),
            html.Td(
                dbc.Button(
                    "View Details",
                    size="sm",
                    color="outline-primary",
                    id={"type": "view-participant-btn", "user_id": row['user_id'], "march_id": row['march_id']}
                ) if row['completed'] else "-"
            )
        ])
        table_rows.append(table_row)

    table = dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Participant"),
                html.Th("Avg HR"),
                html.Th("Total Steps"),
                html.Th("Actions")
            ])
        ]),
        html.Tbody(table_rows)
    ], striped=True, hover=True, size="sm")

    return table


def create_error_message(message: str):
    """Create error message component"""
    return dbc.Alert([
        html.H5("⚠️ Error", className="alert-heading"),
        html.P(message),
        html.P("Please check the database connection and ensure the data has been seeded.", className="mb-0")
    ], color="danger")
