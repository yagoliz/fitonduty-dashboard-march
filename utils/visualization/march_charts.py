"""March-specific visualization components using Plotly"""

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_hr_speed_timeline(
    timeseries_data: pd.DataFrame, participant_name: str = "Participant"
) -> go.Figure:
    """Create dual-axis timeline showing HR and speed progression during march"""

    if timeseries_data.empty:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(
            text="No time-series data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    # Create subplot with secondary y-axis
    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    # Convert minutes to hours
    time_hours = timeseries_data["timestamp_minutes"] / 60

    # Heart Rate trace - using primary color
    fig.add_trace(
        go.Scatter(
            x=time_hours,
            y=timeseries_data["heart_rate"],
            mode="lines+markers",
            name="Heart Rate",
            line=dict(color="#2c3e50", width=3),
            marker=dict(size=5, color="#2c3e50"),
            hovertemplate="<b>Time:</b> %{x:.2f} h<br><b>HR:</b> %{y} bpm<extra></extra>",
        ),
        secondary_y=False,
    )

    # Speed trace - using secondary color
    fig.add_trace(
        go.Scatter(
            x=time_hours,
            y=timeseries_data["estimated_speed_kmh"],
            mode="lines+markers",
            name="Speed",
            line=dict(color="#3498db", width=3),
            marker=dict(size=5, color="#3498db"),
            hovertemplate="<b>Time:</b> %{x:.2f} h<br><b>Speed:</b> %{y:.1f} km/h<extra></extra>",
        ),
        secondary_y=True,
    )

    # Update x-axis
    fig.update_xaxes(
        title_text="Time (hours)", showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)"
    )

    # Update y-axes
    fig.update_yaxes(
        title_text="Heart Rate (bpm)",
        secondary_y=False,
        showgrid=True,
        gridwidth=1,
        gridcolor="rgba(231,76,60,0.1)",
        automargin=True,
    )

    fig.update_yaxes(title_text="Speed (km/h)", secondary_y=True, showgrid=False, automargin=True)

    # Update layout with professional styling
    fig.update_layout(
        height=350,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=30, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, sans-serif", size=12, color="#212529"),
    )

    # Enable responsive sizing
    fig.update_layout(autosize=True)

    return fig


def create_hr_zones_chart(hr_zones_data: dict[str, float]) -> go.Figure:
    """Create doughnut chart showing heart rate zone distribution"""

    if not hr_zones_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No HR zones data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    zone_labels = ["Very Light", "Light", "Moderate", "Intense", "Beast Mode"]
    # Professional color palette for HR zones
    zone_colors = ["#95a5a6", "#f39c12", "#e67e22", "#e74c3c", "#2c3e50"]

    values = [
        hr_zones_data.get("very_light_percent", 0),
        hr_zones_data.get("light_percent", 0),
        hr_zones_data.get("moderate_percent", 0),
        hr_zones_data.get("intense_percent", 0),
        hr_zones_data.get("beast_mode_percent", 0),
    ]

    # Filter out zero values for cleaner chart
    filtered_data = [
        (label, value, color)
        for label, value, color in zip(zone_labels, values, zone_colors, strict=False)
        if value > 0
    ]

    if not filtered_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No HR zone data",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    labels, values, colors = zip(*filtered_data, strict=False)

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker=dict(colors=colors),
                textinfo="label+percent",
                textposition="outside",
                hovertemplate="<b>%{label}</b><br>%{percent}<br>%{value:.1f}%<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        height=350,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, sans-serif", size=12, color="#212529"),
    )

    return fig


