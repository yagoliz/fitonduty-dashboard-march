#!/usr/bin/env python3
"""
FitonDuty March Dashboard - Main Application
Post-event analysis dashboard for long march physiological monitoring
"""

import logging
import os
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html
from flask import Flask
from flask_login import LoginManager, UserMixin, current_user

# Import components
# Import callbacks
from callbacks.navigation_callbacks import register_navigation_callbacks
from components.auth import create_login_form, create_user_info_dropdown

# Show participant detail view
from components.march.participant_detail import (
    create_back_to_overview_button,
    create_participant_detail_view,
)
from components.march.role_based_overview import create_role_based_march_overview

# Import configuration
from config.settings import config

# Check permissions
from utils.auth import user_can_view_participant

# Import database utilities
from utils.database import get_user_by_id, init_database_manager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask server
server = Flask(__name__)

# Load configuration
config_name = os.environ.get('FLASK_ENV', 'development')
app_config = config.get(config_name, config['default'])

server.config.from_object(app_config)

# Initialize database connection
init_database_manager(app_config.DATABASE_URL)

# Initialize Dash app
app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=[
        # Use a modern Bootswatch theme for improved defaults
        dbc.themes.LUX,
        "https://use.fontawesome.com/releases/v5.15.4/css/all.css"
    ],
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    title=app_config.DASHBOARD_TITLE,
)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'


# User class for authentication
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.username = user_data.get('username')
        self.role = user_data.get('role', 'participant')
        self.is_active_user = user_data.get('is_active', True)
        self.last_login = user_data.get('last_login')

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_supervisor(self):
        return self.role == 'supervisor'

    @property
    def is_participant(self):
        return self.role == 'participant'

    @property
    def display_name(self):
        return self.username


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID from database"""
    try:
        user_data = get_user_by_id(int(user_id))
        if user_data:
            return User(user_data)
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {e}")
    return None

# Register navigation callbacks
register_navigation_callbacks(app)

# Main app layout with routing
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='navigation-state', data=None),
    html.Div(id="page-content")
])


# Main routing callback
@callback(
    Output("page-content", "children"),
    [Input("url", "pathname")]
)
def display_page(pathname):
    """Main routing logic with authentication"""

    if pathname == "/login" or not current_user.is_authenticated:
        return create_login_form()

    # Authenticated routes
    if pathname == "/" or pathname is None:
        return create_authenticated_layout()
    elif pathname.startswith("/march/"):
        try:
            path_parts = pathname.split("/")
            # Handle /march/<id>/participant/<user_id>
            if len(path_parts) >= 5 and path_parts[3] == "participant":
                march_id = int(path_parts[2])
                user_id = int(path_parts[4])
                return create_authenticated_layout(march_id, participant_id=user_id)
            # Handle /march/<id>
            else:
                march_id = int(path_parts[2])
                return create_authenticated_layout(march_id)
        except (ValueError, IndexError):
            return create_authenticated_layout()
    else:
        return create_authenticated_layout()


def create_authenticated_layout(march_id=None, participant_id=None):
    """Create main layout for authenticated users"""

    if not current_user.is_authenticated:
        return create_login_form()

    # Custom navigation bar with better alignment
    navbar = html.Nav([
        html.Div([
            html.A([
                html.I(className="fas fa-chart-line me-2"),
                "FitonDuty March Dashboard"
            ],
                href="/",
                className="navbar-brand"
            ),
            html.Div([
                create_user_info_dropdown(current_user)
            ], className="navbar-nav")
        ], className="navbar-content")
    ], className="navbar navbar-expand navbar-dark navbar-simple")

    # Main content based on route
    if participant_id and march_id:
        if not user_can_view_participant(current_user.id, participant_id, current_user.role):
            from components.auth import create_access_denied
            main_content_body = create_access_denied("You don't have permission to view this participant's details.")
        else:
            back_button = create_back_to_overview_button(march_id)
            detail_view = create_participant_detail_view(march_id, participant_id)
            main_content_body = html.Div([back_button, detail_view])

        main_content = html.Div(main_content_body, id="main-content")
    else:
        # Show regular march overview - use main-content id for navigation callbacks
        main_content = html.Div(
            create_role_based_march_overview(march_id),
            id="main-content"
        )

    # Footer
    footer = dbc.Row([
        dbc.Col([
            html.Hr(),
            html.P([
                f"Logged in as: {current_user.role.title()} - {current_user.display_name} | ",
                f"Environment: {getattr(app_config, 'ENV', 'development').title()}"
            ], className="text-center text-muted small")
        ])
    ])

    return html.Div([
        navbar,
        dbc.Container([
            main_content,
            footer
        ], className="main-content-wrapper mt-4")
    ])


# Navigation callbacks
@callback(
    Output('url', 'pathname', allow_duplicate=True),
    [Input({'type': 'view-march-btn', 'march_id': dash.dependencies.ALL}, 'n_clicks')],
    prevent_initial_call=True
)
def navigate_to_march(n_clicks_list):
    """Navigate to specific march view"""
    if not any(n_clicks_list):
        return dash.no_update

    ctx = dash.callback_context
    if ctx.triggered:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        march_data = eval(button_id)  # Safe here as we control the button IDs
        march_id = march_data['march_id']
        return f"/march/{march_id}"

    return dash.no_update


@callback(
    Output('url', 'pathname', allow_duplicate=True),
    [Input('back-to-all-marches-btn', 'n_clicks')],
    prevent_initial_call=True
)
def navigate_back_to_all_marches(n_clicks):
    """Navigate back to all marches view"""
    if n_clicks:
        return "/"
    return dash.no_update

# Simple route for testing
@server.route('/health')
def health_check():
    """Health check endpoint"""
    return {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'app': 'fitonduty-march-dashboard'
    }


if __name__ == '__main__':
    print("🚀 Starting FitonDuty March Dashboard...")
    print(f"Environment: {config_name}")
    print(f"Debug mode: {app_config.DEBUG}")
    print(f"Host: {app_config.HOST}")
    print(f"Port: {app_config.PORT}")
    print(f"Database: {app_config.DATABASE_URL.split('@')[-1] if '@' in app_config.DATABASE_URL else 'Not configured'}")

    # Run the app
    app.run(
        debug=app_config.DEBUG,
        host=app_config.HOST,
        port=app_config.PORT
    )
