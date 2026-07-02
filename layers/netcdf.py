# NetCDF layer
import os
import netCDF4 as nc

class NetCDF:
    def __init__(self, file_name):
        self.file_path = file_name
        self.layer = None

    def __str__(self):
        return os.path.basename(self.file_path)
    
    def add_to_map(self, folium_map):
        ncdf = nc.Dataset(self.file_path, mode='r')

        ncdf.close()

    def remove_from_map(self, folium_map):
        if self.layer:
            folium_map._children.pop(self.layer._name, None)
            self.layer = None