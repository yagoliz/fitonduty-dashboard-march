"""Individual participant detailed performance view component"""

from typing import Any

import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html

from utils.database import (
    get_march_timeseries_data,
    get_participant_hr_zones,
    get_participant_march_summary,
    get_participant_movement_speeds,
)
from utils.visualization.march_charts import (
    create_cumulative_steps_chart,
    create_hr_speed_timeline,
    create_hr_zones_chart,
    create_movement_speeds_chart,
    create_pace_consistency_chart,
    create_performance_summary_card_data,
)


def create_performance_summary_cards(summary_data: dict[str, Any]) -> dbc.Row:
    """Create performance summary cards showing key metrics"""

    card_data = create_performance_summary_card_data(summary_data)

    # Performance status badge
    status_color = "success" if summary_data.get('completed', False) else "warning"
    status_badge = dbc.Badge(
        card_data['completion_status'],
        color=status_color,
        className="mb-2"
    )

    cards = [
        # Duration & Completion
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6([
                        html.I(className="fas fa-clock me-2"),
                        "March Duration"
                    ], className="metric-label"),
                    html.H4(card_data['duration'], className="metric-value"),
                    status_badge
                ])
            ], className="h-100 metric-card")
        ], width=6, lg=3),

        # Average Pace
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6([
                        html.I(className="fas fa-tachometer-alt me-2"),
                        "Average Pace"
                    ], className="metric-label"),
                    html.H4(card_data['avg_pace'], className="metric-value"),
                    html.Small(f"Distance: {card_data['estimated_distance']}", className="text-muted")
                ])
            ], className="h-100 metric-card")
        ], width=6, lg=3),

        # Steps & Activity
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6([
                        html.I(className="fas fa-walking me-2"),
                        "Total Steps"
                    ], className="metric-label"),
                    html.H4(card_data['total_steps'], className="metric-value"),
                    html.Small(f"HR: {card_data['avg_hr']} avg / {card_data['max_hr']} max", className="text-muted")
                ])
            ], className="h-100 metric-card")
        ], width=6, lg=3),

        # Effort Score
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6([
                        html.I(className="fas fa-bolt me-2"),
                        "Effort Score"
                    ], className="metric-label"),
                    html.H4(card_data['effort_score'], className="metric-value"),
                    html.Small("Relative performance", className="text-muted")
                ])
            ], className="h-100 metric-card")
        ], width=6, lg=3),
    ]

    return dbc.Row(cards, className="mb-4")


