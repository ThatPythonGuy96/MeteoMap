# ShapefileLayer, GeoJSONLayer, CircleMarker
import json, random, os 
import geopandas as gpd
import folium

class ShapefileLayer:
    def __init__(self, file_name):
        self.file_path = file_name
        self.layer = None
        self.color_list = ['blue', 'green', 'red', 'purple', 'orange', 'yellow', 'brown']

    def __str__(self):
        return os.path.basename(self.file_path)

    def add_to_map(self, folium_map):
        geodata = gpd.read_file(self.file_path)
        file_name = os.path.basename(self.file_path)
        self.layer = folium.GeoJson(
            geodata,
            name=file_name,
            style_function=lambda feature: {
                'fillColor': random.choice(self.color_list),
                'color': random.choice(self.color_list),
                'weight': 2,
                'fillOpacity': 0.5
            }
        )
        self.layer.add_to(folium_map)
        bounds = geodata.total_bounds  # [minx, miny, maxx, maxy]
        folium_map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        return self.layer
    
    def remove_from_map(self, folium_map):
        if self.layer:
            folium_map._children.pop(self.layer._name, None)
            self.layer = None

class GeoJSONLayer:
    def __init__(self, file_name):
        self.file_path = file_name
        self.layer = None
        self.color_list = ['blue', 'green', 'red', 'purple', 'orange', 'yellow', 'brown']

    def __str__(self):
        return os.path.basename(self.file_path)

    def add_to_map(self, folium_map):
        with open(self.file_path) as f:
            geojson_data = json.load(f)
        self.layer = folium.GeoJson(
            geojson_data,
            name=os.path.basename(self.file_path),
            style_function=lambda feature: {
                'fillColor': random.choice(self.color_list),
                'color': random.choice(self.color_list),
                'weight': 2,
                'fillOpacity': 0.6
            }
        )
        self.layer.add_to(folium_map)
        bounds = self.layer.get_bounds()
        folium_map.fit_bounds(bounds)
        return self.layer

    def remove_from_map(self, folium_map):
        if self.layer:
            folium_map._children.pop(self.layer._name, None)
            self.layer = None

class CircleMarker:
    def __init__(self, file_name):
        self.file_path = file_name
        self.layer = []
        self.color_list = ['blue', 'green', 'red', 'purple', 'orange', 'yellow', 'brown']
        self.color = random.choice(self.color_list)
    
    def __str__(self):
        return os.path.basename(self.file_path)
    
    def add_to_map(self, folium_map):
        geodata = gpd.read_file(self.file_path)
        for _, row in geodata.iterrows():
            marker  = folium.CircleMarker(
                location=(row.geometry.y, row.geometry.x),
                radius=2,
                color= self.color,
                fill=True,
                fill_opacity=0.5,
                popup=str(row.iloc[2])
            )
            marker.add_to(folium_map)
            self.layer.append(marker)
        return self.layer
    
    def remove_from_map(self, folium_map):
        for marker in self.layer:
            if marker._name in folium_map._children:
                folium_map._children.pop(marker._name, None)
        self.layer = []