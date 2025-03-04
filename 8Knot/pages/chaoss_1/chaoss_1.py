from dash import html, dcc
import dash
import dash_bootstrap_components as dbc
import warnings

# import visualization cards
from .visualizations.issue_response_time import gc_issue_response_time
from .visualizations.organizational_diversity import gc_organizational_diversity
from .visualizations.review_cycle_duration import gc_review_cycle_duration
from .visualizations.defect_resolution_duration import gc_defect_resolution_duration
from.visualizations.change_requests_duration import gc_change_requests_duration


warnings.filterwarnings("ignore")

dash.register_page(__name__, path="/chaoss_1")

layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(gc_defect_resolution_duration, width=6),
                dbc.Col(gc_change_requests_duration, width=6),
            ],
            align="center",
            style={"marginBottom": ".5%"},
        ),
        dbc.Row(
            [
                dbc.Col(gc_review_cycle_duration, width=6),
            ],
            align="center",
            style={"marginBottom": ".5%"},
        ),
    ],
    fluid=True,
)
