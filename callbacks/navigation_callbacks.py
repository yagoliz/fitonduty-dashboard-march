"""Navigation callbacks for switching between march views"""

import dash
from dash import Input, Output, State, callback_context, no_update
from dash.exceptions import PreventUpdate

from components.march.march_overview import create_march_overview
from components.march.participant_detail import (
    create_back_to_overview_button,
    create_participant_detail_view,
)


def register_navigation_callbacks(app):
    """Register all navigation callbacks"""

    # Store current navigation state for better back navigation
    @app.callback(
        Output('navigation-state', 'data'),
        [
            Input({'type': 'view-march-btn', 'march_id': dash.dependencies.ALL}, 'n_clicks'),
            Input({'type': 'view-participant-btn', 'user_id': dash.dependencies.ALL, 'march_id': dash.dependencies.ALL}, 'n_clicks')
        ],
        [
            State({'type': 'view-march-btn', 'march_id': dash.dependencies.ALL}, 'id'),
            State({'type': 'view-participant-btn', 'user_id': dash.dependencies.ALL, 'march_id': dash.dependencies.ALL}, 'id'),
            State('navigation-state', 'data')
        ]
    )
    def update_navigation_state(march_clicks, participant_clicks, march_ids, participant_ids, current_state):
        """Update navigation state for better back button functionality"""

        if not callback_context.triggered:
            raise PreventUpdate

        trigger = callback_context.triggered[0]
        trigger_id = trigger['prop_id']

        # Initialize state if None
        if current_state is None:
            current_state = {'view_stack': []}

        # Handle march selection
        if 'view-march-btn' in trigger_id and any(march_clicks):
            for i, clicks in enumerate(march_clicks):
                if clicks:
                    march_id = march_ids[i]['march_id']
                    current_state['current_march'] = march_id
                    current_state['current_view'] = 'march_overview'
                    return current_state

        # Handle participant detail view
        if 'view-participant-btn' in trigger_id and any(participant_clicks):
            for i, clicks in enumerate(participant_clicks):
                if clicks:
                    user_id = participant_ids[i]['user_id']
                    march_id = participant_ids[i]['march_id']
                    current_state['current_march'] = march_id
                    current_state['current_participant'] = user_id
                    current_state['current_view'] = 'participant_detail'
                    return current_state

        raise PreventUpdate


    @app.callback(
        Output('url', 'pathname', allow_duplicate=True),
        [Input({'type': 'view-participant-btn', 'user_id': dash.dependencies.ALL, 'march_id': dash.dependencies.ALL}, 'n_clicks')],
        prevent_initial_call=True
    )
    def navigate_to_participant_detail(n_clicks_list):
        """Navigate to participant detail view"""
        if not any(n_clicks_list or []):
            return no_update

        ctx = callback_context
        if ctx.triggered:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            try:
                # Parse the button ID to extract march_id and user_id
                import json
                button_data = json.loads(button_id.replace("'", '"'))
                march_id = button_data['march_id']
                user_id = button_data['user_id']
                return f'/march/{march_id}/participant/{user_id}'
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing button ID: {e}")
                return no_update

        return no_update


    @app.callback(
        Output('url', 'pathname', allow_duplicate=True),
        [Input({'type': 'back-to-march-btn', 'march_id': dash.dependencies.ALL}, 'n_clicks')],
        prevent_initial_call=True
    )
    def navigate_back_to_march_overview(n_clicks_list):
        """Navigate back to march overview from participant detail"""
        if not any(n_clicks_list or []):
            return no_update

        ctx = callback_context
        if ctx.triggered:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            try:
                # Parse the button ID to extract march_id
                import json
                button_data = json.loads(button_id.replace("'", '"'))
                march_id = button_data['march_id']
                return f'/march/{march_id}'
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing button ID: {e}")
                return no_update

        return no_update