def create_movement_speeds_chart(movement_data: dict[str, int]) -> go.Figure:
    """Create horizontal bar chart showing time spent in different movement speeds"""

    if not movement_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No movement data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    categories = ["Walking", "Walking Fast", "Jogging", "Running", "Stationary"]
    values = [
        movement_data.get("walking_minutes", 0),
        movement_data.get("walking_fast_minutes", 0),
        movement_data.get("jogging_minutes", 0),
        movement_data.get("running_minutes", 0),
        movement_data.get("stationary_minutes", 0),
    ]
    # Professional color palette for movement categories
    colors = ["#3498db", "#27ae60", "#f39c12", "#2c3e50", "#95a5a6"]

    # Filter out zero values
    filtered_data = [
        (cat, val, color)
        for cat, val, color in zip(categories, values, colors, strict=False)
        if val > 0
    ]

    if not filtered_data:
        fig = go.Figure()
        fig.add_annotation(
            text="No movement data",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    categories, values, colors = zip(*filtered_data, strict=False)

    fig = go.Figure(
        data=[
            go.Bar(
                y=categories,
                x=values,
                orientation="h",
                marker=dict(color=colors),
                hovertemplate="<b>%{y}</b><br>%{x} minutes<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        xaxis_title="Minutes",
        height=350,
        margin=dict(l=20, r=20, t=20, b=40),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, sans-serif", size=12, color="#212529"),
        autosize=True,
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(showgrid=False, automargin=True)

    return fig


def create_cumulative_steps_chart(timeseries_data: pd.DataFrame) -> go.Figure:
    """Create line chart showing cumulative steps during march"""

    if timeseries_data.empty or "cumulative_steps" not in timeseries_data.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No cumulative steps data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    # Convert minutes to hours
    time_hours = timeseries_data["timestamp_minutes"] / 60

    fig = go.Figure(
        data=[
            go.Scatter(
                x=time_hours,
                y=timeseries_data["cumulative_steps"],
                mode="lines+markers",
                name="Cumulative Steps",
                line=dict(color="#27ae60", width=3),
                marker=dict(size=5, color="#27ae60"),
                fill="tonexty",
                fillcolor="rgba(39,174,96,0.1)",
                hovertemplate="<b>Time:</b> %{x:.2f} h<br><b>Steps:</b> %{y:,}<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        xaxis_title="Time (hours)",
        yaxis_title="Cumulative Steps",
        height=350,
        margin=dict(l=20, r=20, t=20, b=40),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, sans-serif", size=12, color="#212529"),
        autosize=True,
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)", automargin=True)

    return fig


def create_pace_consistency_chart(timeseries_data: pd.DataFrame) -> go.Figure:
    """Create chart showing pace consistency and variation during march"""

    if timeseries_data.empty or "estimated_speed_kmh" not in timeseries_data.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No pace data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    speeds = timeseries_data["estimated_speed_kmh"]
    avg_speed = speeds.mean()

    # Convert minutes to hours
    time_hours = timeseries_data["timestamp_minutes"] / 60

    # Calculate rolling average (5-point window)
    rolling_avg = speeds.rolling(window=5, center=True).mean()

    fig = go.Figure()

    # Add actual speed - lighter color
    fig.add_trace(
        go.Scatter(
            x=time_hours,
            y=speeds,
            mode="lines",
            name="Actual Speed",
            line=dict(color="#95a5a6", width=2, dash="dot"),
            opacity=0.8,
            hovertemplate="<b>Time:</b> %{x:.2f} h<br><b>Speed:</b> %{y:.1f} km/h<extra></extra>",
        )
    )

    # Add rolling average - primary color
    fig.add_trace(
        go.Scatter(
            x=time_hours,
            y=rolling_avg,
            mode="lines",
            name="5-Point Average",
            line=dict(color="#2c3e50", width=3),
            hovertemplate="<b>Time:</b> %{x:.2f} h<br><b>Avg Speed:</b> %{y:.1f} km/h<extra></extra>",
        )
    )

    # Add overall average line - accent color
    fig.add_hline(
        y=avg_speed,
        line_dash="dash",
        line_color="#f39c12",
        annotation_text=f"March Average: {avg_speed:.1f} km/h",
        annotation_position="top right",
    )

    fig.update_layout(
        xaxis_title="Time (hours)",
        yaxis_title="Speed (km/h)",
        height=350,
        margin=dict(l=20, r=20, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, sans-serif", size=12, color="#212529"),
        autosize=True,
    )

    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(128,128,128,0.2)", automargin=True)

    return fig


def create_performance_summary_card_data(summary_data: dict[str, Any]) -> dict[str, Any]:
    """Generate performance summary metrics for display cards"""

    if not summary_data:
        return {
            "duration": "N/A",
            "avg_pace": "N/A",
            "total_steps": "N/A",
            "effort_score": "N/A",
            "completion_status": "Unknown",
        }

    # Format duration
    duration_min = summary_data.get("march_duration_minutes") or summary_data.get(
        "finish_time_minutes", 0
    )
    duration_hours = duration_min // 60
    duration_mins = duration_min % 60
    duration_str = (
        f"{duration_hours}h {duration_mins}m" if duration_hours > 0 else f"{duration_mins}m"
    )

    # Format metrics
    avg_pace = summary_data.get("avg_pace_kmh", 0)
    total_steps = summary_data.get("total_steps", 0)
    effort_score = summary_data.get("effort_score", 0)
    completed = summary_data.get("completed", False)

    return {
        "duration": duration_str,
        "avg_pace": f"{avg_pace:.1f} km/h" if avg_pace else "N/A",
        "total_steps": f"{total_steps:,}" if total_steps else "N/A",
        "effort_score": f"{effort_score:.1f}" if effort_score else "N/A",
        "completion_status": "Completed" if completed else "Did Not Finish",
        "estimated_distance": f"{summary_data.get('estimated_distance_km', 0):.1f} km",
        "avg_hr": f"{summary_data.get('avg_hr', 0)} bpm" if summary_data.get("avg_hr") else "N/A",
        "max_hr": f"{summary_data.get('max_hr', 0)} bpm" if summary_data.get("max_hr") else "N/A",
    }
