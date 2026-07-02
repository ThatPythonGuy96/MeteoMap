# This module provides a function to fetch historical weather data from the Open-Meteo API.
import os
import pandas as pd
import openmeteo_requests, requests_cache
from retry_requests import retry
from utils.paths import get_app_temp_dir

cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

def openMeteo(latitude, longitude, start_date, end_date, status_callback=None):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "models": "era5_seamless",
        "timezone": "auto",
        "daily": ["precipitation_sum", "et0_fao_evapotranspiration"]
    }
    try:
        responses = openmeteo.weather_api(url, params=params)
        
        if status_callback:
            status_callback("Getting Data...", 5000)

        if not responses:
            status_callback("Check your internet connection.", 10000)

        response = responses[0]
        daily = response.Daily()
        
        daily_precipitation_sum = daily.Variables(0).ValuesAsNumpy()
        daily_et0_fao_evapotranspiration = daily.Variables(1).ValuesAsNumpy()
        
        daily_data = {"date": pd.date_range(
            start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
            end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = daily.Interval()),
            inclusive = "left"
        )}
        
        daily_data["precipitation_sum"] = daily_precipitation_sum
        daily_data["et0_fao_evapotranspiration"] = daily_et0_fao_evapotranspiration
        
        df = pd.DataFrame(data = daily_data)
        
        if status_callback:
            status_callback("Saving Data...", 2000)
        
        temp_dir = get_app_temp_dir()
        temp_path = os.path.join(temp_dir, f"climate_{latitude}_{longitude}.csv")
        df.to_csv(temp_path, index=False)
        return temp_path
    except Exception as e:
        if status_callback:
            status_callback(f"Error fetching or processing data: {e}", 100000)
        return None
    