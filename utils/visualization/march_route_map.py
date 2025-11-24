"""Map visualization for march GPS routes"""

import pandas as pd
import plotly.graph_objects as go


def create_march_route_map(
    gps_data: pd.DataFrame, participant_name: str = "Participant"
) -> go.Figure:
    """
    Create an interactive map showing the participant's march route

    Args:
        gps_data: DataFrame with columns: latitude, longitude, elevation, speed_kmh, timestamp_minutes
        participant_name: Name of the participant for the title

    Returns:
        Plotly Figure object with the route map
    """
    if gps_data.empty:
        # Return empty map
        fig = go.Figure()
        fig.add_annotation(
            text="No GPS data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    # Create color scale based on speed
    if "speed_kmh" in gps_data.columns and gps_data["speed_kmh"].notna().any():
        colors = gps_data["speed_kmh"]
        colorbar_title = "Speed (km/h)"
    else:
        colors = gps_data["timestamp_minutes"]
        colorbar_title = "Time (min)"

    # Create hover text
    hover_text = []
    for _, row in gps_data.iterrows():
        text_parts = [
            f"Time: {row['timestamp_minutes']:.1f} min",
            f"Lat: {row['latitude']:.5f}°",
            f"Lon: {row['longitude']:.5f}°",
        ]
        if "elevation" in row and pd.notna(row["elevation"]):
            text_parts.append(f"Elevation: {row['elevation']:.1f} m")
        if "speed_kmh" in row and pd.notna(row["speed_kmh"]):
            text_parts.append(f"Speed: {row['speed_kmh']:.2f} km/h")
        hover_text.append("<br>".join(text_parts))

    # Create the map trace
    fig = go.Figure()

    # Add the route line with color gradient
    fig.add_trace(
        go.Scattermapbox(
            lat=gps_data["latitude"],
            lon=gps_data["longitude"],
            mode="lines+markers",
            marker=dict(
                size=6,
                color=colors,
                colorscale="Viridis",
                showscale=False,
                cmin=colors.min() if len(colors) > 0 else 0,
                cmax=colors.max() if len(colors) > 0 else 1,
            ),
            line=dict(width=2, color="rgba(0, 116, 217, 0.7)"),
            hovertext=hover_text,
            hoverinfo="text",
            name="Route",
            showlegend=False,
        )
    )

    # Add start marker
    fig.add_trace(
        go.Scattermapbox(
            lat=[gps_data.iloc[0]["latitude"]],
            lon=[gps_data.iloc[0]["longitude"]],
            mode="markers",
            marker=dict(size=12, color="green", symbol="marker"),
            text="Start",
            hoverinfo="text",
            name="Start",
            showlegend=False,
        )
    )

    # Add finish marker
    fig.add_trace(
        go.Scattermapbox(
            lat=[gps_data.iloc[-1]["latitude"]],
            lon=[gps_data.iloc[-1]["longitude"]],
            mode="markers",
            marker=dict(size=12, color="red", symbol="marker"),
            text="Finish",
            hoverinfo="text",
            name="Finish",
            showlegend=False,
        )
    )

    # Calculate center point
    center_lat = gps_data["latitude"].mean()
    center_lon = gps_data["longitude"].mean()

    # Calculate zoom level based on route extent
    lat_range = gps_data["latitude"].max() - gps_data["latitude"].min()
    lon_range = gps_data["longitude"].max() - gps_data["longitude"].min()
    max_range = max(lat_range, lon_range)

    # Approximate zoom level (adjust as needed)
    if max_range < 0.01:
        zoom = 14
    elif max_range < 0.05:
        zoom = 12
    elif max_range < 0.1:
        zoom = 11
    elif max_range < 0.5:
        zoom = 9
    else:
        zoom = 8

    # Update layout
    fig.update_layout(
        mapbox=dict(
            style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=zoom
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=600,
        showlegend=False,
    )

    return fig


def create_multi_participant_route_map(all_gps_data: pd.DataFrame) -> go.Figure:
    """
    Create an interactive map showing routes for multiple participants

    Args:
        all_gps_data: DataFrame with columns: user_id, username, latitude, longitude,
                     elevation, speed_kmh, timestamp_minutes

    Returns:
        Plotly Figure object with all participant routes
    """
    if all_gps_data.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No GPS data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig

    fig = go.Figure()

    # Color palette for different participants
    colors = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    participants = all_gps_data["user_id"].unique()

    for idx, user_id in enumerate(participants):
        participant_data = all_gps_data[all_gps_data["user_id"] == user_id].sort_values(
            "timestamp_minutes"
        )
        username = participant_data.iloc[0]["username"]
        color = colors[idx % len(colors)]

        # Create hover text
        hover_text = []
        for _, row in participant_data.iterrows():
            text_parts = [
                f"Participant: {username}",
                f"Time: {row['timestamp_minutes']:.1f} min",
                f"Lat: {row['latitude']:.5f}°",
                f"Lon: {row['longitude']:.5f}°",
            ]
            if "speed_kmh" in row and pd.notna(row["speed_kmh"]):
                text_parts.append(f"Speed: {row['speed_kmh']:.2f} km/h")
            hover_text.append("<br>".join(text_parts))

        # Add route trace
        fig.add_trace(
            go.Scattermapbox(
                lat=participant_data["latitude"],
                lon=participant_data["longitude"],
                mode="lines",
                line=dict(width=2, color=color),
                hovertext=hover_text,
                hoverinfo="text",
                name=username,
            )
        )

        # Add start marker
        fig.add_trace(
            go.Scattermapbox(
                lat=[participant_data.iloc[0]["latitude"]],
                lon=[participant_data.iloc[0]["longitude"]],
                mode="markers",
                marker=dict(size=8, color=color, symbol="circle"),
                hovertext=f"{username} - Start",
                hoverinfo="text",
                showlegend=False,
            )
        )

    # Calculate center and zoom
    center_lat = all_gps_data["latitude"].mean()
    center_lon = all_gps_data["longitude"].mean()

    lat_range = all_gps_data["latitude"].max() - all_gps_data["latitude"].min()
    lon_range = all_gps_data["longitude"].max() - all_gps_data["longitude"].min()
    max_range = max(lat_range, lon_range)

    if max_range < 0.01:
        zoom = 14
    elif max_range < 0.05:
        zoom = 12
    elif max_range < 0.1:
        zoom = 11
    elif max_range < 0.5:
        zoom = 9
    else:
        zoom = 8

    # Update layout
    fig.update_layout(
        title=dict(text="March Routes - All Participants", x=0.5, xanchor="center"),
        mapbox=dict(
            style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=zoom
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=600,
        showlegend=True,
        legend=dict(
            x=0.01, y=0.99, bgcolor="rgba(255, 255, 255, 0.8)", bordercolor="gray", borderwidth=1
        ),
    )

    return fig


def create_elevation_profile(
    gps_data: pd.DataFrame, participant_name: str = "Participant"
) -> tuple[go.Figure, dict]:
    """
    Create elevation profile chart from GPS data

    Args:
        gps_data: DataFrame with columns: timestamp_minutes, elevation, cumulative_distance_km
        participant_name: Name of the participant

    Returns:
        Tuple of (Plotly Figure object, dict with elevation statistics)
    """
    empty_stats = {
        "max_elevation": None,
        "min_elevation": None,
        "total_ascent": None,
        "total_descent": None,
    }

    if gps_data.empty or "elevation" not in gps_data.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No elevation data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig, empty_stats

    # Filter out null elevations
    elevation_data = gps_data[gps_data["elevation"].notna()].copy()

    if elevation_data.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No elevation data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
        )
        return fig, empty_stats

    # Use distance if available, otherwise use time
    if (
        "cumulative_distance_km" in elevation_data.columns
        and elevation_data["cumulative_distance_km"].notna().any()
    ):
        x_data = elevation_data["cumulative_distance_km"]
        x_label = "Distance (km)"
    else:
        x_data = elevation_data["timestamp_minutes"] / 60  # Convert to hours
        x_label = "Time (hours)"

    fig = go.Figure()

    # Add elevation profile with area fill
    fig.add_trace(
        go.Scatter(
            x=x_data,
            y=elevation_data["elevation"],
            mode="lines",
            fill="tozeroy",
            line=dict(color="rgb(34, 139, 34)", width=2),
            fillcolor="rgba(34, 139, 34, 0.3)",
            name="Elevation",
            hovertemplate="<b>Time: %{x:.2f} h</b><br>Elevation: %{y:.1f} m<extra></extra>",
        )
    )

    # Calculate elevation statistics
    elevation_diff = elevation_data["elevation"].diff()
    total_ascent = elevation_diff[elevation_diff > 0].sum()
    total_descent = abs(elevation_diff[elevation_diff < 0].sum())
    min_elev = elevation_data["elevation"].min()
    max_elev = elevation_data["elevation"].max()

    # Prepare statistics dict
    stats = {
        "max_elevation": max_elev,
        "min_elevation": min_elev,
        "total_ascent": total_ascent,
        "total_descent": total_descent,
    }

    # Update layout with mobile-friendly margins
    fig.update_layout(
        xaxis=dict(title=x_label, showgrid=True, gridcolor="lightgray"),
        yaxis=dict(title="Elevation (m)", showgrid=True, gridcolor="lightgray", automargin=True),
        hovermode="x unified",
        height=300,
        margin=dict(l=20, r=20, t=20, b=40),
        plot_bgcolor="white",
        autosize=True,
    )

    return fig, stats
