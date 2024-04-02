from dash import Dash, html, dcc, callback, Output, Input, State
from dash import dash_table, no_update, callback_context
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
import dash_daq as daq
from datetime import datetime
import numpy as np
import os
import pandas as pd
from pathlib import Path
import plotly.express as px
import plotly.graph_objs as go
import src.predictions_with_land_mask as preds



# Initialize the app
app = Dash(__name__, external_stylesheets=[dbc.themes.SPACELAB])
load_figure_template('SPACELAB')

# Timestamps for existing SAR images
timestamp_file = 'data/timestamps_sar_images.csv'
df_timestamp = pd.read_csv(timestamp_file)
df_timestamp = df_timestamp.set_index('TILE_ID')
sar_dates = df_timestamp['DATE'].unique().tolist()

# AIS data from datalastic dataset
ais_file = 'data/ais_datalastic_filtered.csv'
df_ais = pd.read_csv(ais_file)
df_ais['timestamp'] = pd.to_datetime(df_ais['timestamp'])

# Path to the SAR images
bucket_id = os.environ.get('SAR_BUCKET')
local_path = f'data/{bucket_id}/VH'
# local_path = 'data/bucket/VH'

# Get list of SAR images from local path
list_of_imgs = os.listdir(local_path)

# Base map for Laconian Bay
latitude = 36.53353  # 36.34289 
longitude = 22.721728  # 22.43289


#==============================================================================
# Define the content of the app
#==============================================================================


header_content = html.Div([
    html.H1('My Dashboard', id='header'),
])

#==============================================================================

sidebar_content = html.Div([
    html.H2("Sidebar", className="display-4"),
    html.Hr(),
    html.P(
        "A simple sidebar layout with navigation links", className="lead"
    ),
    dbc.Nav(
        [
            dbc.NavLink("Home", href="/", active="exact"),
            dbc.NavLink("About", href="/about", active="exact"),
            # dbc.NavLink("Page 2", href="/page-2", active="exact"),
        ],
        vertical=True,
        pills=True,
    ),
    dcc.Dropdown(
        id='date-dropdown',
        options=[{'label': date, 'value': date} for date in sar_dates],
        value=sar_dates[0] if sar_dates else None,  # Sets the default value to the first date
    ),
    dbc.Button('Previous', id='prev-btn', n_clicks=0),
    dbc.Button('Next', id='next-btn', n_clicks=0),
    html.Div(id='selected-date-display')
])

#==============================================================================

map_content = html.Div([
    dbc.Button('Run', id='run-button', n_clicks=0),
    dcc.Graph(
        id='base-map',
        config={'displayModeBar': False},
        clickData=None),
    dash_table.DataTable(
        id='data-table',
        columns=[
            {'name': 'Name', 'id': 'name'},
            {'name': 'Latitude', 'id': 'lat'},
            {'name': 'Longitude', 'id': 'lon'},
            {'name': 'Prediction', 'id': 'prediction'}
        ],
        data=[]),
])

#==============================================================================

report_content = html.Div([
    dash_table.DataTable(
        id='click-output-data',
        columns=[
            {"name": "Attribute", "id": "Attribute"}, 
            {"name": "Value", "id": "Value"}
        ],
        style_cell_conditional=[
            {'if': {'column_id': 'Attribute'}, 'width': '60px'},
            {'if': {'column_id': 'Value'}, 'width': '240px'}
        ],
        style_cell={
            'textAlign': 'left', 
            'minWidth': '60px',
            'maxWidth': '240px',
            'whiteSpace': 'normal'
        },
        style_data=dict(height='20px'),
        style_table={'overflowX': 'auto'},
    ),
    html.Img(
        id='image-placeholder', 
        # src='data/results/S1A_IW_GRDH_1SDV_20230215T162338_20230215T162403_047249_05AB7F_600C/ship_2.png', 
        alt='Image will be displayed here',
    ),
])

#==============================================================================
# Define the layout of the app
#==============================================================================


