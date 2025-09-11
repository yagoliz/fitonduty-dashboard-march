"""Authentication Components for March Dashboard"""


import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, html
from flask_login import login_user, logout_user

from utils.auth import authenticate_user


def create_login_form():
    """Create login form component"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4("🔒 Login to FitonDuty March Dashboard", className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        html.Div(id="login-error-message"),

                        dbc.Form([
                            dbc.InputGroup([
                                dbc.InputGroupText("👤"),
                                dbc.Input(
                                    id="login-username",
                                    placeholder="Username",
                                    type="text",
                                    required=True,
                                    autoFocus=True
                                )
                            ], className="mb-3"),

                            dbc.InputGroup([
                                dbc.InputGroupText("🔑"),
                                dbc.Input(
                                    id="login-password",
                                    placeholder="Password",
                                    type="password",
                                    required=True
                                )
                            ], className="mb-3"),

                            dbc.Button(
                                "Login",
                                id="login-submit-btn",
                                color="primary",
                                size="lg",
                                className="w-100",
                                type="submit"
                            ),
                        ], id="login-form"),

                        html.Hr(),

                        dbc.Alert([
                            html.H6("Test Credentials", className="alert-heading"),
                            html.P([
                                html.Strong("Admin: "), "admin / test123", html.Br(),
                                html.Strong("Participants: "), "participant1-4 / test123"
                            ], className="mb-0")
                        ], color="info", className="small")
                    ])
                ], style={"maxWidth": "450px"})
            ], width=12, lg=8, xl=6)
        ], justify="center", className="min-vh-100 py-5")
    ])


def create_user_info_dropdown(user):
    """Create user info dropdown for navigation"""
    if not user or not hasattr(user, 'username'):
        return html.Div()

    # Role badge with emoji
    role_config = {
        'admin': {'emoji': '👑', 'label': 'Admin', 'color': 'danger'},
        'supervisor': {'emoji': '👮', 'label': 'Supervisor', 'color': 'warning'},
        'participant': {'emoji': '👤', 'label': 'Participant', 'color': 'info'}
    }

    role_info = role_config.get(user.role, {'emoji': '👤', 'label': 'User', 'color': 'secondary'})

    return dbc.DropdownMenu(
        children=[
            dbc.DropdownMenuItem([
                dbc.Badge([
                    role_info['emoji'], " ", role_info['label']
                ], color=role_info['color'], className="me-2"),
                user.display_name
            ], header=True),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem([
                html.I(className="fas fa-sign-out-alt me-2"),
                "Logout"
            ], id="logout-btn", className="text-danger")
        ],
        nav=True,
        in_navbar=True,
        label=f"{role_info['emoji']} {user.display_name}",
        align_end=True,
        color="outline-light"
    )


def create_access_denied(message: str = None):
    """Create access denied component"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Alert([
                    html.H4("🚫 Access Denied", className="alert-heading"),
                    html.P(message or "You don't have permission to view this content."),
                    html.Hr(),
                    html.P([
                        "Please log in with appropriate credentials or contact your administrator.",
                    ], className="mb-3"),
                    dbc.Button([
                        html.I(className="fas fa-sign-in-alt me-2"),
                        "Go to Login"
                    ], href="/login", color="primary")
                ], color="danger")
            ], md=8, lg=6)
        ], justify="center", className="mt-5")
    ])


def create_loading_spinner():
    """Create loading spinner component"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    dbc.Spinner(color="primary", size="lg"),
                    html.P("Loading...", className="mt-3 text-muted")
                ], className="text-center")
            ])
        ], justify="center", className="mt-5")
    ])


# Authentication callbacks
@callback(
    [Output('login-error-message', 'children'),
     Output('url', 'pathname', allow_duplicate=True)],
    [Input('login-submit-btn', 'n_clicks'),
     Input('login-form', 'n_submit')],
    [State('login-username', 'value'),
     State('login-password', 'value')],
    prevent_initial_call=True
)
def handle_login(n_clicks, n_submit, username, password):
    """Handle login form submission"""
    # Check if login was triggered (either by button click or form submit)
    if not (n_clicks or n_submit) or not username or not password:
        return dash.no_update, dash.no_update

    # Strip whitespace
    username = username.strip()

    if not username or not password:
        error_alert = dbc.Alert(
            "❌ Please enter both username and password",
            color="danger",
            className="mb-3"
        )
        return error_alert, dash.no_update

    user_data = authenticate_user(username, password)

    if user_data:
        # Import User class from app
        from app import User
        user = User(user_data)
        login_user(user, remember=True)
        return "", "/"  # Redirect to main page
    else:
        error_alert = dbc.Alert([
            html.Strong("❌ Login Failed"), html.Br(),
            "Invalid username or password. Please check your credentials and try again."
        ], color="danger", className="mb-3")
        return error_alert, dash.no_update


@callback(
    Output('url', 'pathname', allow_duplicate=True),
    [Input('logout-btn', 'n_clicks')],
    prevent_initial_call=True
)
def handle_logout(n_clicks):
    """Handle logout"""
    if n_clicks:
        logout_user()
        return "/login"
    return dash.no_update
