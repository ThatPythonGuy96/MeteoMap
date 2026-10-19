# raster_to_point, shp_to_geojson, nc_to_raster, nc_to_csv
import os, time
import pandas as pd
from shapely.geometry import Point
import numpy as np
import geopandas as gpd
import rasterio
import netCDF4 as nc
import xarray as xr
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QPushButton, QFileDialog, QLabel, QHBoxLayout, QListWidget
from PyQt6.QtWidgets import QDialog, QPushButton, QProgressBar, QLineEdit
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
from utils.paths import resource_path
from utils.logger import setup_logger

logger = setup_logger()

def raster_to_point(self):
    dialog = QDialog()
    dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
    dialog.setWindowTitle("Raster to Point")
    dialog.resize(500, 300)
    layout = QVBoxLayout(dialog)

    input_layout = QHBoxLayout()
    input_widget = QLineEdit()
    layout.addWidget(QLabel("Input Raster Path:"))
    input_layout.addWidget(input_widget)
    layout.addLayout(input_layout)
    
    progress_bar = QProgressBar(self)
    progress_bar.setValue(0)
    self.main_window.status_Bar.addPermanentWidget(progress_bar)
    
    def open_file_dialog():
        raster_file, _ = QFileDialog.getOpenFileName(self, "Select Raster File", "", "TIF Files (*.tif)")
        if raster_file:
            input_widget.setText(raster_file)
                    
    load_layer_button = QPushButton(dialog)
    load_layer_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_layer_button.setIconSize(QSize(25, 25))
    load_layer_button.clicked.connect(open_file_dialog)
    input_layout.addWidget(load_layer_button)

    output_layout = QHBoxLayout()
    output_input = QLineEdit()
    layout.addWidget(QLabel("Output Path:"))
    output_layout.addWidget(output_input)
    layout.addLayout(output_layout)

    def save_data():
        output_path, _ = QFileDialog.getSaveFileName(dialog, "Save Shape File", "", "Shapefile Files (*.shp)")
        if output_path:
            output_input.setText(output_path)

    load_output_button = QPushButton(dialog)
    load_output_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_output_button.setIconSize(QSize(25, 25))
    load_output_button.clicked.connect(save_data)
    output_layout.addWidget(load_output_button)

    button_layout = QHBoxLayout()
    ok_button = QPushButton("Ok")
    cancel_button = QPushButton("Cancel")
    button_layout.addWidget(ok_button)
    button_layout.addWidget(cancel_button)
    layout.addLayout(button_layout)
    ok_button.clicked.connect(dialog.accept)
    cancel_button.clicked.connect(dialog.reject)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        output_path = output_input.text()
        input_path = input_widget.text()
        
        def progress(i):
            for i in range(1, 101):
                progress = int((i / total_points) * 100)
                progress_bar.setValue(progress)
                if i % 100 == 0:  # Update UI every 100 iterations
                    QApplication.processEvents()
        try:
            with rasterio.open(input_path) as src:
                band = src.read(1)
                transform = src.transform
                crs = src.crs if src.crs is not None else "EPSG:4326"
                rows, cols = np.where(band != src.nodata)
                points = []
                values = []
                total_points = len(rows)
                for i, (r, c) in enumerate(zip(rows, cols)):
                    progress(i)
                    value = band[r, c]
                    values.append(value)
                    x, y = transform * (c, r)
                    points.append(Point(x, y))

                gdf = gpd.GeoDataFrame({'value': values, 'geometry': points}, crs=crs)
                gdf.to_file(output_path, driver='ESRI Shapefile')
                self.main_window.status("Conversion Complete.", 2000)
                self.main_window.status(f"Loading {output_path}", 3000)

                self.main_window.create_layer(output_path)
        except Exception as e:
            self.main_window.status(f"Error: {e}", 10000)
        finally:
            self.main_window.status_Bar.removeWidget(progress_bar)

