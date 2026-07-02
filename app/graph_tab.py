# plot tab — Open-Meteo fetch + Matplotlib canvas
import pandas as pd
import matplotlib.dates as mdates
from PyQt6.QtWidgets import QFileDialog
import openmeteo_requests, requests_cache
from retry_requests import retry

cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

def plot_graph(self):
    latitude = float(self.latitude_input.text().strip())
    longitude = float(self.longitude_input.text().strip())
    start_date = str(self.start_input_field.text().strip())
    end_date = str(self.end_input_field.text().strip())

    selected_variables = [
        var for var, checkbox in self.variables.items() if checkbox.isChecked()
    ]
    
    if not selected_variables:
        raise ValueError("At least one variable must be selected!")
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "models": "era5_seamless",
        "timezone": "auto",
        "daily": selected_variables  
    }
    try:
        responses = openmeteo.weather_api(url, params=params)

        if not responses:
            self.status("Check Your internet connection", 50000)

        response = responses[0]
        daily = response.Daily()

        daily_data = {
            "date": pd.date_range(
                start=pd.to_datetime(daily.Time(), unit="s", utc=True),
                end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=daily.Interval()),
                inclusive="left"
            )
        }

        for i, variable in enumerate(selected_variables):
            values = daily.Variables(i).ValuesAsNumpy()
            daily_data[variable] = values

        daily_dataframe = pd.DataFrame(daily_data)
        daily_data['date'] = pd.to_datetime(daily_data['date'])
        x = daily_data['date']

        self.figure.clear()

        ax1 = self.figure.add_subplot(111)

        variable_config = {
            "temperature_2m_max": {"axis": "primary", "type": "line", "color": "#d62728"},
            "temperature_2m_min": {"axis": "primary", "type": "line", "color": "#ff7f0e"},
            "temperature_2m_mean": {"axis": "primary", "type": "line", "color": "#1f77b4"},
            "precipitation_sum": {"axis": "secondary", "type": "bar", "color": "#4A90E2"},
            "et0_fao_evapotranspiration": {"axis": "secondary", "type": "line", "color": "#2ca02c"},
        }

        ax2 = None

        # Plot each variable with its configuration
        for variable in selected_variables:
            config = variable_config.get(variable, {})
            axis = config.get("axis", "primary")
            plot_type = config.get("type", "line")
            color = config.get("color", "black")

            if axis == "primary":
                if plot_type == "line":
                    ax1.plot(
                        daily_dataframe["date"],
                        daily_dataframe[variable],
                        label=variable.replace("_", " ").capitalize(),
                        color=color
                    )
            elif axis == "secondary":
                if not ax2:
                    ax2 = ax1.twinx()
                if plot_type == "line":
                    ax2.plot(
                        daily_dataframe["date"],
                        daily_dataframe[variable],
                        label=variable.replace("_", " ").capitalize(),
                        color=color
                    )
                elif plot_type == "bar":
                    if variable == "precipitation_sum":
                        ax2.bar(
                            x - pd.Timedelta(days=0.2),
                            daily_data[variable],
                            width=0.8,
                            color="#4A90E2",
                            alpha=0.5,
                            label="Precipitation sum",
                        )

        ax1.set_ylabel("°C", color="red")
        ax1.tick_params(axis="y", labelcolor="red")
        ax1.xaxis.set_major_locator(mdates.YearLocator(2))

        if ax2:
            ax2.set_ylabel("mm", color="blue")
            ax2.tick_params(axis="y", labelcolor="blue")

        handles, labels = ax1.get_legend_handles_labels()
        if ax2:
            handles2, labels2 = ax2.get_legend_handles_labels()
            handles.extend(handles2)
            labels.extend(labels2)
        ax1.legend(handles, labels, loc="upper left", title="Variables")

        ax1.set_title("Weather Data")
        ax1.set_xlabel('Date') 
        ax1.grid(True)
        self.canvas.draw()
        
        self.save_button.setEnabled(True)
        self.save_button.clicked.connect(lambda: save_spi_data(daily_data))
        
        def save_spi_data(data):
            file_dialog = QFileDialog()
            save_path, _ = file_dialog.getSaveFileName(self, "Save Weather Data", "", "CSV Files (*.csv)")
            if save_path:
                data = pd.DataFrame(data = daily_data)
                data.to_csv(save_path)
                self.status(f"Weather data saved to {save_path}", 5000)
    except Exception as e:
        self.status(f"Error fetching data: {e}", 10000)