app.layout = dbc.Container(
    [
        dbc.Row(
            [
                # Header
                dbc.Col(
                    header_content,
                    style={'textAlign': 'left', "background-color": "#f8f9fa", "padding": "1rem 1rem"},
                ),
            ],
        ),
        dbc.Row(
            [
                # Left sidebar
                dbc.Col(
                    sidebar_content,
                    width=2, # 2 out of 12 columns
                    style={"background-color": "#f8f9fa", "padding": "1rem 1rem"},
                ),
                # Map
                dbc.Col(
                    map_content,
                    width=8, # 8 out of 12 columns
                    style={'background-color': '#f8f9fa', "padding": "1rem 1rem"},
                ),
                # Right sidebar
                dbc.Col(
                    report_content,
                    width=2, # 2 out of 12 columns
                    style={"background-color": "#f8f9fa", "padding": "1rem 0rem"},
                ),
            ],
        )
    ],
    fluid=True,
)


#==============================================================================
# Define the app callbacks
#==============================================================================

# Callback to update dates
@app.callback(
    Output('date-dropdown', 'value'),
    [Input('prev-btn', 'n_clicks'),
     Input('next-btn', 'n_clicks')],
    [State('date-dropdown', 'value')]
)
def update_dropdown(prev_clicks, next_clicks, current_value):
    ctx = callback_context
    if not ctx.triggered or not sar_dates:
        return sar_dates[0] if sar_dates else None
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        current_index = sar_dates.index(current_value)
        if button_id == 'next-btn':
            new_index = min(len(sar_dates) - 1, current_index + 1)
        elif button_id == 'prev-btn':
            new_index = max(0, current_index - 1)
        else:
            new_index = current_index
        return sar_dates[new_index]

# Callback to display the selected date
@app.callback(
    Output('selected-date-display', 'children'),
    [Input('date-dropdown', 'value')]
)
def display_selected_date(selected_date):
    return f'Selected Date: {selected_date}'

#==============================================================================

# Callback to run the model on selected date
@app.callback(
    # [Output('data-table', 'data'), Output('run-button', 'children')],
    Output('data-table', 'data'),
    Input('run-button', 'n_clicks'),
    State('date-dropdown', 'value')
)
def run_model(n_clicks, date):
    if n_clicks > 0:
        # Get image ID from date picker value
        mask_date = df_timestamp['DATE'] == date
        image_list = list(df_timestamp[mask_date].index)
        
        # df_preds = pd.read_csv('results/S1A_IW_GRDH_1SDV_20220201T163119_20220201T163144_041722_04F6E6_38F5.csv')  # FOR TESTING
        
        predictions = []
        # Run predictions on all images for the selected date
        for image_id in image_list:
            image_file = f'{image_id}.tif'
            print(f"Predictions on {image_file}")
            df_preds = preds.predict(image_file, plot=False)
            predictions.append(df_preds)
        # Concatenate predictions
        df_preds = pd.concat(predictions, ignore_index=True, axis=0)
        
        df_preds.columns = ['name', 'lat', 'lon', 'prediction', 'image']
        data = df_preds.to_dict('records')
        return data
    return []

#==============================================================================

@app.callback(
    Output('base-map', 'figure'),
    [Input('run-button', 'n_clicks'), Input('data-table', 'data')]
)
def update_map(n_clicks, data):
    if n_clicks > 0:
        # # Convert data to DataFrame for easier manipulation
        fig = px.scatter_mapbox(
            data,
            lat="lat",
            lon="lon",
            color="prediction",
            zoom=9,
            height=700,
            mapbox_style="carto-positron",
            hover_data=['name', 'lat', 'lon', 'prediction', 'image']
        )
        fig.update_layout(
            # mapbox_bounds={"west": 22.35, "east": 23.12, "south": 36.35, "north": 36.85},
            margin={"r": 5, "t": 5, "l": 5, "b": 5}
        )
        fig.update(layout_coloraxis_showscale=False)
        fig.update_mapboxes(center=dict(lat=latitude, lon=longitude))
        return fig
    
    fig = px.scatter_mapbox(
        lat=[latitude],
        lon=[longitude],
        zoom=9,
        height=700,
        mapbox_style='carto-positron',  # open-street-map
    )
    fig.update_traces(
        marker=dict(
            size=0, # Adjust the size as needed
            symbol="circle", # Set symbol to 'circle'
        ),
        selector=dict(mode="markers"),
    )
    fig.update_layout(
        # mapbox_bounds={"west": 22.35, "east": 23.12, "south": 36.35, "north": 36.85},
        margin={"r": 5, "t": 5, "l": 5, "b": 5}
    )
    fig.update(layout_coloraxis_showscale=False)
    fig.update_mapboxes(center=dict(lat=latitude, lon=longitude))
    return fig  

