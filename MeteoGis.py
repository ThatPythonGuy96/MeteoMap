from pathlib import Path
import json, io, tempfile, random, os, sys, time
import pandas as pd
from scipy import stats as st
import matplotlib, rioxarray
from shapely.geometry import Point, mapping
import matplotlib.dates as mdates
import numpy as np
import geopandas as gpd
import rasterio, folium
import netCDF4 as nc
from rasterio.transform import from_origin
from folium.plugins import Draw, MousePosition
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QWidget, QFileDialog, QLabel, QHBoxLayout, QCheckBox, QListWidget,QListWidgetItem, QTableView
from PyQt6.QtWidgets import QToolBar, QDialog, QPushButton, QComboBox, QProgressBar, QTreeWidget, QTreeWidgetItem, QSplashScreen, QLineEdit, QStatusBar, QTabWidget, QSplitter, QTextEdit
from PyQt6.QtWebEngineWidgets import QWebEngineView 
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtCore import QSize, Qt, QAbstractTableModel
from folium.raster_layers import ImageOverlay
from rasterio.mask import mask
import xarray as xr
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import openmeteo_requests, requests_cache
from retry_requests import retry
from utils.paths import resource_path

cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

os.environ["QT_OPENGL"] = "software"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QTWEBENGINE_DISABLE_GPU"] = "0"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

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

class TableModel(QAbstractTableModel):

    def __init__(self, data):
        super().__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            return str(value)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])

            if orientation == Qt.Orientation.Vertical:
                return str(self._data.index[section])
            
class BasemapDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Basemap")
        self.setFixedSize(200, 100)
        layout = QVBoxLayout()
        label = QLabel("Select a basemap:")
        layout.addWidget(label)
        
        self.basemap_combo = QComboBox()

        basemaps = [
            'OpenStreetMap', 
            'Stadia StamenToner', 
            'Stadia StamenWaterColor', 
            'CartoDB positron', 
            'CartoDB dark_matter'
        ]
        self.basemap_combo.addItems(basemaps)
        layout.addWidget(self.basemap_combo)

        ok_button = QPushButton("Add")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)

        self.setLayout(layout)

    def get_selected_basemap(self):
        return self.basemap_combo.currentText()
            
class GISApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MeteoMap")
        self.setWindowIcon(QIcon(resource_path(("meteomap.ico"))
)        self.setGeometry(100, 100, 1000, 900)
        
        self.toolbox = ToolDialog(self)
        self.setStyleSheet("""
            QProgressBar {
                height: 7px;
            }
            QWebEngineView {
                border-color: "black";
            }
            QSplashScreen {
                background-color: "white";               
            }
        """)

        self.tab = QTabWidget(self)
        self.setCentralWidget(self.tab)
        self.layers = []
        self.m = folium.Map(location=[0, 0], tiles=None, control_scale=True, zoom_start=4)
        MousePosition().add_to(self.m)

        self.geodata = None

        self.menu_bar()
        self.toolbar1()
        self.toolbar2()
        self.toolbar3()
        self.toolbar4()
        
        self.status_Bar = QStatusBar()
        self.setStatusBar(self.status_Bar)
        self.map_tab()
        self.graph_tab()
    
    def status(self, message, timeout=0):
        self.status_Bar.showMessage(message, timeout)

    def menu_bar(self):
        menubar = self.menuBar()
        # Create a menu
        file_menu = menubar.addMenu('File')
        edit_menu = menubar.addMenu('Edit')
        view_menu = menubar.addMenu('View')
        help_menu = menubar.addMenu('Help')
        geop_menu = menubar.addMenu('GeoProcessing')
        insert_menu = menubar.addMenu('Insert')
        help_menu = menubar.addMenu('Help')

        # Create file actions using QAction
        new_action = QAction(QIcon(resource_path(resource_path("ico)ns/new.png")), 'New File', self)
        new_action.setShortcut('Ctrl+N') 
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        load_action = QAction('Load Data', self)
        load_action.setShortcut('Ctrl+L')
        load_action.triggered.connect(self.load_data)
        file_menu.addAction(load_action)
        
        save_action = QAction(QIcon(resource_path(resource_path("ico)ns/save.png")), 'Save', self)
        save_action.setShortcut('Ctrl+S') 
        save_action.triggered.connect(self.save_data)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()

        quit_action = QAction('Quit', self)
        quit_action.setShortcut('Alt+F4')
        quit_action.triggered.connect(self.close) 
        file_menu.addAction(quit_action)

        # Create view actions using QAction
        table_action = QAction('Attribute Table', self)
        table_action.triggered.connect(self.attribute_table)
        view_menu.addAction(table_action)

        # Create edit actions using QAction
        undo_action = QAction(QIcon(resource_path('icons/undo.png'),) '&Undo', self)
        undo_action.setStatusTip('Undo')
        undo_action.setShortcut('Ctrl+Z')
        edit_menu.addAction(undo_action)

        redo_action = QAction(QIcon(resource_path('icons/redo.png'),) '&Redo', self)
        redo_action.setStatusTip('Redo')
        redo_action.setShortcut('Ctrl+Y')
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        copy_action = QAction(QIcon(resource_path('icons/copy.png'),) '&Copy', self)
        edit_menu.addAction(copy_action)
        copy_action.setShortcut('Ctrl+C')
        
        cut_action = QAction(QIcon(resource_path('icons/cut.png'), )'&Cut', self)
        edit_menu.addAction(cut_action)
        cut_action.setShortcut('Ctrl+X')
        
        paste_action = QAction(QIcon(resource_path('icons/paste.png')), '&Paste', self)
        edit_menu.addAction(paste_action)
        paste_action.setShortcut('Ctrl+Y')
        
        edit_menu.addSeparator()
        
        # Create Geop actions using QAction
        buffer = QAction(QIcon(resource_path('icons/buffer.png')), 'Buffer', self)
        buffer.triggered.connect(self.toolbox.buffer_data)
        geop_menu.addAction(buffer)

        clip = QAction('Clip', self)
        clip.triggered.connect(self.toolbox.clip)
        geop_menu.addAction(clip)

        union = QAction('Union', self)
        union.triggered.connect(self.toolbox.union)
        geop_menu.addAction(union)

        geop_menu.addSeparator()

        toolbox = QAction(QIcon(resource_path('icons/toolbox.png)'), 'ToolBox', self)
        toolbox.triggered.connect(self.toolbox_dialog)
        geop_menu.addAction(toolbox)

        geop_menu.addSeparator()

        python = QAction(QIcon(resource_path('icons/python.png')), 'Python', self)
        python.triggered.connect(self.open_python_interpreter)
        geop_menu.addAction(python)
        
        # Create insert actions using QAction
        basemap_action = QAction('Add Basemap', self)
        basemap_action.triggered.connect(self.open_basemap_dialog)
        insert_menu.addAction(basemap_action)

        # Create help actions using QAction
        help = QAction('Help', self)
        help_menu.addAction(help)

        help_menu.addSeparator()

        about = QAction('About MeteoMap', self)
        help_menu.addAction(about)

    def map_tab(self):
        map_tab = QWidget()
        self.main_layout = QHBoxLayout()

        self.layer_variable_list = QListWidget()
        self.layer_list_label = QLabel("Layers")
        self.layer_list = QVBoxLayout()
        self.layer_list.addWidget(self.layer_list_label)
        self.layer_list.addWidget(self.layer_variable_list)
        self.layer_list.addStretch()
        self.left_widget = QWidget()
        self.left_widget.setLayout(self.layer_list)
        self.layer_variable_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid gray;
                padding: 0px;
            }
            QCheckBox {
                padding-left: 16px; /* Add left padding to checkboxes */
            }
            """
        )

        self.web_view_widget = QWidget()
        self.web_view = QWebEngineView(self.web_view_widget)

        self.table = QTableView()

        self.right_list = QVBoxLayout()
        self.right_list.addWidget(self.table)
        self.right_variable_list = QWidget()
        self.right_variable_list.setLayout(self.right_list)

        self.splitter = QSplitter()
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.web_view)
        self.splitter.addWidget(self.right_variable_list)

        self.splitter.setSizes([100, 800, 200])

        self.main_layout.addWidget(self.splitter)

        map_tab.setLayout(self.main_layout)
        self.tab.addTab(map_tab, 'Map View')
    
    def graph_tab(self):
        self.graph_tab = QWidget()
        self.layout = QVBoxLayout(self.graph_tab)

        self.top_section = QWidget()
        self.layout.addWidget(self.top_section)
        self.top_layout = QVBoxLayout(self.top_section)

        location = QHBoxLayout()
        location.addWidget(QLabel("Latitude"))
        self.latitude_input = QLineEdit("10")
        location.addWidget(self.latitude_input)

        location.addWidget(QLabel("Longitude"))
        self.longitude_input = QLineEdit("8")
        location.addWidget(self.longitude_input)

        self.top_layout.addLayout(location)

        date = QHBoxLayout()
        date.addWidget(QLabel("Enter Start Date:"))
        self.start_input_field = QLineEdit("2026-01-01")
        date.addWidget(self.start_input_field)

        date.addWidget(QLabel("Enter End Date:"))
        self.end_input_field = QLineEdit("2026-05-31")
        date.addWidget(self.end_input_field)

        self.top_layout.addLayout(date)

        self.variables = {
            "temperature_2m_max": QCheckBox("Max Temperature"),
            "temperature_2m_min": QCheckBox("Min Temperature"),
            "temperature_2m_mean": QCheckBox("Mean Temperature"),
            "precipitation_sum": QCheckBox("Precipitation Sum"),
            "et0_fao_evapotranspiration": QCheckBox("Evapotranspiration"),
        }

        variables_layout = QHBoxLayout()
        variables_layout.addWidget(QLabel("Select Variables to Plot:"))
        for var, checkbox in self.variables.items():
            variables_layout.addWidget(checkbox)
            checkbox.setChecked(True)

        self.top_layout.addLayout(variables_layout)

        buttons = QHBoxLayout()
        self.update_button = QPushButton("Update Graph")
        self.update_button.setFixedSize(QSize(1200, 30))
        self.update_button.clicked.connect(self.plot_graph)
        buttons.addWidget(self.update_button)
        self.top_layout.addLayout(buttons)
        
        self.save_button = QPushButton()
        self.save_button.setIcon(QIcon(resource_path("icons/save.png")))
        self.save_button.setEnabled(False)
        self.save_button.setIconSize(QSize(20, 20))
        buttons.addWidget(self.save_button)

        self.top_section.setFixedHeight(130)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas, stretch=1) # Graph
        
        self.tab.addTab(self.graph_tab, 'Plot')
        self.plot_graph()
       
    def toolbar1(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.setIconSize(QSize(15, 15))

        new_button = QAction(QIcon(resource_path("icons/new.png"), )"New File", self)
        toolbar.addAction(new_button)
        
        toolbar.addSeparator()
        
        paste_button = QAction(QIcon(resource_path("icons/paste.png")), "Paste", self)
        toolbar.addAction(paste_button)

        copy_button = QAction(QIcon(resource_path("icons/copy.png"),) "Copy", self)
        toolbar.addAction(copy_button)

        cut_button = QAction(QIcon(resource_path("icons/cut.png"), )"Cut", self)
        toolbar.addAction(cut_button)

    def toolbar2(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.setIconSize(QSize(15, 15))

        draw_button = QAction(QIcon(resource_path("icons/polygon.png)"), "Draw", self)
        draw_button.triggered.connect(self.draw_polygon)
        toolbar.addAction(draw_button)

        basemap_button = QAction(QIcon(resource_path("icons/basemap.png)"), "BaseMap", self)
        basemap_button.triggered.connect(self.open_basemap_dialog)
        toolbar.addAction(basemap_button)

        add_button = QAction(QIcon(resource_path("icons/plus.png"),) "Add Data", self)
        add_button.triggered.connect(self.load_data)
        toolbar.addAction(add_button)
    
    def toolbar3(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.setIconSize(QSize(15, 15))

        toolbox_button = QAction(QIcon(resource_path("icons/toolbox.png)"), "ToolBox", self)
        toolbox_button.triggered.connect(self.toolbox_dialog)
        toolbar.addAction(toolbox_button)

        interpreter_button = QAction(QIcon(resource_path("icons/python.png")), "Python Interpreter", self)
        interpreter_button.triggered.connect(self.open_python_interpreter)
        toolbar.addAction(interpreter_button)

    def toolbar4(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.setIconSize(QSize(15, 15))
        
        zoomin_button = QAction(QIcon(resource_path("icons/zoom-in.png)"), "Zoom In", self)
        toolbar.addAction(zoomin_button)

        zoomout_button = QAction(QIcon(resource_path("icons/zoom-out.pn)g"), "Zoom Out", self)
        toolbar.addAction(zoomout_button)
        toolbar.addSeparator()

    def toolbox_dialog(self):
        dialog = ToolDialog(main_window=self)
        dialog.exec()

    def open_python_interpreter(self):
        self.python_interpreter = PythonInterpreter()
        self.python_interpreter.show()
        
    def save_data(self):
        output_path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "Shapefile (*.shp)")
        if output_path:
            pass
    
    def open_basemap_dialog(self):
        dialog = BasemapDialog(self)
        if dialog.exec():
            selected_basemap = dialog.get_selected_basemap()
            self.add_basemap(selected_basemap)

    def add_basemap(self, basemap_name):
        basemap_dict = {
            'OpenStreetMap': 'openstreetmap',
            'Stadia StamenToner': 'stadiastamentoner',
            'Stadia StamenWaterColor': 'stadiastamenwatercolor',
            'CartoDB positron': 'cartodbpositron',
            'CartoDB dark_matter': 'cartodbdark_matter',
        }
        progress_bar = QProgressBar(self)
        progress_bar.setValue(0)
        self.status_Bar.addPermanentWidget(progress_bar)

        def progress():
            for i in range(1, 101):
                time.sleep(0.02)
                progress_bar.setValue(i)
                QApplication.processEvents()
        try:
            if basemap_name in basemap_dict:
                tile_layer_name = basemap_dict[basemap_name]
                basemap_layer = folium.TileLayer(tiles=tile_layer_name, name=basemap_name)
                progress()
                basemap_layer.add_to(self.m)

                self.add_layer_checkbox(basemap_layer, basemap_name)
                self.layers.append(basemap_name)
                
                data = io.BytesIO()
                self.m.save(data, close_file=False)
                self.web_view.setHtml(data.getvalue().decode())
            else:
                self.status(f"Basemap {basemap_name} is not recognized.", 10000)
        except Exception as e:
            self.status(f"Error: {e}", 10000)
        finally:
            self.status_Bar.removeWidget(progress_bar)

    def load_data(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load GeoData", "", "DataSets, Layers (*.tif *.tiff *.shp *.geojson)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if file_path:
            self.create_layer(file_path)

    def update_webview(self):
        data = io.BytesIO()
        self.m.save(data, close_file=False)
        self.web_view.setHtml(data.getvalue().decode('utf-8'))

    def create_layer(self, file_path):
        file_name = os.path.basename(file_path)
        file_extension = os.path.splitext(file_path)[1]
        self.status(f"Loading {file_name}", 5000)
        progress_bar = QProgressBar(self)
        progress_bar.setValue(0)
        self.status_Bar.addPermanentWidget(progress_bar)
        
        def progress():
            for i in range(1, 101):
                time.sleep(0.02)
                progress_bar.setValue(i)
                QApplication.processEvents()
        try:
            if file_extension in (".tif", ".tiff"):
                layer = TIFFLayer(file_path)
                progress()
            elif file_extension == ".shp":
                geodata = gpd.read_file(file_path)
                if geodata.geometry.iloc[0].geom_type == 'Point':
                    layer = CircleMarker(file_path)
                else:
                    layer = ShapefileLayer(file_path)
                progress()
            elif file_extension == ".geojson":
                layer = GeoJSONLayer(file_path)
                progress()
    
            layer.add_to_map(self.m)
            self.add_layer_checkbox(layer, file_name)
            self.layers.append(layer)
            data = io.BytesIO()
            self.m.save(data, close_file=False)
            self.web_view.setHtml(data.getvalue().decode())
            self.status(f"{file_name} loaded successfully", 5000)
        except Exception as e:
            self.status(f"Error creating layer: {e}", 10000)
            print(e)
        finally:
            self.status_Bar.removeWidget(progress_bar)

    def add_layer_checkbox(self, layer, file_name):
        item = QListWidgetItem(self.layer_variable_list)
        checkbox = QCheckBox(str(layer))
        checkbox.setCheckState(Qt.CheckState.Checked)
        self.layer_variable_list.setItemWidget(item, checkbox)
        checkbox.stateChanged.connect(lambda state, layer=layer: self.toggle_layer(state, layer))

    def toggle_layer(self, state, layer):
        if state == 2:
            layer.add_to_map(self.m)
        else:
            layer.remove_from_map(self.m)
        self.update_webview()

    def attribute_table(self, file_path):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Csv", "", "CSV Files (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if file_path:
            try:
                csv_data = pd.read_csv(file_path).head(20)
                data = pd.DataFrame(csv_data)
                self.model = TableModel(data)
                self.table.setModel(self.model)
            except Exception as e:
                self.status(f"Error: {e}", 10000)

    def draw_polygon(self):
        Draw(export=True).add_to(self.m)
        data = io.BytesIO()
        self.m.save(data, close_file=False)
        self.web_view.setHtml(data.getvalue().decode())

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
 
class ToolDialog(QDialog):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWindowIcon(QIcon(resource_path('icons/toolbox.png)'))
        self.setWindowTitle("Toolbox")
        self.resize(400, 300)

        layout = QVBoxLayout()

        label = QLabel("Select a tool:")
        layout.addWidget(label)

        self.tool_tree = QTreeWidget()
        self.tool_tree.setHeaderLabel("Tools")

        categories = {
            "Conversion Tools": {
                "Raster to Point": "icons/toolbox.png",
                "Raster to Polygon": "icons/toolbox.png",
                "Vector to Raster": "icons/toolbox.png",
                "Vector to GeoJSON": "icons/toolbox.png",
                "netCDF to Raster": "icons/toolbox.png",
                "netCDF to CSV": "icons/toolbox.png",
                "netCDF to Point": "icons/toolbox.png",
            },
            "Geoprocessing Tools": {
                "Clip": "icons/toolbox.png",
                "Buffer": "icons/toolbox.png",
                "Dissolve": "icons/toolbox.png"
            },
            "Spatial Analysis Tools": {
                "Spatial Join": "icons/toolbox.png",
                "Intersect": "icons/toolbox.png",
                "Union": "icons/toolbox.png",
                "IDW": "icons/toolbox.png",
                "Extract By Mask": "icons/toolbox.png"
            },
            "Projections": {
                "Define Projection": "icons/toolbox.png",
                "Reproject": "icons/toolbox.png"
            },
            "Analysis Tools": {
                "SPI": "icons/toolbox.png",
                "SPEI": "icons/toolbox.png"
            }
        }

        for category, tools in categories.items():
            category_item = QTreeWidgetItem([category])
            category_item.setIcon(0, QIcon(resource_path("icons/toolbox.png)"))
            for tool, icon_path in tools.items():
                tool_item = QTreeWidgetItem([tool])
                tool_item.setIcon(0, QIcon(resource_path(icon_path))
      )          category_item.addChild(tool_item)
            self.tool_tree.addTopLevelItem(category_item)

        self.tool_tree.itemClicked.connect(self.tool_selected)

        layout.addWidget(self.tool_tree)
        self.setLayout(layout)
    
    def tool_selected(self, item):
        if item.parent():  # Ensure it's a tool (not a category)
            selected_tool = item.text(0)
            if selected_tool == "Raster to Point":
                self.raster_to_point()
            elif selected_tool == "Vector to GeoJSON":
                self.shapefile_to_geojson()
            elif selected_tool == "netCDF to CSV":
                self.netCDF_to_csv()
            elif selected_tool == "Buffer":
                self.buffer_data()
            elif selected_tool == "Clip":
                self.clip()
            elif selected_tool == "Union":
                self.union()
            elif selected_tool == "IDW":
                self.idw()
            elif selected_tool == "Extract By Mask":
                self.extract_by_mask()
            elif selected_tool == "netCDF to Raster":
                self.netCDF_to_raster()
            elif selected_tool == "SPI":
                self.SPI()
            elif selected_tool == "SPEI":
                self.SPEI()
            elif selected_tool == "netCDF to Point":
                self.netcdf_to_shp()

    def buffer_data(self):
        dialog = QDialog()
        dialog.setWindowIcon(QIcon(resource_path('icons/buffer.png')))
        dialog.setWindowTitle("Buffer")
    
        layout = QVBoxLayout(dialog)
        list_layout = QHBoxLayout()
        variable_list = QListWidget(dialog)
        list_layout.addWidget(variable_list)
        layout.addLayout(list_layout)
        
        for layer in self.main_window.layers:
            file = str(layer)
            item = QListWidgetItem(file)
            item.setData(0, layer)
            variable_list.addItem(item)

        def open_file_dialog():
            layer_path, _ = QFileDialog.getOpenFileName(dialog, "Select Shapefile", "", "Shapefiles (*.shp)")
            if layer_path:
                layer = ShapefileLayer(layer_path)
                self.main_window.layers.append(layer)
                file = str(layer)
                item = QListWidgetItem(file)
                item.setData(0, layer)
                variable_list.addItem(item)

        load_layer_button = QPushButton(dialog)
        load_layer_button.setIcon(QIcon(resource_path('icons/folder.png')))
        load_layer_button.setIconSize(QSize(25, 25))
        load_layer_button.clicked.connect(open_file_dialog)
        list_layout.addWidget(load_layer_button)
        
        distance = QLineEdit(dialog)
        layout.addWidget(QLabel("Distance in cm"))
        layout.addWidget(distance)
        
        button_layout = QHBoxLayout()
        ok_button = QPushButton("Ok")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_item = variable_list.currentItem()
            if selected_item:
                layer = selected_item.data(0)
                if layer:
                    layer_path = layer.file_path
                    buffer_distance = int(distance.text()) if distance.text().isdigit() else 0
            try:
                gdf = gpd.read_file(layer_path)
                
                progress_bar = QProgressBar(self)
                progress_bar.setValue(0)
                self.status_Bar.addPermanentWidget(progress_bar)
                
                def progress():
                    for i in range(1, 101):
                        time.sleep(0.02)
                        progress_bar.setValue(i)
                        QApplication.processEvents()
                        
                if gdf.crs is None:
                    gdf.set_crs("EPSG:4326", allow_override=True, inplace=True)
                    
                progress()
                gdf = gdf.to_crs(epsg=3857)
                gdf['buffered'] = gdf.geometry.buffer(distance=buffer_distance)
                gdf = gdf.to_crs(epsg=4326)
                file_path = f"data/buffered_{layer}"
                file_name = os.path.basename(file_path)
                gdf[['buffered']].to_file(file_path)

                layer = ShapefileLayer(file_path)
                layer.add_to_map(self.m)
                self.main_window.layers.append(layer)
                self.main_window.add_layer_checkbox(layer, file_name)
                data = io.BytesIO()
                self.main_window.m.save(data, close_file=False)
                self.main_window.web_view.setHtml(data.getvalue().decode())
                self.main_window.status(f"{file} buffered successfully", 5000)
            except Exception as e:
                self.main_window.status(f"Error: {e}", 10000)

    def clip(self):
        dialog = QDialog()
        dialog.setWindowIcon(QIcon(resource_path('icons/buffer.png')))
        dialog.setWindowTitle("Clip")
        dialog.resize(500, 300)
        layout = QVBoxLayout(dialog)

        input_layout = QHBoxLayout()
        input_widget = QLineEdit()
        layout.addWidget(QLabel("Input Path:"))
        input_layout.addWidget(input_widget)
        layout.addLayout(input_layout)
        
        progress_bar = QProgressBar(self)
        progress_bar.setValue(0)
        self.main_window.status_Bar.addPermanentWidget(progress_bar)
       
        def open_file_dialog():
            raster_file, _ = QFileDialog.getOpenFileName(dialog, "Load GeoData", "", "DataSets, Layers (*.tif *.tiff *.shp *.nc)")
            if raster_file:
                input_widget.setText(raster_file)
                      
        load_layer_button = QPushButton(dialog)
        load_layer_button.setIcon(QIcon(resource_path('icons/folder.png')))
        load_layer_button.setIconSize(QSize(25, 25))
        load_layer_button.clicked.connect(open_file_dialog)
        input_layout.addWidget(load_layer_button)
        
        mask_layout = QHBoxLayout()
        mask_input = QLineEdit()
        layout.addWidget(QLabel("Mask File (Shapefile):"))
        mask_layout.addWidget(mask_input)
        layout.addLayout(mask_layout)

        def load_mask_file():
            mask_path, _ = QFileDialog.getOpenFileName(dialog, "Select Mask File", "", "Shapefile (*.shp)")
            if mask_path:
                mask_input.setText(mask_path)

        mask_button = QPushButton(dialog)
        mask_button.setIcon(QIcon(resource_path('icons/folder.png')))
        mask_button.setIconSize(QSize(25, 25))
        mask_button.clicked.connect(load_mask_file)
        mask_layout.addWidget(mask_button)

        # Output file
        output_layout = QHBoxLayout()
        output_input = QLineEdit()
        layout.addWidget(QLabel("Output Raster Path:"))
        output_layout.addWidget(output_input)
        layout.addLayout(output_layout)

        def save_output_file():
            output_path, _ = QFileDialog.getSaveFileName(dialog, "Save Output Raster", "", "DataSets, Layers (*.tif *.tiff *.shp *.nc)")
            if output_path:
                output_input.setText(output_path)

        output_button = QPushButton(dialog)
        output_button.setIcon(QIcon(resource_path('icons/folder.png')))
        output_button.setIconSize(QSize(25, 25))
        output_button.clicked.connect(save_output_file)
        output_layout.addWidget(output_button)
        
        button_layout = QHBoxLayout()
        ok_button = QPushButton("Ok")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            input_path = input_widget.text()
            file_extension = os.path.splitext(input_path)[1]
            
            if file_extension in (".tif", ".tiff"):
                print("Raster")
            elif file_extension == ".shp":
                print("ShapeFile")
            elif file_extension == ".nc":
                print("netCDF")
    
    def union(self):
        dialog = QDialog()
        dialog.setWindowIcon(QIcon(resource_path('icons/buffer.png')))
        dialog.setWindowTitle("Union")

        layout = QVBoxLayout(dialog)
        variable_list = QListWidget(dialog)
        
        for layer in self.main_window.layers:
            file = str(layer)
            item = QListWidgetItem(file)
            item.setData(0, layer)
            variable_list.addItem(item)
        layout.addWidget(variable_list)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("Ok")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_item = variable_list.currentItem()
            if selected_item:
                layer = selected_item.data(0)
                if layer:
                    layer_path = layer.file_path

    def intersect(self):
        dialog = QDialog()
        dialog.setWindowIcon(QIcon(resource_path('icons/buffer.png')))
        dialog.setWindowTitle("Intersect")

        layout = QVBoxLayout(dialog)
        variable_list = QListWidget(dialog)
        
        for layer in self.main_window.layers:
            file = str(layer)
            item = QListWidgetItem(file)
            item.setData(0, layer)
            variable_list.addItem(item)
        layout.addWidget(variable_list)
        
        input_layout = QHBoxLayout()
        input_widget1 = QLineEdit()
        layout.addWidget(QLabel("Input nc Path:"))
        input_layout.addWidget(input_widget1)
        layout.addLayout(input_layout)
        
        input_layout = QHBoxLayout()
        input_widget2 = QLineEdit()
        layout.addWidget(QLabel("Input nc Path:"))
        input_layout.addWidget(input_widget2)
        layout.addLayout(input_layout)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("Ok")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        figure = Figure()
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas, stretch=1)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            input1 = input_widget1.text()
            input2 = input_widget2.text()
            intersection = input1.intersection(input2)
            fig, ax = figure.subplots()
            intersection.plot(ax=ax, color='red')
            canvas.draw()
            
            def save():
                output_path, _ = QFileDialog.getSaveFileName(dialog, "Save CSV File", "", "Comma Seperated Value Files (*.csv)")
                if output_path:
                    intersection.to_file()
                    
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

    def idw(self):
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
                        self.main_window.status(f"Error loading shapefile: {e}", 10000)
                else:
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
                    power = float(power_input.text()) if power_input.text().isdigit() else 2
                    resolution = float(resolution_input.text()) if resolution_input.text().replace('.', '', 1).isdigit() else None
                    attribute = attribute_combo.currentText()
                    output_path = output_input.text()
                    if not (attribute and output_path and resolution):
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
                                
                    def idw_interpolation_on_shapefile(input, attribute, output_file_path, resolution, power=2):
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
                                
                        self.main_window.status("IDW Interpolation completed successfully.", 10000)

                        with rasterio.open(output_path) as src:
                            raster_data = src.read(1)
                            bounds = [[src.bounds.bottom, src.bounds.left], [src.bounds.top, src.bounds.right]]

                            num_bins = 9
                            bin_edges = np.linspace(raster_data.min(), raster_data.max(), num_bins + 1)
                            discrete_data = np.digitize(raster_data, bin_edges)

                            colors = ['#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#005a32']
                            cmap = matplotlib.colors.ListedColormap(colors)
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
                        self.main_window.status(f"Error during IDW: {e}", 10000)
                    
    def extract_by_mask(self):
        dialog = QDialog()
        dialog.setWindowTitle("Extract by Mask")
        dialog.resize(500, 300)
        layout = QVBoxLayout(dialog)

        raster_layout = QHBoxLayout()
        raster_input = QLineEdit()
        layout.addWidget(QLabel("Input Raster:"))
        raster_layout.addWidget(raster_input)
        layout.addLayout(raster_layout)

        def load_raster_file():
            raster_path, _ = QFileDialog.getOpenFileName(dialog, "Select Raster", "", "GeoTIFF (*.tif)")
            if raster_path:
                raster_input.setText(raster_path)

        raster_button = QPushButton(dialog)
        raster_button.setIcon(QIcon(resource_path('icons/folder.png')))
        raster_button.setIconSize(QSize(25, 25))
        raster_button.clicked.connect(load_raster_file)
        raster_layout.addWidget(raster_button)

        mask_layout = QHBoxLayout()
        mask_input = QLineEdit()
        layout.addWidget(QLabel("Mask File (Shapefile):"))
        mask_layout.addWidget(mask_input)
        layout.addLayout(mask_layout)

        def load_mask_file():
            mask_path, _ = QFileDialog.getOpenFileName(dialog, "Select Mask File", "", "Shapefile (*.shp)")
            if mask_path:
                mask_input.setText(mask_path)

        mask_button = QPushButton(dialog)
        mask_button.setIcon(QIcon(resource_path('icons/folder.png')))
        mask_button.setIconSize(QSize(25, 25))
        mask_button.clicked.connect(load_mask_file)
        mask_layout.addWidget(mask_button)

        # Output file
        output_layout = QHBoxLayout()
        output_input = QLineEdit()
        layout.addWidget(QLabel("Output Raster Path:"))
        output_layout.addWidget(output_input)
        layout.addLayout(output_layout)

        def save_output_file():
            output_path, _ = QFileDialog.getSaveFileName(dialog, "Save Output Raster", "", "GeoTIFF (*.tif)")
            if output_path:
                output_input.setText(output_path)

        output_button = QPushButton(dialog)
        output_button.setIcon(QIcon(resource_path('icons/folder.png')))
        output_button.setIconSize(QSize(25, 25))
        output_button.clicked.connect(save_output_file)
        output_layout.addWidget(output_button)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("Ok")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            raster_path = raster_input.text()
            mask_path = mask_input.text()
            output_path = output_input.text()
            output_file_name = os.path.basename(output_path)
            
            if not raster_path or not mask_path or not output_path:
                self.main_window.status("Error: All fields are required.", 5000)
                return

            try:
                with rasterio.open(raster_path) as src:
                    progress_bar = QProgressBar(self)
                    progress_bar.setValue(0)
                    self.main_window.status_Bar.addPermanentWidget(progress_bar)
                    progress_bar.setVisible(True)
            
                    mask_gdf = gpd.read_file(mask_path)
                    mask_geometry = mask_gdf.geometry

                    out_image, out_transform = mask(src, mask_geometry, crop=True)
                    out_meta = src.meta.copy()

                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_image.shape[1],
                        "width": out_image.shape[2],
                        "transform": out_transform,
                    })

                    with rasterio.open(output_path, "w", **out_meta) as dest:
                        dest.write(out_image)
                    
                    progress_bar.setValue(100)
                    
                self.main_window.status("Extract by Mask completed successfully!", 5000)
                layer = TIFFLayer(output_path)
                layer.add_to_map(self.main_window.m)
                self.main_window.add_layer_checkbox(layer, output_file_name)
                self.main_window.layers.append(layer)

                data = io.BytesIO()
                self.main_window.m.save(data, close_file=False)
                self.main_window.web_view.setHtml(data.getvalue().decode())
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

    def SPI(self):
        dialog = QDialog()
        dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
        dialog.setWindowTitle("Standard Precipitation Index(SPI)")
        dialog.resize(1300, 1000)
        layout = QVBoxLayout(dialog)
        
        def update_progress(value):
            progress_bar.setValue(value)
            QApplication.processEvents()

        def openMeteo(latitude, longitude, start_date, end_date):
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "models": "era5_seamless",
                "timezone": "auto",
                "daily": "precipitation_sum"
            }
            try:

                responses = openmeteo.weather_api(url, params=params)
                status_bar.showMessage("Getting Data...", 5000)

                if not responses:
                    self.main_window.status("Check your internet connection.")

                response = responses[0]
                daily = response.Daily()
                
                daily_precipitation_sum = daily.Variables(0).ValuesAsNumpy()
                
                daily_data = {"date": pd.date_range(
                    start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
                    end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
                    freq = pd.Timedelta(seconds = daily.Interval()),
                    inclusive = "left"
                )}
                
                daily_data["precipitation_sum"] = daily_precipitation_sum
                df = pd.DataFrame(data = daily_data)
                status_bar.showMessage("Saving Data...", 5000)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", prefix="climate_data")
                df.to_csv(temp_file.name, index=False)
                return temp_file.name
            except Exception as e:
                self.main_window.status(f"Error fetching or processing data: {e}", 100000)
                return None

        top_section = QWidget()
        layout.addWidget(top_section)
        top_layout = QVBoxLayout(top_section)

        location = QHBoxLayout()
        location.addWidget(QLabel("Latitude"))
        latitude_input = QLineEdit("7.8526")
        location.addWidget(latitude_input)
        location.addWidget(QLabel("Longitude"))
        longitude_input = QLineEdit("3.9312")
        location.addWidget(longitude_input)
        top_layout.addLayout(location)

        date = QHBoxLayout()
        date.addWidget(QLabel("Enter Start Date:"))
        start_input_field = QLineEdit("1993-01-01")
        date.addWidget(start_input_field)
        date.addWidget(QLabel("Enter End Date:"))
        end_input_field = QLineEdit("2023-12-31")
        date.addWidget(end_input_field)
        top_layout.addLayout(date)
        
        figure = Figure()
        canvas = FigureCanvas(figure)

        toolbar = NavigationToolbar(canvas, self)
        
        layout.addWidget(toolbar)
        layout.addWidget(canvas, stretch=1)

        def spi(ds, thresh):         
            #Rolling Mean
            ds_ma = ds.rolling(window=thresh, min_periods=1, center=False).mean()

            # Replace zeros in rolling mean with a small value to avoid log issues
            epsilon = 1e-6  # Small value to substitute for zeros
            ds_ma_safe = ds_ma.replace(0, epsilon)
            
            #Nutural log of M. A.
            ds_In = np.log(ds_ma_safe)

            ds_mu = ds_ma.mean()

            #summation of log of M. A.
            ds_sum = ds_In.sum()

            #computing for gamma distribution
            n = len(ds_In)
            A = np.log(ds_mu) - (ds_sum/n)
            alpha = (1 / (4 * A) ) * (1 + (1 + (4 * A) / 3) ** 0.5)
            beta = ds_mu/alpha

            #gamm distribution (CDF)
            gamma = st.gamma.cdf(ds_ma, a=alpha, scale=beta)

            #SPI (Inverse of CDF)
            norm_spi = st.norm.ppf(gamma, loc=0, scale=1)
            return norm_spi
            update_progress(100)
        
        def update_spi():
            try:
                progress_bar.setVisible(True)
                latitude = float(latitude_input.text())
                longitude = float(longitude_input.text())
                start_date = str(start_input_field.text())
                end_date = str(end_input_field.text())

                csv_path = openMeteo(latitude, longitude, start_date, end_date)
                if not csv_path:
                    self.main_window.status("No csv file path", 10000)
                    return

                data = pd.read_csv(csv_path, parse_dates=["date"])
                data.set_index('date', inplace=True)
                data = data.sort_index()
                data['precipitation_sum'] = data['precipitation_sum'].fillna(0)

                times = [3, 6, 9, 12]
                for i in times:
                    x = spi(data['precipitation_sum'], i)
                    data['spi_'+str(i)] = x

                figure.clear()

                axes = figure.subplots(nrows=4)
                figure.subplots_adjust(hspace=0.15)

                for i, ax in enumerate(axes):
                    col_scheme = np.where(data['spi_'+str(times[i])]>0, 'b', 'r')
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
                    ax.bar(data.index, data['spi_'+str(times[i])], width=25, align='center', color=col_scheme, label='SPI '+str(times[i]))
                    ax.axhline(y=0, color='k')
                    ax.xaxis.set_major_locator(mdates.YearLocator(2))
                    ax.legend(loc='upper right')
                    ax.set_yticks(range(-3,4), range(-3,4))
                    ax.set_ylabel('SPI', fontsize=12)

                    if i<len(times)-1:
                        ax.set_xticks([], [])
                canvas.draw()
                progress_bar.setVisible(False)
                
                save_button.setEnabled(True)
                save_button.activated.connect(lambda: save_spi_data(data))
            except Exception as e:
                self.main_window.status(f"Error: {e}", 10000)
            finally:
                status_bar.removeWidget(progress_bar)
        
        buttons = QHBoxLayout()
        update_button = QPushButton("Calculate SPI")
        update_button.setFixedSize(QSize(1200, 30))
        update_button.clicked.connect(update_spi)
        buttons.addWidget(update_button)
        top_layout.addLayout(buttons)
        
        def save_spi_data(data):
            selected_option = save_button.currentText()
            if selected_option == "Save as CSV":
                file_dialog = QFileDialog()
                save_path, _ = file_dialog.getSaveFileName(dialog, "Save SPI Data", "", "CSV Files (*.csv)")
                if save_path:
                    data.to_csv(save_path)
                    self.main_window.status(f"SPI data saved to {save_path}.", 5000)
            elif selected_option == "Save as Image":
                file_dialog = QFileDialog()
                save_path, _ = file_dialog.getSaveFileName(dialog, "Save SPI Plot", "", "PNG Files (*.png)")
                if save_path:
                    figure.savefig(save_path)
                    self.main_window.status(f"SPI data saved to {save_path}", 5000)
            
        save_button = QComboBox()
        save_button.setEnabled(False)
        save_button.addItem(QIcon(resource_path("icons/save.png"),) "Save as CSV")
        save_button.addItem(QIcon(resource_path("icons/save.png"),) "Save as Image")
        buttons.addWidget(save_button)
    
        status_bar = QStatusBar(dialog)
        layout.addWidget(status_bar)
        
        progress_bar = QProgressBar(dialog)
        progress_bar.setValue(0)
        status_bar.addPermanentWidget(progress_bar)

        dialog.exec()

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

    def SPEI(self):
        dialog = QDialog()
        dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
        dialog.setWindowTitle("Standard Precipitation Evapotranspiration Index(SPEI)")
        dialog.resize(1300, 1000)
        layout = QVBoxLayout(dialog)
        
        def update_progress(value):
            progress_bar.setValue(value)
            QApplication.processEvents()

        def openMeteo(latitude, longitude, start_date, end_date):
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
                status_bar.showMessage("Getting Data...", 5000)

                if not responses:
                    self.main_window.status("Check your internet connection.")

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
                status_bar.showMessage("Saving Data...", 2000)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", prefix="climate_data")
                df.to_csv(temp_file.name, index=False)
                return temp_file.name
            except Exception as e:
                self.main_window.status(f"Error fetching or processing data: {e}", 100000)
                return None

        top_section = QWidget()
        layout.addWidget(top_section)
        top_layout = QVBoxLayout(top_section)

        location = QHBoxLayout()
        location.addWidget(QLabel("Latitude"))
        latitude_input = QLineEdit("7.8526")
        location.addWidget(latitude_input)
        location.addWidget(QLabel("Longitude"))
        longitude_input = QLineEdit("3.9312")
        location.addWidget(longitude_input)
        top_layout.addLayout(location)

        date = QHBoxLayout()
        date.addWidget(QLabel("Enter Start Date:"))
        start_input_field = QLineEdit("1993-01-01")
        date.addWidget(start_input_field)
        date.addWidget(QLabel("Enter End Date:"))
        end_input_field = QLineEdit("2023-12-31")
        date.addWidget(end_input_field)
        top_layout.addLayout(date)
        
        figure = Figure()
        canvas = FigureCanvas(figure)

        toolbar = NavigationToolbar(canvas, self)
        
        layout.addWidget(toolbar)
        layout.addWidget(canvas, stretch=1)

        def spei(precipitation, pet, window):
            deficit = precipitation - pet

            # Rolling sum over the specified window
            rolling_deficit = deficit.rolling(window=window, min_periods=1).sum()
            
            # Fit Gamma distribution to rolling sums
            rolling_deficit_safe = rolling_deficit.replace(
                0, 1e-6
            )  # Avoid log issues with zeros
            gamma_cdf = st.gamma.cdf(
                rolling_deficit_safe, a=2, scale=1
            )  # Example params, adjust as needed

            # Convert CDF to standard normal distribution (z-scores)
            spei = st.norm.ppf(gamma_cdf)

            return pd.Series(spei, index=precipitation.index)
            update_progress(100)
        
        def update_spei():
            try:
                progress_bar.setVisible(True)
                latitude = float(latitude_input.text())
                longitude = float(longitude_input.text())
                start_date = str(start_input_field.text())
                end_date = str(end_input_field.text())

                csv_path = openMeteo(latitude, longitude, start_date, end_date)
                if not csv_path:
                    self.main_window.status("No csv file path", 10000)
                    return

                data = pd.read_csv(csv_path, parse_dates=["date"])
                data.set_index('date', inplace=True)
                data = data.sort_index()
                data['precipitation_sum'] = data['precipitation_sum'].fillna(0)
                data["et0_fao_evapotranspiration"] = data["et0_fao_evapotranspiration"].fillna(0)

                times = [3, 6, 9, 12]
                for i in times:
                    x = spei(data['precipitation_sum'], data["et0_fao_evapotranspiration"], i)
                    data['spei_'+str(i)] = x

                figure.clear()

                axes = figure.subplots(nrows=4)
                figure.subplots_adjust(hspace=0.15)
                
                for i, ax in enumerate(axes):
                    col_scheme = np.where(data['spei_'+str(times[i])]>0, 'b', 'r')
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
                    ax.bar(data.index, data['spei_'+str(times[i])], width=25, align='center', color=col_scheme, label='SPEI '+str(times[i]))
                    ax.axhline(y=0, color='k')
                    ax.xaxis.set_major_locator(mdates.YearLocator(2))
                    ax.legend(loc='upper right')
                    ax.set_yticks(range(-3,4), range(-3,4))
                    ax.set_ylabel('SPEI', fontsize=12)

                    if i<len(times)-1:
                        ax.set_xticks([], [])
                canvas.draw()
                progress_bar.setVisible(False)
                
                save_button.setEnabled(True)
                save_button.activated.connect(lambda: save_spei_data(data))
            except Exception as e:
                self.main_window.status(f"Error: {e}", 10000)
            finally:
                status_bar.removeWidget(progress_bar)
        
        buttons = QHBoxLayout()
        update_button = QPushButton("Calculate SPEI")
        update_button.setFixedSize(QSize(1200, 30))
        update_button.clicked.connect(update_spei)
        buttons.addWidget(update_button)
        top_layout.addLayout(buttons)
        
        def save_spei_data(data):
            selected_option = save_button.currentText()
            if selected_option == "Save as CSV":
                file_dialog = QFileDialog()
                save_path, _ = file_dialog.getSaveFileName(dialog, "Save SPEI Data", "", "CSV Files (*.csv)")
                if save_path:
                    data.to_csv(save_path)
                    self.main_window.status(f"SPEI data saved to {save_path}", 5000)
            elif selected_option == "Save as Image":
                file_dialog = QFileDialog()
                save_path, _ = file_dialog.getSaveFileName(dialog, "Save SPEI Plot", "", "Portable Network Graphics (*.png)")
                if save_path:
                    figure.savefig(save_path)
                    self.main_window.status(f"SPEI data saved to {save_path}", 5000)
        
        save_button = QComboBox()
        save_button.setEnabled(False)
        save_button.addItem(QIcon(resource_path("icons/save.png"),) "Save as CSV")
        save_button.addItem(QIcon(resource_path("icons/save.png"),) "Save as Image")
        buttons.addWidget(save_button)
        
        status_bar = QStatusBar(dialog)
        layout.addWidget(status_bar)
        
        progress_bar = QProgressBar(dialog)
        progress_bar.setValue(0)
        status_bar.addPermanentWidget(progress_bar)

        dialog.exec()

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

class PythonInterpreter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("icons/python.png")))
        self.setWindowTitle("Python Interpreter")
        self.resize(600, 400)

        self.layout = QVBoxLayout()
        self.code_input = QTextEdit(self)
        self.code_input.setPlaceholderText("Write your Python code here...")
        self.layout.addWidget(self.code_input)

        self.run_button = QPushButton("Run Code", self)
        self.run_button.clicked.connect(self.execute_code)
        self.layout.addWidget(self.run_button)

        self.output_display = QTextEdit(self)
        self.output_display.setReadOnly(True)
        self.layout.addWidget(self.output_display)

        self.setLayout(self.layout)

        self.toolbar()

    def execute_code(self):
        code = self.code_input.toPlainText()
        try:
            old_stdout = sys.stdout
            sys.stdout = OutputRedirect(self.output_display)
            exec(code)
        except Exception as e:
            self.output_display.append(f"Error: {e}")
        finally:
            sys.stdout = old_stdout

    def toolbar(self):
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(15, 15))

        run = QAction(QIcon(resource_path("icons/polygon.png)"), "Draw", self)
        run.triggered.connect(self.execute_code)
        toolbar.addAction(run)

class OutputRedirect:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, text):
        self.text_edit.append(text)

    def flush(self):
        pass

#======================================================================================================================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    pixmap = QPixmap("icons/loading.png").scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    window = GISApp()
    window.show()
    splash.finish(window)
    sys.exit(app.exec())
