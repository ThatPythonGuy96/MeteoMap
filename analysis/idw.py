# IDW interpolation
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QPushButton, QFileDialog, QLabel, QHBoxLayout, QListWidget
from PyQt6.QtWidgets import QDialog, QPushButton, QComboBox, QProgressBar, QLineEdit
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
import geopandas as gpd
import numpy as np
import io, os, time
import rasterio
from rasterio.transform import from_origin
from folium.raster_layers import ImageOverlay
import matplotlib
import matplotlib.colors as mcolors
from utils.paths import resource_path
from utils.logger import setup_logger

logger = setup_logger()

def IDW(self):
    dialog = QDialog()
    dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
    dialog.setWindowTitle("IDW")
    dialog.resize(500, 300)

    layout = QVBoxLayout(dialog)
    list_layout = QHBoxLayout()
    variable_list = QListWidget(dialog)
    list_layout.addWidget(variable_list)
    layout.addLayout(list_layout)

    input_layout = QHBoxLayout()
    input_widget = QLineEdit()
    layout.addWidget(QLabel("Input Shapefile Path:"))
    input_layout.addWidget(input_widget)
    layout.addLayout(input_layout)

    def open_file_dialog():
        layer_path, _ = QFileDialog.getOpenFileName(dialog, "Select Shapefile", "", "Shapefiles (*.shp)")
        if layer_path:
            input_widget.setText(layer_path)
            populate_attribute_combo()

    load_layer_button = QPushButton(dialog)
    load_layer_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_layer_button.setIconSize(QSize(25, 25))
    load_layer_button.clicked.connect(open_file_dialog)
    list_layout.addWidget(load_layer_button)
    
    attribute_combo = QComboBox()
    layout.addWidget(QLabel("Attribute Field:"))
    layout.addWidget(attribute_combo)

    def populate_attribute_combo():
        selected_item = variable_list.currentItem()
        if selected_item:
            layer = selected_item.data(0)
            if layer and hasattr(layer, 'file_path'):
                file_path = layer.file_path
                try:
                    gdf = gpd.read_file(file_path)
                    attributes = gdf.columns.tolist()
                    attribute_combo.clear()
                    attribute_combo.addItems(attributes)
                except Exception as e:
                    logger.error(f"IDW: Error loading shapefile: {e}")
                    self.main_window.status(f"Error loading shapefile: {e}", 10000)
            else:
                logger.error("IDW: Invalid layer or missing file_path")
                self.main_window.status("Invalid layer or missing file_path", 10000)

    output_layout = QHBoxLayout()
    output_input = QLineEdit()
    layout.addWidget(QLabel("Output Raster Path:"))
    output_layout.addWidget(output_input)
    layout.addLayout(output_layout)

    def save_data():
        output_path, _ = QFileDialog.getSaveFileName(dialog, "Save Output Raster", "", "GeoTIFF (*.tif)")
        if output_path:
            output_input.setText(output_path)

    load_output_button = QPushButton(dialog)
    load_output_button.setIcon(QIcon(resource_path('icons/folder.png')))
    load_output_button.setIconSize(QSize(25, 25))
    load_output_button.clicked.connect(save_data)
    output_layout.addWidget(load_output_button)

    resolution_input = QLineEdit()
    resolution_input.setText("0.006")  # Default resolution
    layout.addWidget(QLabel("Resolution:"))
    layout.addWidget(resolution_input)

    power_input = QLineEdit()
    power_input.setText("2")  # Default power
    layout.addWidget(QLabel("Power:"))
    layout.addWidget(power_input)

    button_layout = QHBoxLayout()
    ok_button = QPushButton("Ok")
    cancel_button = QPushButton("Cancel")
    button_layout.addWidget(ok_button)
    button_layout.addWidget(cancel_button)
    layout.addLayout(button_layout)
    ok_button.clicked.connect(dialog.accept)
    cancel_button.clicked.connect(dialog.reject)

    def inverse_distance_weighting(x, y, z, xi, yi, power=2):
        interpolated_values = np.zeros_like(xi, dtype=float)
        for i in range(len(xi)):
            distances = np.sqrt((x - xi[i])**2 + (y - yi[i])**2)
            with np.errstate(divide='ignore'):
                weights = 1 / (distances**power)
            zero_dist_mask = distances == 0
            if np.any(zero_dist_mask):
                interpolated_values[i] = z[zero_dist_mask][0]
            else:
                interpolated_values[i] = np.sum(weights * z) / np.sum(weights)
        return interpolated_values
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        selected_item = variable_list.currentItem()
        if selected_item:
            layer = selected_item.data(0)
            if layer:
                input = layer.file_path
                power = float(power_input.text()) if power_input.text().replace('.', '', 1).isdigit() else 2.0
                resolution = float(resolution_input.text()) if resolution_input.text().replace('.', '', 1).isdigit() else None
                attribute = attribute_combo.currentText()
                output_path = output_input.text()
                if not (attribute and output_path and resolution):
                    logger.error("IDW: Missing required fields")
                    self.status("Error: Please fill in all required fields.", 10000)
                    return

                output_file_path = os.path.basename(output_path)
                
                progress_bar = QProgressBar(self)
                progress_bar.setValue(0)
                self.status_Bar.addPermanentWidget(progress_bar)
                
                def progress():
                    for i in range(1, 101):
                        time.sleep(0.02)
                        progress_bar.setValue(i)
                        QApplication.processEvents()
                            
                def idw_interpolation_on_shapefile(input, attribute, output_file_path, resolution, power: float = 2.0):
                    gdf = gpd.read_file(input)
                    x = gdf.geometry.x
                    y = gdf.geometry.y
                    z = gdf[attribute]

                    xmin, ymin, xmax, ymax = gdf.total_bounds
                    xi = np.arange(xmin, xmax, resolution)
                    yi = np.arange(ymin, ymax, resolution)
                    x_grid, y_grid = np.meshgrid(xi, yi)

                    x_flat = x_grid.ravel()
                    y_flat = y_grid.ravel()

                    interpolated_values = inverse_distance_weighting(
                        np.array(x), np.array(y), np.array(z), x_flat, y_flat, power=power
                    )

                    interpolated_grid = interpolated_values.reshape(x_grid.shape)

                    transform = from_origin(xmin, ymax, resolution, resolution)
                    with rasterio.open(
                        output_file_path,
                        "w",
                        driver="GTiff",
                        height=interpolated_grid.shape[0],
                        width=interpolated_grid.shape[1],
                        count=1,
                        dtype="float32",
                        crs=gdf.crs,
                        transform=transform,
                    ) as dst:
                        dst.write(interpolated_grid, 1)

                try:
                    idw_interpolation_on_shapefile(input, attribute, output_file_path, resolution, power)
                    progress()
                    
                    logger.info("IDW Interpolation completed successfully.")
                    self.main_window.status("IDW Interpolation completed successfully.", 10000)

                    with rasterio.open(output_path) as src:
                        raster_data = src.read(1)
                        bounds = [[src.bounds.bottom, src.bounds.left], [src.bounds.top, src.bounds.right]]

                        num_bins = 9
                        bin_edges = np.linspace(raster_data.min(), raster_data.max(), num_bins + 1)
                        discrete_data = np.digitize(raster_data, bin_edges)

                        colors = ['#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#005a32']
                        cmap = mcolors.ListedColormap(colors)
                        colored_raster = cmap(discrete_data / num_bins)

                        layer = ImageOverlay(
                            image=colored_raster[:, :, :3],
                            bounds=bounds,
                            opacity=0.7,
                            interactive=True,
                        )

                        layer.add_to(self.main_window.m)
                        self.main_window.add_layer_checkbox(layer, output_file_path)
                        self.main_window.layers.append(layer)
                        data = io.BytesIO()
                        self.main_window.m.save(data, close_file=False)
                        self.main_window.web_view.setHtml(data.getvalue().decode())
                except Exception as e:
                    logger.error(f"IDW: Error during interpolation: {e}")
                    self.main_window.status(f"Error during IDW: {e}", 10000)