#==============================================================================

# Define a callback to update the graph when the switch is toggled
# @app.callback(
#     Output('base-map', 'figure'), 
#     [Input('toggle-switch', 'on')],
#     [State('date-picker', 'date'), State('base-map', 'figure')],
# )
# def update_graph(toggle_on, date, current_figure):
#     if toggle_on:
#         # Get image ID from date picker value
#         mask_date = df_timestamp['DATE'] == date
#         image_list = list(df_timestamp[mask_date].index)
#         # Get timestamp for selected image
#         image_timestamp = df_timestamp.loc[image_list[0], 'TIMESTAMP']
        
#         # Filter for date range of SAR image
#         timedelta = 45  # minutes
#         start = pd.to_datetime(image_timestamp) - pd.Timedelta(timedelta, 'min')
#         end = pd.to_datetime(image_timestamp) + pd.Timedelta(timedelta, 'min')
#         df_ais_filtered = df_ais[df_ais.timestamp.between(start, end)].copy()

#         # Aggregate coordinates for each vessel
#         df_ais_agg = df_ais_filtered.groupby(['name', 'mmsi']).agg({'lat': 'mean', 'lon': 'mean'}).reset_index()
#         df_ais_agg['prediction'] = 0
        
#         fig = px.scatter_mapbox(
#             df_ais_agg,
#             lat="lat",
#             lon="lon",
#             color="prediction",
#             zoom=8,
#             height=700,
#             mapbox_style="carto-positron",
#             hover_data=['name', 'mmsi','lat', 'lon']
#         )
#         # fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
#         fig.update(layout_coloraxis_showscale=False)
#         # fig.update_mapboxes(center=dict(lat=latitude, lon=longitude))
#         # fig.update_layout(mapbox_bounds={"west": 20.0, "east": 25.0, "south": 35.0, "north": 37.0})
        
#         fig.update_traces(
#             marker=dict(
#                 size=15, # Adjust the size as needed
#                 symbol="circle", # Set symbol to 'circle'
#             ),
#             selector=dict(mode="markers"),
#         )
#         return fig
#     else:
#         # The switch is in the "off" state
#         # Update the graph with a different set of data
#         return current_figure

#==============================================================================

# @app.callback(
#     Output('click-output', 'data'),
#     Input('base-map', 'clickData'))
# def display_click_data(clickData):
#     if clickData is None:
#         return [{}]
#     else:
#         point_data = clickData['points'][0]
#         return [{
#             "Name": point_data['customdata'][0],
#             "Lat": point_data['lat'],
#             "Lon": point_data['lon']
#         }]
        

@app.callback(
    Output('click-output-data', 'data'),
    Input('base-map', 'clickData'))
def display_click_data_table(clickData):
    if clickData is None:
        return [{}]
    else:
        point_data = clickData['points'][0]
        data = [
            # {"Attribute": "Name", "Value": point_data.get('name')},
            {"Attribute": "Name", "Value": point_data.get('customdata', [None])[0]},
            {"Attribute": "Lat", "Value": point_data.get('lat')},
            {"Attribute": "Lon", "Value": point_data.get('lon')},
            {"Attribute": "Prediction", "Value": point_data.get('prediction')},
            # {"Attribute": "Name", "Value": point_data.get('customdata', [None])[4]},
            # {"Attribute": "Image", "Value": point_data.get('image')}
        ]
    return data


@app.callback(
    Output('image-placeholder', 'src'),
    Input('base-map', 'clickData'))
def display_click_data_image(clickData):
    if clickData is None:
        return ''
    else:
        point_data = clickData['points'][0]
        image = point_data.get('customdata', 'no image')[4]  # local path to image
        return image


# Run the app
if __name__ == '__main__':
    app.run(debug=True)
