from dash import html, dcc, callback
import dash
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import pandas as pd
import logging
from dateutil.relativedelta import *  # type: ignore
import plotly.express as px
from pages.utils.graph_utils import get_graph_time_values, color_seq
#from queries.change_requests_query import change_requests_query as crq
from queries.prs_query import prs_query as prq
import io
from cache_manager.cache_manager import CacheManager as cm
from pages.utils.job_utils import nodata_graph
import time
import datetime as dt
import math
import numpy as np

"""
NOTE: VARIABLES TO CHANGE:

X (1) PAGE
X (2) VIZ_ID
X (3) gc_VISUALIZATION
X (4) TITLE OF VISUALIZATION
X (5) CONTEXT OF GRAPH
X (6) IDs of Dash components
X (6) NAME_OF_VISUALIZATION_graph
(7) COLUMN_WITH_DATETIME
(8) COLUMN_WITH_DATETIME
(9) COLUMN_TO_SORT_BY
X (10) Comments before callbacks
X (11) QUERY_USED, QUERY_NAME, QUERY_INITIALS

NOTE: IMPORTING A VISUALIZATION INTO A PAGE
(1) Include the visualization file in the visualization folder for the respective page
(2) Import the visualization into the page_name.py file using "from .visualizations.visualization_file_name import gc_visualization_name"
(3) Add the card into a column in a row on the page

NOTE: ADDITIONAL DASH COMPONENTS FOR USER GRAPH CUSTOMIZATIONS

If you add Dash components (ie dbc.Input, dbc.RadioItems, dcc.DatePickerRange...) the ids, html_for, and targets should be in the
following format: f"component-identifier-{PAGE}-{VIZ_ID}"

NOTE: If you change or add a new query, you need to do "docker system prune -af" before building again

For more information, check out the new_vis_guidance.md
"""


# TODO: Remove unused imports and edit strings and variables in all CAPS
# TODO: Remove comments specific for the template

PAGE = "chaoss_1"  # EDIT FOR CURRENT PAGE
VIZ_ID = "change-requests-duration"  # UNIQUE IDENTIFIER FOR VIZUALIZATION

gc_change_requests_duration = dbc.Card(
    [
        dbc.CardBody(
            [
                html.H3(
                    "Change Requests Duration",
                    className="card-title",
                    style={"textAlign": "center"},
                ),
                dbc.Popover(
                    [
                        dbc.PopoverHeader("Graph Info:"),
                        dbc.PopoverBody(
                            """The change request duration is the duration of the period since the change request started, 
                            to the moment it ended (by being accepted and being merged in the code base). 
                            This only applies to accepted change requests. For example, 
                            in GitLab a change request starts when a developer uploads a proposal for a change in code, 
                            opening a change request. It finishes when the change request is finally accepted 
                            and merged in the code base, closing the change request."""
                        ),
                    ],
                    id=f"popover-{PAGE}-{VIZ_ID}",
                    target=f"popover-target-{PAGE}-{VIZ_ID}",
                    placement="top",
                    is_open=False,
                ),
                dcc.Loading(
                    dcc.Graph(id=f"{PAGE}-{VIZ_ID}"),
                ),
                dbc.Form(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    dcc.DatePickerRange(
                                        id=f"date-picker-range-{PAGE}-{VIZ_ID}",
                                        min_date_allowed=dt.date(2005, 1, 1),
                                        max_date_allowed=dt.date.today(),
                                        initial_visible_month=dt.date(dt.date.today().year, 1, 1),
                                        clearable=True,
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        "About Graph",
                                        id=f"popover-target-{PAGE}-{VIZ_ID}",
                                        color="secondary",
                                        size="sm",
                                    ),
                                    width="auto",
                                    style={"paddingTop": ".5em"},
                                ),
                            ],
                            align="center",
                            justify="between",
                        ),
                    ]
                ),
            ]
        )
    ],
)


# callback for graph info popover
@callback(
    Output(f"popover-{PAGE}-{VIZ_ID}", "is_open"),
    [Input(f"popover-target-{PAGE}-{VIZ_ID}", "n_clicks")],
    [State(f"popover-{PAGE}-{VIZ_ID}", "is_open")],
)
def toggle_popover(n, is_open):
    if n:
        return not is_open
    return is_open


# callback for Change Requests Duration graph
@callback(
    Output(f"{PAGE}-{VIZ_ID}", "figure"),
    # Output(f"check-alert-{PAGE}-{VIZ_ID}", "is_open"), USE WITH ADDITIONAL PARAMETERS
    # if additional output is added, change returns accordingly
    [
        Input("repo-choices", "data"),
        Input(f"date-picker-range-{PAGE}-{VIZ_ID}", "start_date"),
        Input(f"date-picker-range-{PAGE}-{VIZ_ID}", "end_date"),
    ],
    background=True,
)
def change_requests_duration_graph(repolist, start_date, end_date):
    # wait for data to asynchronously download and become available.
    cache = cm()
    df = cache.grabm(func=prq, repos=repolist)
    while df is None:
        time.sleep(1.0)
        df = cache.grabm(func=prq, repos=repolist)

    start = time.perf_counter()
    logging.warning(f"{VIZ_ID}- START")

    # test if there is data
    if df.empty:
        logging.warning(f"{VIZ_ID} - NO DATA AVAILABLE")
        return nodata_graph

    # function for all data pre processing, COULD HAVE ADDITIONAL INPUTS AND OUTPUTS
    df = process_data(df, start_date, end_date)

    fig = create_figure(df, start_date, end_date)

    logging.warning(f"{VIZ_ID} - END - {time.perf_counter() - start}")
    return fig


def process_data(df: pd.DataFrame, start_date, end_date):
    """Implement your custom data-processing logic in this function.
    The output of this function is the data you intend to create a visualization with,
    requiring no further processing."""

    # convert to datetime objects rather than strings
    # ADD ANY OTHER COLUMNS WITH DATETIME
    df["created"] = pd.to_datetime(df["created"], utc=True)
    df["merged"] = pd.to_datetime(df["merged"], utc=True)
    df["closed"] = pd.to_datetime(df["closed"], utc=True)

    # order values chronologically by created date
    df = df.sort_values(by="created", axis=0, ascending=True)
    
    # filter values based on date picker
    if start_date is not None:
        df = df[df.created >= start_date]
    if end_date is not None:
        df = df[df.created <= end_date]

    # then add new column for duration
    df['duration'] = (df['merged'] - df['created']).dt.days
    
    return df


def create_figure(df: pd.DataFrame, start_date, end_date):
    fig = px.box(df, y="duration")

    return fig
