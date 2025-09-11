#!/usr/bin/env python3
"""
FitonDuty March Dashboard - Main Application
Post-event analysis dashboard for long march physiological monitoring
"""

import os
import dash
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
from flask_login import LoginManager, UserMixin, current_user
from flask import Flask
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import configuration
from config.settings import config

# Import database utilities
from utils.database import init_database_manager

# Import auth utilities
from utils.auth import get_user_by_id

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
        dbc.themes.BOOTSTRAP,
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


# Import components
from components.auth import create_login_form, create_user_info_dropdown, create_loading_spinner
from components.march.role_based_overview import create_role_based_march_overview

# Import callbacks
from callbacks.navigation_callbacks import register_navigation_callbacks

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
            march_id = int(pathname.split("/")[-1])
            return create_authenticated_layout(march_id)
        except (ValueError, IndexError):
            return create_authenticated_layout()
    else:
        return create_authenticated_layout()


def create_authenticated_layout(march_id=None):
    """Create main layout for authenticated users"""
    
    if not current_user.is_authenticated:
        return create_login_form()
    
    # Navigation bar with user info
    navbar = dbc.NavbarSimple(
        children=[
            create_user_info_dropdown(current_user)
        ],
        brand="FitonDuty March Dashboard",
        brand_href="/",
        color="primary",
        dark=True,
        className="mb-4"
    )
    
    # Main content based on route - use main-content id for navigation callbacks
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
                "Environment: Development"
            ], className="text-center text-muted small")
        ])
    ])
    
    return dbc.Container([
        navbar,
        main_content,
        footer
    ], fluid=True)


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