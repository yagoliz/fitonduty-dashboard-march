#!/usr/bin/env python3
"""
FitonDuty March Dashboard - Main Application
Post-event analysis dashboard for long march physiological monitoring
"""

import os
import dash
from dash import html
import dash_bootstrap_components as dbc
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask import Flask
from datetime import datetime

# Import configuration
from config.settings import config

# Initialize Flask server
server = Flask(__name__)

# Load configuration
config_name = os.environ.get('FLASK_ENV', 'development')
app_config = config.get(config_name, config['default'])

server.config.from_object(app_config)

# Initialize Dash app
app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    title=app_config.DASHBOARD_TITLE,
)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'


# Simple User class for authentication
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.username = user_data.get('username')
        self.role = user_data.get('role', 'participant')
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_participant(self):
        return self.role == 'participant'
    
    @property
    def display_name(self):
        return self.username


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID - simplified for now"""
    # TODO: Replace with actual database lookup
    # For now, return a dummy user for development
    return User({
        'id': int(user_id),
        'username': f'user_{user_id}',
        'role': 'participant'
    })


# Import components
from components.march.march_overview import create_march_overview

# Basic layout for now
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            dbc.NavbarSimple(
                brand="FitonDuty March Dashboard",
                brand_href="/",
                color="primary",
                dark=True,
                className="mb-4"
            )
        ])
    ]),
    
    # Main content area
    html.Div(id="main-content", children=[
        create_march_overview()
    ]),
    
    dbc.Row([
        dbc.Col([
            dash.html.Hr(),
            dash.html.P([
                "Development Mode - Database seeded with sample march data"
            ], className="text-center text-muted small")
        ])
    ])
    
], fluid=True)


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
    
    # Run the app
    app.run(
        debug=app_config.DEBUG,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8050))
    )