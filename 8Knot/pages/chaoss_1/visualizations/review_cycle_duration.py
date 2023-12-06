from dash import html, dcc
import dash
import dash_bootstrap_components as dbc
from dash import callback
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd
import datetime as dt
import logging
from pages.utils.graph_utils import get_graph_time_values, color_seq
import io
from pages.utils.job_utils import nodata_graph
from queries.prs_query import prs_query as prq
from cache_manager.cache_manager import CacheManager as cm
import time

PAGE = "chaoss_1"
VIZ_ID = "prs-review-cycle-duration"
# NOTE: Need to fix mean/median dataframes

gc_review_cycle_duration = dbc.Card(
    [
        dbc.CardBody(
            [
                html.H3(
                    "Review Cycle Duration",
                    className="card-title",
                    style={"textAlign": "center"},
                ),
                dbc.Popover(
                    [
                        dbc.PopoverHeader("Graph Info:"),
                        dbc.PopoverBody(
                            """
                            Visualizes PR behavior by tracking pull request review cycle times (days)
                            """
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
                                dbc.Label(
                                    "Date Interval:",
                                    html_for=f"date-interval-{PAGE}-{VIZ_ID}",
                                    width="auto",
                                ),
                                dbc.Col(
                                    dbc.RadioItems(
                                        id=f"date-interval-{PAGE}-{VIZ_ID}",
                                        options=[
                                            {
                                                "label": "Day",
                                                "value": "D",
                                            },
                                            {
                                                "label": "Week",
                                                "value": "W",
                                            },
                                            {"label": "Month", "value": "M"},
                                            {"label": "Year", "value": "Y"},
                                        ],
                                        value="M",
                                        inline=True,
                                    ),
                                    className="me-2",
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
                        ),
                    ]
                ),
            ]
        ),
    ],
)

# formatting for graph generation
@callback(
    Output(f"popover-{PAGE}-{VIZ_ID}", "is_open"),
    [Input(f"popover-target-{PAGE}-{VIZ_ID}", "n_clicks")],
    [State(f"popover-{PAGE}-{VIZ_ID}", "is_open")],
)
def toggle_popover(n, is_open):
    if n:
        return not is_open
    return is_open


# callback for prs over time graph
@callback(
    Output(f"{PAGE}-{VIZ_ID}", "figure"),
    [
        Input("repo-choices", "data"),
        Input(f"date-interval-{PAGE}-{VIZ_ID}", "value"),
    ],
    background=True,
)

def prs_review_cycle_graph(repolist, interval):
    # wait for data to asynchronously download and become available.
    cache = cm()
    df = cache.grabm(func=prq, repos=repolist)
    while df is None:
        time.sleep(1.0)
        df = cache.grabm(func=prq, repos=repolist)

    # data ready.
    start = time.perf_counter()
    logging.warning(f"{VIZ_ID} - START")

    # test if there is data
    if df.empty:
        logging.warning(f"{VIZ_ID} - NO DATA AVAILABLE")
        return nodata_graph

    # function for all data pre processing
    mean, median = process_data(df, interval)

    fig = create_figure(mean, median, interval)

    logging.warning(f"{VIZ_ID} - END - {time.perf_counter() - start}")

    return fig

def process_data(df: pd.DataFrame, interval):
    # convert dates to datetime objects rather than strings
    df["created"] = pd.to_datetime(df["created"], utc=True)
    df["closed"] = pd.to_datetime(df["closed"], utc=True)
    mean = pd.DataFrame(None, columns=["Date","Value"])
    median = pd.DataFrame(None, columns=["Date","Value"])
    diff_df = pd.DataFrame(None, columns=["Duration"])
    diff = []

    # order values chronologically by creation date
    df = df.sort_values(by="created", axis=0, ascending=True)

    # variable to slice on to handle weekly period edge case
    period_slice = None
    if interval == "W":
        # this is to slice the extra period information that comes with the weekly case
        period_slice = 10

    # --data frames for PR created, merged, or closed. Detailed description applies for all 3.--

    # get the count of created prs in the desired interval in pandas period format, sort index to order entries
    created_range = df["created"].dt.to_period(interval).value_counts().sort_index()

    # converts to data frame object and created date column from period values
    df_created = created_range.to_frame().reset_index().rename(columns={"index": "Date"})

    # converts date column to a datetime object, converts to string first to handle period information
    # the period slice is to handle weekly corner case
    df_created["Date"] = pd.to_datetime(df_created["Date"].astype(str).str[:period_slice])

    # df for closed prs in time interval
    closed_range = pd.to_datetime(df["closed"]).dt.to_period(interval).value_counts().sort_index()
    df_closed = closed_range.to_frame().reset_index().rename(columns={"index": "Date"})
    df_closed["Date"] = pd.to_datetime(df_closed["Date"].astype(str).str[:period_slice])

    for x,y in zip(df["closed"], df["created"]):
        difference = y - x
        diff.append(difference.days)

    for x in range(1,50):
        logging.warning(f"\n\n\nDIFF\n{diff[x]}\n\n\n")
    
    diff_df["Duration"] = diff

    mean["Value"] = diff_df["Duration"]
    mean["Date"] = df_closed["Date"]
    mean.groupby(pd.PeriodIndex(mean["Date"], freq=interval)).mean()

    median["Value"] = diff_df["Duration"]
    median["Date"] = df_closed["Date"]
    median.groupby(pd.PeriodIndex(median["Date"], freq=interval)).median()

    # formatting for graph generation
    if interval == "M":
        mean["Date"] = mean["Date"].dt.strftime("%Y-%m-01")
        median["Date"] = median["Date"].dt.strftime("%Y-%m-01")
    elif interval == "Y":
        mean["Date"] = mean["Date"].dt.strftime("%Y-01-01")
        median["Date"] = median["Date"].dt.strftime("%Y-01-01")


    #logging.warning(f"\n\n\nMEAN\n{mean}\n")
    #logging.warning(f"\nMEDIAN\n{median}\n\n\n\n")
    return mean, median


def create_figure(
    mean: pd.DataFrame,
    median: pd.DataFrame,
    interval
):
    x_r, x_name, hover, period = get_graph_time_values(interval)
    
    # graph generation
    fig = go.Figure()
    fig.add_bar(
        x=mean["Date"],
        y=mean["Value"],
        opacity=0.9,
        hovertemplate=hover + "<br>Average: %{y}<br>" + "<extra></extra>",
        offsetgroup=0,
        marker=dict(color=color_seq[2]),
        name="Average",
    )
    fig.add_bar(
        x=median["Date"],
        y=median["Value"],
        opacity=0.9,
        hovertemplate=hover + "<br>Median: %{y}<br>" + "<extra></extra>",
        offsetgroup=1,
        marker=dict(color=color_seq[4]),
        name="Median",
    )
    fig.update_xaxes(
        showgrid=True,
        ticklabelmode="period",
        dtick=period,
        rangeslider_yaxis_rangemode="match",
        range=x_r,
    )
    fig.update_layout(
        xaxis_title=x_name,
        yaxis_title="Hrs",
        bargroupgap=0.1,
        margin_b=40,
        font=dict(size=14),
    )
    
    return fig


# for each day, this function calculates the amount of open prs
def get_open(df, date):
    # drop rows that are more recent than the date limit
    df_created = df[df["created"] <= date]

    # drops rows that have been closed after date
    df_open = df_created[df_created["closed"] > date]

    # include prs that have not been close yet
    df_open = pd.concat([df_open, df_created[df_created.closed.isnull()]])

    # generates number of columns ie open prs
    num_open = df_open.shape[0]
    return num_open
