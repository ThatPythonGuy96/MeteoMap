# TIFFLayer, ColoredTIFFLayer
import os
import rasterio
import matplotlib
import numpy as np
from folium.raster_layers import ImageOverlay

class ColoredTIFFLayer:
    def __init__(self, file_name):
        self.file_path = file_name
        self.layer = None

    def __str__(self):
        return os.path.basename(self.file_path)
    
    def add_to_map(self, folium_map):
        with rasterio.open(self.file_path) as src:
            raster_data = src.read(1)
            bounds = [[src.bounds.bottom, src.bounds.left], [src.bounds.top, src.bounds.right]]

            num_bins = 9
            bin_edges = np.linspace(raster_data.min(), raster_data.max(), num_bins + 1)
            discrete_data = np.digitize(raster_data, bin_edges)

            colors = ['#eaf8d3', '#d4eab0', '#bede8c', '#a8d169', '#92c546', '#7cb935', '#66a92d','#508a25','#3a6b1e','#245014']
            cmap = matplotlib.colors.ListedColormap(colors)
            colored_raster = cmap(discrete_data / num_bins)
            
            self.layer = ImageOverlay(
                image=colored_raster[:, :, :3],
                bounds=bounds,
                opacity=0.7,
                interactive=True,
            )
            self.layer.add_to(folium_map)
            folium_map.fit_bounds(bounds)
            return self.layer

    def remove_from_map(self, folium_map):
        if self.layer:
            folium_map._children.pop(self.layer._name, None)
            self.layer = None
    
class TIFFLayer:
    def __init__(self, file_name):
        self.file_path = file_name
        self.layer = None

    def __str__(self):
        return os.path.basename(self.file_path)

    def add_to_map(self, folium_map):
        with rasterio.open(self.file_path) as src:
            bounds = [[src.bounds.bottom, src.bounds.left], [src.bounds.top, src.bounds.right]]
            self.layer = ImageOverlay(
                image=src.read(1),
                bounds=bounds,
                opacity=0.6,
                name=os.path.basename(self.file_path),
                interactive=True,
                cross_origin=True,
                overlay=True
            )
            self.layer.add_to(folium_map)
            folium_map.fit_bounds(bounds)
            return self.layer
        
    def remove_from_map(self, folium_map):
        if self.layer:
            folium_map._children.pop(self.layer._name, None)
            self.layer = None