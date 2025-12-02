"""Authentication Components for March Dashboard"""


import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, html
from flask_login import login_user, logout_user

from src.app.utils.auth import authenticate_user


def create_login_form(debug: bool = False):
    """Create login form component"""

    debug_info = dbc.Alert(
        [
            html.H6(
                [html.I(className="fas fa-info-circle me-2"), "Development Dashboard"],
                className="alert-heading",
            ),
            html.P(
                [
                    "You shouldn't see this in production!",
                ],
                className="mb-0",
            ),
        ],
        color="info",
        className="small",
    )

    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4([
                            html.I(className="fas fa-shield-alt me-3"),
                            "Dashboard Login"
                        ], className="text-center mb-0 text-white")
                    ], className="bg-gradient-primary text-white py-3"),
                    dbc.CardBody([
                        html.Div(id="login-error-message"),

                        dbc.Form([
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-user")),
                                dbc.Input(
                                    id="login-username",
                                    placeholder="Username",
                                    type="text",
                                    required=True,
                                    autoFocus=True
                                )
                            ], className="mb-3"),

                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-key")),
                                dbc.Input(
                                    id="login-password",
                                    placeholder="Password",
                                    type="password",
                                    required=True
                                )
                            ], className="mb-3"),

                            dbc.Button(
                                [html.I(className="fas fa-sign-in-alt me-2"), "Login"],
                                id="login-submit-btn",
                                color="primary",
                                size="lg",
                                className="w-100 btn-professional",
                                type="submit"
                            ),
                        ], id="login-form"),

                        html.Hr(),

                        debug_info if debug else html.Div()
                    ], className="py-3")
                ], className="card-professional shadow-professional", style={"maxWidth": "450px", "maxHeight": "fit-content"})
            ], width=12, className="d-flex justify-content-center")
        ], justify="center", className="min-vh-100 py-5")
    ])


def create_user_info_dropdown(user):
    """Create user info dropdown for navigation"""
    if not user or not hasattr(user, 'username'):
        return html.Div()

    # Role badge with professional icons
    role_config = {
        'admin': {'icon': 'fas fa-crown', 'label': 'Admin', 'color': 'danger'},
        'supervisor': {'icon': 'fas fa-user-shield', 'label': 'Supervisor', 'color': 'warning'},
        'participant': {'icon': 'fas fa-user', 'label': 'Participant', 'color': 'info'}
    }

    role_info = role_config.get(user.role, {'icon': 'fas fa-user', 'label': 'User', 'color': 'secondary'})

    return dbc.DropdownMenu(
        children=[
            dbc.DropdownMenuItem([
                dbc.Badge([
                    html.I(className=f"{role_info['icon']} me-1"),
                    role_info['label']
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
        label=[
            html.I(className=f"{role_info['icon']} me-2"),
            user.display_name
        ],
        align_end=True,
        color="outline-light"
    )


def create_access_denied(message: str = None):
    """Create access denied component"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Alert([
                    html.H4([
                        html.I(className="fas fa-ban me-2"),
                        "Access Denied"
                    ], className="alert-heading"),
                    html.P(message or "You don't have permission to view this content."),
                    html.Hr(),
                    html.P([
                        "Please log in with appropriate credentials or contact your administrator.",
                    ], className="mb-3"),
                    dbc.Button([
                        html.I(className="fas fa-sign-in-alt me-2"),
                        "Go to Login"
                    ], href="/login", color="primary", className="btn-professional")
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
                    html.P([
                        html.I(className="fas fa-clock me-2"),
                        "Loading..."
                    ], className="mt-3 text-muted")
                ], className="text-center loading-container")
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
        error_alert = dbc.Alert([
            html.I(className="fas fa-exclamation-triangle me-2"),
            "Please enter both username and password"
        ], color="danger", className="mb-3")
        return error_alert, dash.no_update

    user_data = authenticate_user(username, password)

    if user_data:
        # Import User class from main
        from src.app.main import User
        user = User(user_data)
        login_user(user, remember=False)
        return "", "/"  # Redirect to main page
    else:
        error_alert = dbc.Alert([
            html.Strong([
                html.I(className="fas fa-times-circle me-2"),
                "Login Failed"
            ]), html.Br(),
            "Invalid username or password. Please check your credentials and try again."
        ], color="danger", className="mb-3")
        return error_alert, dash.no_update


@callback(
    Output('url', 'pathname', allow_duplicate=True),
    [Input('logout-btn', 'n_clicks')],
    prevent_initial_call=True
)
def handle_logout(n_clicks):
    """Handle logout and clear session"""
    if n_clicks:
        from flask import session
        # Logout the user (removes user from Flask-Login)
        logout_user()
        # Clear the entire Flask session (removes server-side session data)
        session.clear()
        return "/login"
    return dash.no_update
