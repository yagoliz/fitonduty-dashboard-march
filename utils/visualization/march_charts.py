"""March-specific visualization components using Plotly"""

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_hr_speed_timeline(timeseries_data: pd.DataFrame, participant_name: str = "Participant") -> go.Figure:
    """Create dual-axis timeline showing HR and speed progression during march"""

    if timeseries_data.empty:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="No time-series data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16, color="gray")
        )
        return fig

    # Create subplot with secondary y-axis
    fig = make_subplots(
        rows=1, cols=1,
        specs=[[{"secondary_y": True}]],
        subplot_titles=[f"{participant_name} - Heart Rate & Speed During March"]
    )

    # Heart Rate trace
    fig.add_trace(
        go.Scatter(
            x=timeseries_data['timestamp_minutes'],
            y=timeseries_data['heart_rate'],
            mode='lines+markers',
            name='Heart Rate',
            line=dict(color='#e74c3c', width=2),
            marker=dict(size=4),
            hovertemplate='<b>Time:</b> %{x} min<br><b>HR:</b> %{y} bpm<extra></extra>'
        ),
        secondary_y=False,
    )

    # Speed trace
    fig.add_trace(
        go.Scatter(
            x=timeseries_data['timestamp_minutes'],
            y=timeseries_data['estimated_speed_kmh'],
            mode='lines+markers',
            name='Speed',
            line=dict(color='#3498db', width=2),
            marker=dict(size=4),
            hovertemplate='<b>Time:</b> %{x} min<br><b>Speed:</b> %{y:.1f} km/h<extra></extra>'
        ),
        secondary_y=True,
    )

    # Update x-axis
    fig.update_xaxes(
        title_text="Time (minutes)",
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(128,128,128,0.2)'
    )

    # Update y-axes
    fig.update_yaxes(
        title_text="Heart Rate (bpm)",
        secondary_y=False,
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(231,76,60,0.1)'
    )

    fig.update_yaxes(
        title_text="Speed (km/h)",
        secondary_y=True,
        showgrid=False
    )

    # Update layout
    fig.update_layout(
        height=400,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50)
    )

    return fig


def create_hr_zones_chart(hr_zones_data: dict[str, float]) -> go.Figure:
    """Create doughnut chart showing heart rate zone distribution"""

    if not hr_zones_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No HR zones data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16, color="gray")
        )
        return fig

    zone_labels = ['Very Light', 'Light', 'Moderate', 'Intense', 'Beast Mode']
    zone_colors = ['#95a5a6', '#f39c12', '#e67e22', '#e74c3c', '#8e44ad']

    values = [
        hr_zones_data.get('very_light_percent', 0),
        hr_zones_data.get('light_percent', 0),
        hr_zones_data.get('moderate_percent', 0),
        hr_zones_data.get('intense_percent', 0),
        hr_zones_data.get('beast_mode_percent', 0)
    ]

    # Filter out zero values for cleaner chart
    filtered_data = [(label, value, color) for label, value, color in zip(zone_labels, values, zone_colors, strict=False) if value > 0]

    if not filtered_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No HR zone data",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16, color="gray")
        )
        return fig

    labels, values, colors = zip(*filtered_data, strict=False)

    fig = go.Figure(data=[
        go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(colors=colors),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate='<b>%{label}</b><br>%{percent}<br>%{value:.1f}%<extra></extra>'
        )
    ])

    fig.update_layout(
        title=dict(
            text="Heart Rate Zones Distribution",
            x=0.5,
            xanchor='center'
        ),
        height=300,
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05
        )
    )

    return fig