def shapefile_to_geojson(self):
    dialog = QDialog()
    dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
    dialog.setWindowTitle("Shapefile to GeoJSON")
    dialog.resize(500, 300)
    layout = QVBoxLayout(dialog)

    input_layout = QHBoxLayout()
    input_widget = QLineEdit()
    layout.addWidget(QLabel("Input Shapefile Path:"))
    input_layout.addWidget(input_widget)
    layout.addLayout(input_layout)
    
    progress_bar = QProgressBar(self)
    progress_bar.setValue(0)
    self.main_window.status_Bar.addPermanentWidget(progress_bar)
            
    def progress():
        for i in range(1, 101):
            time.sleep(0.02)
            progress_bar.setValue(i)
            QApplication.processEvents()
    
    def open_file_dialog():
        shapefile, _ = QFileDialog.getOpenFileName(self, "Select Shape File", "", "Shapefile Files (*.shp)")
        if shapefile:
            input_widget.setText(shapefile)
                    
    load_layer_button = QPushButton(dialog)
    load_layer_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_layer_button.setIconSize(QSize(25, 25))
    load_layer_button.clicked.connect(open_file_dialog)
    input_layout.addWidget(load_layer_button)

    output_layout = QHBoxLayout()
    output_input = QLineEdit()
    layout.addWidget(QLabel("Output GeoJSON Path:"))
    output_layout.addWidget(output_input)
    layout.addLayout(output_layout)

    def save_data():
        output_path, _ = QFileDialog.getSaveFileName(dialog, "Save GeoJSON File", "", "GeoJSON Files (*.geojson)")
        if output_path:
            output_input.setText(output_path)

    load_output_button = QPushButton(dialog)
    load_output_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_output_button.setIconSize(QSize(25, 25))
    load_output_button.clicked.connect(save_data)
    output_layout.addWidget(load_output_button)

    button_layout = QHBoxLayout()
    ok_button = QPushButton("Ok")
    cancel_button = QPushButton("Cancel")
    button_layout.addWidget(ok_button)
    button_layout.addWidget(cancel_button)
    layout.addLayout(button_layout)
    ok_button.clicked.connect(dialog.accept)
    cancel_button.clicked.connect(dialog.reject)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        output_path = output_input.text()
        input_path = input_widget.text()
        
        try:
            gdf = gpd.read_file(input_path)
            gdf.to_file(output_path, driver='GeoJSON')
            progress()
            self.main_window.status(f"{input_path} converted successfully", 2000)
            self.main_window.status(f"Loading {output_path}", 3000)
            self.main_window.create_layer(output_path)
        except Exception as e:
            self.main_window.status(f"Error: {e}", 10000)
        finally:
            self.main_window.status_Bar.removeWidget(progress_bar)

def netCDF_to_raster(self):
    dialog = QDialog()
    dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
    dialog.setWindowTitle("nc to Raster")
    dialog.resize(400, 300)
    layout = QVBoxLayout(dialog)

    input_layout = QHBoxLayout()
    input_widget = QLineEdit()
    layout.addWidget(QLabel("Input nc Path:"))
    input_layout.addWidget(input_widget)
    layout.addLayout(input_layout)

    list_layout = QHBoxLayout()
    variable_list = QListWidget(dialog)
    variable_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
    layout.addWidget(QLabel("Variables"))
    list_layout.addWidget(variable_list)
    layout.addLayout(list_layout)
    
    def open_file_dialog():
        nc_file, _ = QFileDialog.getOpenFileName(self, "Select nc File", "", "netCDF Files (*.nc)")
        if nc_file:
            input_widget.setText(nc_file)
            variable_list.clear()
            try:
                dataset = xr.open_dataset(nc_file)
                variables = list(dataset.variables.keys())
                for i, variable in enumerate(variables):
                    variable_list.addItem(variable)
            except Exception as e:
                self.main_window.status(f"Error Reading file: {e}", 10000)
                    
    load_layer_button = QPushButton(dialog)
    load_layer_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_layer_button.setIconSize(QSize(25, 25))
    load_layer_button.clicked.connect(open_file_dialog)
    input_layout.addWidget(load_layer_button)

    output_layout = QHBoxLayout()
    output_input = QLineEdit()
    layout.addWidget(QLabel("Output Raster Path:"))
    output_layout.addWidget(output_input)
    layout.addLayout(output_layout)

    def save_data():
        output_path, _ = QFileDialog.getSaveFileName(dialog, "Save Raster File", "", "Tiff Files (*.tif)")
        if output_path:
            output_input.setText(output_path)

    load_output_button = QPushButton(dialog)
    load_output_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_output_button.setIconSize(QSize(25, 25))
    load_output_button.clicked.connect(save_data)
    output_layout.addWidget(load_output_button)

    button_layout = QHBoxLayout()
    ok_button = QPushButton("Ok")
    cancel_button = QPushButton("Cancel")
    button_layout.addWidget(ok_button)
    button_layout.addWidget(cancel_button)
    layout.addLayout(button_layout)
    ok_button.clicked.connect(dialog.accept)
    cancel_button.clicked.connect(dialog.reject)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        output_path = output_input.text()
        input_path = input_widget.text()
        selected_variables = [variable_list.item(i).text() for i in range(variable_list.count()) if variable_list.item(i).isSelected()]
        
        progress_bar = QProgressBar(self)
        progress_bar.setValue(0)
        self.main_window.status_Bar.addPermanentWidget(progress_bar)
        progress_bar.setVisible(True)
        
        try:
            dataset = xr.open_dataset(input_path)
            progress_bar.setRange(0, len(selected_variables))
            for i, variable in enumerate(selected_variables):
                variable_data = dataset[variable]
                progress_bar.setValue(i + 1)
                variable_data = variable_data.rio.write_crs("EPSG:4326")
                variable_data.rio.to_raster(output_path)

            self.main_window.status(f"{input_path} converted successfully", 2000)
            self.main_window.status(f"Loading {output_path}", 3000)
            self.main_window.create_layer(output_path)
        except Exception as e:
            self.main_window.status(f"Error: {e}", 10000)
        finally:
            self.main_window.status_Bar.removeWidget(progress_bar)

