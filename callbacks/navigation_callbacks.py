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

    @app.callback(
        Output('main-content', 'children'),
        [
            Input({'type': 'view-march-btn', 'march_id': dash.dependencies.ALL}, 'n_clicks'),
            Input({'type': 'view-participant-btn', 'user_id': dash.dependencies.ALL, 'march_id': dash.dependencies.ALL}, 'n_clicks'),
            Input({'type': 'back-to-march-btn', 'march_id': dash.dependencies.ALL}, 'n_clicks'),
        ],
        [
            State({'type': 'view-march-btn', 'march_id': dash.dependencies.ALL}, 'id'),
            State({'type': 'view-participant-btn', 'user_id': dash.dependencies.ALL, 'march_id': dash.dependencies.ALL}, 'id'),
            State({'type': 'back-to-march-btn', 'march_id': dash.dependencies.ALL}, 'id'),
        ],
        prevent_initial_call=True
    )
    def handle_navigation(march_clicks, participant_clicks, back_to_march_clicks, march_ids, participant_ids, back_to_march_ids):
        """Handle navigation between march overview and participant detail views"""

        if not callback_context.triggered:
            raise PreventUpdate

        trigger = callback_context.triggered[0]
        trigger_id = trigger['prop_id']

        # Handle march selection
        if 'view-march-btn' in trigger_id and any(march_clicks or []):
            # Find which march button was clicked
            for i, clicks in enumerate(march_clicks or []):
                if clicks:
                    march_id = march_ids[i]['march_id']
                    return create_march_overview(march_id)

        # Handle participant detail view
        if 'view-participant-btn' in trigger_id and any(participant_clicks or []):
            # Find which participant button was clicked
            for i, clicks in enumerate(participant_clicks or []):
                if clicks:
                    user_id = participant_ids[i]['user_id']
                    march_id = participant_ids[i]['march_id']

                    # Create participant detail view with back button
                    detail_view = create_participant_detail_view(march_id, user_id)
                    back_button = create_back_to_overview_button(march_id)

                    return [back_button, detail_view]

        # Handle back to march overview from participant detail
        if 'back-to-march-btn' in trigger_id and any(back_to_march_clicks or []):
            # Find which back button was clicked
            for i, clicks in enumerate(back_to_march_clicks or []):
                if clicks:
                    march_id = back_to_march_ids[i]['march_id']
                    return create_march_overview(march_id)

        raise PreventUpdate


    # Separate callback for back-to-all-marches button to avoid missing element errors
    @app.callback(
        Output('main-content', 'children', allow_duplicate=True),
        [Input('back-to-all-marches-btn', 'n_clicks')],
        prevent_initial_call=True
    )
    def handle_back_to_all_marches(n_clicks):
        """Handle back to all marches navigation"""
        if n_clicks:
            return create_march_overview()
        raise PreventUpdate

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
        Output('url', 'pathname'),
        [Input('main-content', 'children')],
        [State('navigation-state', 'data')]
    )
    def update_url(content, nav_state):
        """Update URL based on current view for better navigation"""

        if nav_state is None:
            return no_update

        current_view = nav_state.get('current_view', 'home')
        current_march = nav_state.get('current_march')
        current_participant = nav_state.get('current_participant')

        if current_view == 'march_overview' and current_march:
            return f'/march/{current_march}'
        elif current_view == 'participant_detail' and current_march and current_participant:
            return f'/march/{current_march}/participant/{current_participant}'

        return '/'
