import os
import folium
import math
import exifread
import datetime
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from jinja2 import Environment, FileSystemLoader
import plotly.express as px
import json
import plotly.graph_objects as go
import numpy as np
import shutil


# Extracts geo-position tags from the image(s)
def extract_gps_tags(image_path):
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f)

    lat_tag = tags.get('GPS GPSLatitude')
    lon_tag = tags.get('GPS GPSLongitude')
    date_taken_tag = tags.get('EXIF DateTimeOriginal')  # Добавляем тег для даты и времени создания фото

    if lat_tag and lon_tag:
        lat_values = [float(x.num) / float(x.den) if x.den != 0 else 0.0 for x in lat_tag.values]
        lon_values = [float(x.num) / float(x.den) if x.den != 0 else 0.0 for x in lon_tag.values]

        lat = lat_values[0] + lat_values[1] / 60 + lat_values[2] / 3600
        lon = lon_values[0] + lon_values[1] / 60 + lon_values[2] / 3600

        date_taken = datetime.datetime.strptime(str(date_taken_tag),
                                                '%Y:%m:%d %H:%M:%S') if date_taken_tag else None  # Преобразуем строку даты в объект datetime

        return lat, lon, date_taken

    return None, None, None


def get_weather_data(lat, lon, date_taken):
    session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": [round(l, 2) for l in lat],
        "longitude": [round(l, 2) for l in lon],
        "start_date": [(date - datetime.timedelta(days=5)).strftime("%Y-%m-%d") for date in date_taken],
        "end_date": [(date + datetime.timedelta(days=5)).strftime("%Y-%m-%d") for date in date_taken],
        "hourly": ["temperature_2m", "precipitation", "wind_speed_10m"]
    }
    responses = openmeteo.weather_api(url, params=params)

    weather_dataframes = []
    # Process first location. Add a for-loop for multiple locations or weather models
    for i in range(0, len(lat)):
        response = responses[i]

        hourly = response.Hourly()
        hourly_temperature_2m = np.round(hourly.Variables(0).ValuesAsNumpy(), 1)
        hourly_precipitation = np.round(hourly.Variables(1).ValuesAsNumpy(), 2)
        hourly_wind_speed_10m = np.round(hourly.Variables(2).ValuesAsNumpy(), 2)

        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            ),
            "temperature_2m": hourly_temperature_2m,
            "precipitation": hourly_precipitation,
            "wind_speed_10m": hourly_wind_speed_10m
        }

        hourly_dataframe = pd.DataFrame(data=hourly_data)
        weather_dataframes.append(hourly_dataframe)
    return weather_dataframes


def export_data(output_folder, image_folder):
    image_paths = [os.path.join(image_folder, filename) for filename in os.listdir(image_folder) if
                   filename.lower().endswith(('.jpg', '.jpeg', '.tiff', '.png'))]
    lats, lons, dates = [], [], []
    for idx, image_path in enumerate(image_paths):
        lat, lon, date_taken = extract_gps_tags(image_path)

        if lat and lon and date_taken and all(math.isfinite(coord) for coord in (lat, lon)):
            lat, lon = round(lat, 6), round(lon, 6)
            lats.append(lat)
            lons.append(lon)
            dates.append(date_taken)


    points_file = os.path.join(output_folder, 'points.json')
    graphs_per_point = create_plotly_graphs(get_weather_data(lats, lons, dates))

    # Convert plotly graphs to JSON-compatible format
    points_json = []
    for i in range(len(lats)):
        pointDict = {
            'lat': lats[i],
            'lon': lons[i],
            'timestamp': dates[i].strftime('%Y-%m-%d'),
            'pointIndex': i   # Store the index of associated graph
        }
        for key, value in graphs_per_point[i].items():
            pointDict[key] = value.to_json()
        points_json.append(pointDict)

    with open(points_file, 'w') as f:
        json.dump(points_json, f)

    shutil.copy('Resources/index.html', output_folder)  # Copy the HTML file
    shutil.copy('Resources/script.js', output_folder)  # Copy the JS file
    messagebox.showinfo('Успех', f'Интерактивная карта сохранена в {output_folder}')


def create_plotly_graphs(weather_dataframes):
    graphs = []
    for df in weather_dataframes:

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['temperature_2m'],
            name='Temperature',
            mode='lines',
            line_color="#b30000",
        ))
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['wind_speed_10m'],
            name='Wind Speed',
            mode='lines',
            line_color="#00b7c7",
        ))
        fig.update_layout(title='Temperature & Wind',
                          xaxis_title="Date",
                          yaxis_title="",
                          template='plotly_white')
        fig.update_traces(
            hovertemplate="%{x}<br>Temperature: %{y} C<extra></extra>", selector={'name': 'Temperature'}
        )
        fig.update_traces(
            hovertemplate="%{x}<br>Wind Speed: %{y} km/h<extra></extra>", selector={'name': 'Wind Speed'}
        )

        fig.update_layout(showlegend=False)
        fig.update_layout(
            yaxis=dict(
                showticklabels=False  # Set to False to hide tick labels
            )
        )

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df['date'],
            y=df['temperature_2m'],
            name='Precipitation',
            mode='lines',
            line_color="#1a53ff",
        ))
        fig2.update_layout(title='Precipitation',
                          xaxis_title="Date",
                          yaxis_title="",
                          template='plotly_white')
        fig2.update_traces(
            hovertemplate="%{x}<br>Precipitation: %{y} mm<extra></extra>"  # For bars (if needed)
        )
        fig2.update_layout(showlegend=False)
        fig2.update_layout(
            yaxis=dict(
                showticklabels=False  # Set to False to hide tick labels
            )
        )

        graphs.append({"plot1": fig, "plot2": fig2})

    return graphs




# 'Get Data' Button is pressed
def get_data():
    image_folder = filedialog.askdirectory()
    if not image_folder:
        messagebox.showerror('Ошибка', 'Папка с фотографиями не выбрана.')
        return

    output_folder = filedialog.askdirectory()
    if not output_folder:
        messagebox.showerror('Ошибка', 'Папка для сохранения данных не выбрана.')
        return
    export_data(output_folder, image_folder)


# Folders Selection Dialogue
window = tk.Tk()
window.title('GPS Data Extractor')
window.geometry('400x200')

# Button Style
style = ttk.Style()
style.configure('TButton', font=('Open Sans', 20), foreground='green', background='white', width=20, height=2)

get_data_button = ttk.Button(window, text='Получить данные', command=get_data, style='TButton')
get_data_button.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

window.mainloop()