def netCDF_to_csv(self):
    dialog = QDialog()
    dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
    dialog.setWindowTitle("nc to CSV")
    dialog.resize(400, 300)
    layout = QVBoxLayout(dialog)

    input_layout = QHBoxLayout()
    input_widget = QLineEdit()
    layout.addWidget(QLabel("Input nc Path:"))
    input_layout.addWidget(input_widget)
    layout.addLayout(input_layout)

    list_layout = QHBoxLayout()
    variable_list = QListWidget(dialog)
    variable_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
    layout.addWidget(QLabel("Variables"))
    list_layout.addWidget(variable_list)
    layout.addLayout(list_layout)
    
    def open_file_dialog():
        nc_file, _ = QFileDialog.getOpenFileName(self, "Select nc File", "", "netCDF Files (*.nc)")
        if nc_file:
            input_widget.setText(nc_file)
            variable_list.clear()
            try:
                dataset = nc.Dataset(nc_file)
                variables = list(dataset.variables.keys())
                for i, variable in enumerate(variables):
                    variable_list.addItem(variable)
            except Exception as e:
                self.main_window.status(f"Error Reading file: {e}", 10000)
                    
    load_layer_button = QPushButton(dialog)
    load_layer_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_layer_button.setIconSize(QSize(25, 25))
    load_layer_button.clicked.connect(open_file_dialog)
    input_layout.addWidget(load_layer_button)

    output_layout = QHBoxLayout()
    output_input = QLineEdit()
    layout.addWidget(QLabel("Output CSV Path:"))
    output_layout.addWidget(output_input)
    layout.addLayout(output_layout)

    def save_data():
        output_path, _ = QFileDialog.getSaveFileName(dialog, "Save CSV File", "", "Comma Seperated Value Files (*.csv)")
        if output_path:
            output_input.setText(output_path)

    load_output_button = QPushButton(dialog)
    load_output_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_output_button.setIconSize(QSize(25, 25))
    load_output_button.clicked.connect(save_data)
    output_layout.addWidget(load_output_button)

    button_layout = QHBoxLayout()
    ok_button = QPushButton("Ok")
    cancel_button = QPushButton("Cancel")
    button_layout.addWidget(ok_button)
    button_layout.addWidget(cancel_button)
    layout.addLayout(button_layout)
    ok_button.clicked.connect(dialog.accept)
    cancel_button.clicked.connect(dialog.reject)
        
    if dialog.exec() == QDialog.DialogCode.Accepted:
        output_path = output_input.text()
        input_path = input_widget.text()
        selected_variables = [variable_list.item(i).text() 
                                for i in range(variable_list.count()) 
                                if variable_list.item(i).isSelected()]
        
        progress_bar = QProgressBar(self)
        progress_bar.setValue(0)
        self.main_window.status_Bar.addPermanentWidget(progress_bar)
        progress_bar.setVisible(True)
        
        try:
            df = nc.Dataset(input_path)
            
            total_steps = sum(
                len(nc.num2date(df.variables[df.variables[var].get_dims()[0].name][:], df.variables[df.variables[var].get_dims()[0].name].units))
                for var in selected_variables
            )
            current_progress = 0
            progress_bar.setRange(0, total_steps)
            for i, variable in enumerate(selected_variables):
                variable_data = df.variables[variable]
                
                time_dim, lat_dim, lon_dim = variable_data.get_dims()
                time_var = df.variables[time_dim.name]
                times = nc.num2date(time_var[:], time_var.units)
                latitudes = df.variables[lat_dim.name][:]
                longitudes = df.variables[lon_dim.name][:]
                
                for _ in range(len(times)):
                    current_progress += 1
                    progress_bar.setValue(current_progress)
                
                filename = os.path.join(output_path)
                self.main_window.status(f"Writing data in tabular form to {filename}...", 9000)
                times_grid, latitudes_grid, longitudes_grid = [
                    x.flatten() for x in np.meshgrid(times, latitudes, longitudes, indexing="ij")
                ]
                df = pd.DataFrame(
                    {
                        "time": [t.isoformat() for t in times_grid],
                        "latitude": latitudes_grid,
                        "longitude": longitudes_grid,
                        "t2m": variable_data[:].flatten(),
                    }
                )
                df.to_csv(filename, index=False)
                self.main_window.status(f"Conversion Completed.", 9000)
        except Exception as e:
            self.main_window.status(f"Error: {e}", 5000)
        finally:
            progress_bar.setVisible(False)
            self.main_window.status_Bar.removeWidget(progress_bar)