def create_movement_speeds_chart(movement_data: dict[str, int]) -> go.Figure:
    """Create horizontal bar chart showing time spent in different movement speeds"""

    if not movement_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No movement data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16, color="gray")
        )
        return fig

    categories = ['Walking', 'Walking Fast', 'Jogging', 'Running', 'Stationary']
    values = [
        movement_data.get('walking_minutes', 0),
        movement_data.get('walking_fast_minutes', 0),
        movement_data.get('jogging_minutes', 0),
        movement_data.get('running_minutes', 0),
        movement_data.get('stationary_minutes', 0)
    ]
    colors = ['#3498db', '#2ecc71', '#f39c12', '#e74c3c', '#95a5a6']

    # Filter out zero values
    filtered_data = [(cat, val, color) for cat, val, color in zip(categories, values, colors, strict=False) if val > 0]

    if not filtered_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No movement data",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16, color="gray")
        )
        return fig

    categories, values, colors = zip(*filtered_data, strict=False)

    fig = go.Figure(data=[
        go.Bar(
            y=categories,
            x=values,
            orientation='h',
            marker=dict(color=colors),
            hovertemplate='<b>%{y}</b><br>%{x} minutes<extra></extra>'
        )
    ])

    fig.update_layout(
        title=dict(
            text="Time Spent in Movement Categories",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Minutes",
        height=250,
        margin=dict(l=100, r=50, t=60, b=50),
        showlegend=False
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(showgrid=False)

    return fig


def create_cumulative_steps_chart(timeseries_data: pd.DataFrame) -> go.Figure:
    """Create line chart showing cumulative steps during march"""

    if timeseries_data.empty or 'cumulative_steps' not in timeseries_data.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No cumulative steps data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16, color="gray")
        )
        return fig

    fig = go.Figure(data=[
        go.Scatter(
            x=timeseries_data['timestamp_minutes'],
            y=timeseries_data['cumulative_steps'],
            mode='lines+markers',
            name='Cumulative Steps',
            line=dict(color='#2ecc71', width=3),
            marker=dict(size=5),
            fill='tonexty',
            fillcolor='rgba(46,204,113,0.1)',
            hovertemplate='<b>Time:</b> %{x} min<br><b>Steps:</b> %{y:,}<extra></extra>'
        )
    ])

    fig.update_layout(
        title=dict(
            text="Cumulative Steps During March",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Time (minutes)",
        yaxis_title="Cumulative Steps",
        height=300,
        margin=dict(l=50, r=50, t=60, b=50),
        showlegend=False
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')

    return fig


def create_pace_consistency_chart(timeseries_data: pd.DataFrame) -> go.Figure:
    """Create chart showing pace consistency and variation during march"""

    if timeseries_data.empty or 'estimated_speed_kmh' not in timeseries_data.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No pace data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16, color="gray")
        )
        return fig

    speeds = timeseries_data['estimated_speed_kmh']
    avg_speed = speeds.mean()

    # Calculate rolling average (5-point window)
    rolling_avg = speeds.rolling(window=5, center=True).mean()

    fig = go.Figure()

    # Add actual speed
    fig.add_trace(go.Scatter(
        x=timeseries_data['timestamp_minutes'],
        y=speeds,
        mode='lines',
        name='Actual Speed',
        line=dict(color='#3498db', width=1, dash='dot'),
        opacity=0.7,
        hovertemplate='<b>Time:</b> %{x} min<br><b>Speed:</b> %{y:.1f} km/h<extra></extra>'
    ))

    # Add rolling average
    fig.add_trace(go.Scatter(
        x=timeseries_data['timestamp_minutes'],
        y=rolling_avg,
        mode='lines',
        name='5-Point Average',
        line=dict(color='#2ecc71', width=2),
        hovertemplate='<b>Time:</b> %{x} min<br><b>Avg Speed:</b> %{y:.1f} km/h<extra></extra>'
    ))

    # Add overall average line
    fig.add_hline(
        y=avg_speed,
        line_dash="dash",
        line_color="#e74c3c",
        annotation_text=f"March Average: {avg_speed:.1f} km/h",
        annotation_position="top right"
    )

    fig.update_layout(
        title=dict(
            text="Pace Consistency Analysis",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Time (minutes)",
        yaxis_title="Speed (km/h)",
        height=350,
        margin=dict(l=50, r=50, t=60, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')

    return fig


def create_performance_summary_card_data(summary_data: dict[str, Any]) -> dict[str, Any]:
    """Generate performance summary metrics for display cards"""

    if not summary_data:
        return {
            'duration': 'N/A',
            'avg_pace': 'N/A',
            'total_steps': 'N/A',
            'effort_score': 'N/A',
            'completion_status': 'Unknown'
        }

    # Format duration
    duration_min = summary_data.get('march_duration_minutes') or summary_data.get('finish_time_minutes', 0)
    duration_hours = duration_min // 60
    duration_mins = duration_min % 60
    duration_str = f"{duration_hours}h {duration_mins}m" if duration_hours > 0 else f"{duration_mins}m"

    # Format metrics
    avg_pace = summary_data.get('avg_pace_kmh', 0)
    total_steps = summary_data.get('total_steps', 0)
    effort_score = summary_data.get('effort_score', 0)
    completed = summary_data.get('completed', False)

    return {
        'duration': duration_str,
        'avg_pace': f"{avg_pace:.1f} km/h" if avg_pace else 'N/A',
        'total_steps': f"{total_steps:,}" if total_steps else 'N/A',
        'effort_score': f"{effort_score:.1f}" if effort_score else 'N/A',
        'completion_status': 'Completed' if completed else 'Did Not Finish',
        'estimated_distance': f"{summary_data.get('estimated_distance_km', 0):.1f} km",
        'avg_hr': f"{summary_data.get('avg_hr', 0)} bpm" if summary_data.get('avg_hr') else 'N/A',
        'max_hr': f"{summary_data.get('max_hr', 0)} bpm" if summary_data.get('max_hr') else 'N/A'
    }