def create_participant_detail_view(march_id: int, user_id: int) -> html.Div:
    """Create detailed performance view for a specific participant"""

    try:
        # Get participant data
        summary_data = get_participant_march_summary(march_id, user_id)
        hr_zones_data = get_participant_hr_zones(march_id, user_id)
        movement_data = get_participant_movement_speeds(march_id, user_id)
        timeseries_data = get_march_timeseries_data(march_id, user_id)

        if not summary_data:
            return html.Div([
                dbc.Alert(
                    [
                        html.H4("Participant Not Found", className="alert-heading"),
                        html.P("No performance data found for this participant in this march.")
                    ],
                    color="warning"
                )
            ])

        participant_name = summary_data.get('march_name', 'Unknown March')

        # Create summary cards
        summary_cards = create_performance_summary_cards(summary_data)

        # Create charts
        hr_speed_chart = create_hr_speed_timeline(timeseries_data, "March Performance")
        hr_zones_chart = create_hr_zones_chart(hr_zones_data)
        movement_chart = create_movement_speeds_chart(movement_data)
        steps_chart = create_cumulative_steps_chart(timeseries_data)
        pace_chart = create_pace_consistency_chart(timeseries_data)

        return html.Div([
            # Header
            dbc.Row([
                dbc.Col([
                    html.H2([
                        html.I(className="fas fa-chart-line me-2"),
                        "March Performance Analysis",
                        html.Small(f" - {participant_name}", className="text-muted ms-2")
                    ], className="text-gradient"),
                    html.Hr()
                ])
            ], className="mb-3"),

            # Performance Summary Cards
            summary_cards,

            # Main Timeline Chart
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H5([
                                html.I(className="fas fa-chart-line me-2"),
                                "Heart Rate & Speed Timeline"
                            ], className="mb-0 text-professional")
                        ]),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=hr_speed_chart,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="chart-container")
                ], width=12)
            ], className="mb-4"),

            # Analysis Charts Row 1
            dbc.Row([
                # HR Zones
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([
                                html.I(className="fas fa-heartbeat me-2"),
                                "Heart Rate Zones"
                            ], className="mb-0 text-professional")
                        ]),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=hr_zones_chart,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="chart-container")
                ], width=12, lg=6),

                # Movement Speeds
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([
                                html.I(className="fas fa-running me-2"),
                                "Movement Categories"
                            ], className="mb-0 text-professional")
                        ]),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=movement_chart,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="chart-container")
                ], width=12, lg=6)
            ], className="mb-4"),

            # Analysis Charts Row 2
            dbc.Row([
                # Cumulative Steps
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([
                                html.I(className="fas fa-walking me-2"),
                                "Step Progress"
                            ], className="mb-0 text-professional")
                        ]),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=steps_chart,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="chart-container")
                ], width=12, lg=6),

                # Pace Consistency
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H6([
                                html.I(className="fas fa-tachometer-alt me-2"),
                                "Pace Analysis"
                            ], className="mb-0 text-professional")
                        ]),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=pace_chart,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="chart-container")
                ], width=12, lg=6)
            ], className="mb-4")

        ])

    except Exception as e:
        return html.Div([
            dbc.Alert(
                [
                    html.H4("Error Loading Data", className="alert-heading"),
                    html.P(f"Unable to load participant performance data: {str(e)}")
                ],
                color="danger"
            )
        ])


def create_participant_selector_modal(participants_data: pd.DataFrame) -> dbc.Modal:
    """Create modal for selecting which participant to view in detail"""

    if participants_data.empty:
        options = []
    else:
        options = [
            {
                'label': f"{row['username']} - {row['finish_time_minutes']}min ({row['effort_score']:.1f} effort)",
                'value': row['user_id']
            }
            for _, row in participants_data.iterrows()
            if row['completed']
        ]

    return dbc.Modal([
        dbc.ModalHeader([
            dbc.ModalTitle("Select Participant for Detailed Analysis")
        ]),
        dbc.ModalBody([
            html.P("Choose a participant to view their detailed march performance:"),
            dcc.Dropdown(
                id="participant-selector-dropdown",
                options=options,
                placeholder="Select a participant...",
                className="mb-3"
            )
        ]),
        dbc.ModalFooter([
            dbc.Button(
                "View Analysis",
                id="view-participant-btn",
                color="primary",
                disabled=True
            ),
            dbc.Button(
                "Cancel",
                id="cancel-participant-btn",
                color="secondary",
                className="ms-2"
            )
        ])
    ], id="participant-selector-modal", size="lg")


def create_back_to_overview_button(march_id: int) -> dbc.Row:
    """Create navigation button to return to march overview"""

    return dbc.Row([
        dbc.Col([
            dbc.Button(
                [
                    html.I(className="fas fa-arrow-left me-2"),
                    "Back to March Overview"
                ],
                id={"type": "back-to-march-btn", "march_id": march_id},
                color="outline-primary",
                size="sm",
                className="btn-outline-professional"
            )
        ], width="auto")
    ], className="mb-3")


def create_participant_comparison_button(march_id: int) -> dbc.Col:
    """Create button to compare multiple participants"""

    return dbc.Col([
        dbc.Button(
            [
                html.I(className="fas fa-users me-2"),
                "Compare Participants"
            ],
            id="compare-participants-btn",
            color="info",
            size="sm",
            outline=True,
            className="btn-outline-professional"
        )
    ], width="auto")