def netcdf_to_shp(self):
    dialog = QDialog()
    dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
    dialog.setWindowTitle("nc to shp")
    dialog.resize(400, 300)
    layout = QVBoxLayout(dialog)

    input_layout = QHBoxLayout()
    input_widget = QLineEdit()
    layout.addWidget(QLabel("Input nc Path:"))
    input_layout.addWidget(input_widget)
    layout.addLayout(input_layout)

    list_layout = QHBoxLayout()
    variable_list = QListWidget(dialog)
    variable_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
    layout.addWidget(QLabel("Variables"))
    list_layout.addWidget(variable_list)
    layout.addLayout(list_layout)
    
    def open_file_dialog():
        nc_file, _ = QFileDialog.getOpenFileName(self, "Select nc File", "", "netCDF Files (*.nc)")
        if nc_file:
            input_widget.setText(nc_file)
            variable_list.clear()
            try:
                dataset = xr.open_dataset(nc_file)
                variables = list(dataset.variables.keys())
                for i, variable in enumerate(variables):
                    variable_list.addItem(variable)
            except Exception as e:
                self.main_window.status(f"Error Reading file: {e}", 10000)
                    
    load_layer_button = QPushButton(dialog)
    load_layer_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_layer_button.setIconSize(QSize(25, 25))
    load_layer_button.clicked.connect(open_file_dialog)
    input_layout.addWidget(load_layer_button)

    output_layout = QHBoxLayout()
    output_input = QLineEdit()
    layout.addWidget(QLabel("Output Shapefile Path:"))
    output_layout.addWidget(output_input)
    layout.addLayout(output_layout)

    def save_data():
        output_path, _ = QFileDialog.getSaveFileName(dialog, "Save Shapefile", "", "Shapefile (*.shp)")
        if output_path:
            output_input.setText(output_path)

    load_output_button = QPushButton(dialog)
    load_output_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_output_button.setIconSize(QSize(25, 25))
    load_output_button.clicked.connect(save_data)
    output_layout.addWidget(load_output_button)

    button_layout = QHBoxLayout()
    ok_button = QPushButton("Ok")
    cancel_button = QPushButton("Cancel")
    button_layout.addWidget(ok_button)
    button_layout.addWidget(cancel_button)
    layout.addLayout(button_layout)
    ok_button.clicked.connect(dialog.accept)
    cancel_button.clicked.connect(dialog.reject)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        output_path = output_input.text()
        input_path = input_widget.text()
        selected_variables = [variable_list.item(i).text() for i in range(variable_list.count()) if variable_list.item(i).isSelected()]
        
        try:
            df = nc.Dataset(input_path)
            for i, variable in enumerate(selected_variables):
                variable_data = df.variables[variable][0, :, :]
                latitudes = df.variables["lat"][:]
                longitudes = df.variables["lon"][:]

                lat_grid, lon_grid = np.meshgrid(latitudes, longitudes, indexing='ij')
                flat_lats = lat_grid.flatten()
                flat_lons = lon_grid.flatten()
                flat_values = variable_data.flatten()

                data = pd.DataFrame({
                    'latitude': flat_lats,
                    'longitude': flat_lons,
                    'air': flat_values
                })

                data = data.dropna(subset=[variable])
                data['geometry'] = data.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)

                gdf = gpd.GeoDataFrame(data, geometry='geometry', crs="EPSG:4326")
                gdf.to_file(output_path, driver='ESRI Shapefile')
        except Exception as e:
            self.main_window.status(f"{e}", 50000)
