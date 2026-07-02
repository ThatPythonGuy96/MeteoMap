# GISApp (QMainWindow) — map tab, toolbars, menu
import io, os, time
import pandas as pd
import matplotlib.dates as mdates
import geopandas as gpd
import folium
from folium.plugins import MousePosition
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QPushButton, QWidget, QFileDialog, QLabel, QHBoxLayout, QCheckBox, QListWidget,QListWidgetItem, QTableView
from PyQt6.QtWidgets import QToolBar, QPushButton, QProgressBar, QLineEdit, QSplitter, QMainWindow, QTabWidget, QStatusBar, QApplication, QMainWindow, QStatusBar
from PyQt6.QtWebEngineWidgets import QWebEngineView 
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import QSize, Qt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import openmeteo_requests, requests_cache
from retry_requests import retry
from folium.plugins import Draw
from app.tool_dialog import ToolDialog
from widgets.basemap_dialog import BasemapDialog
from widgets.python_interpreter import PythonInterpreter
from layers.netcdf import *
from layers.raster import *
from layers.vector import *
from widgets.table_model import TableModel
from tools.geoprocessing import *
from utils.paths import resource_path

cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

class GISApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MeteoMap")
        self.setWindowIcon(QIcon(resource_path("meteomap.ico")))
        self.setGeometry(100, 100, 1000, 900)
        
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
        new_action = QAction(QIcon(resource_path("icons/new.png")), 'New File', self)
        new_action.setShortcut('Ctrl+N') 
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        load_action = QAction('Load Data', self)
        load_action.setShortcut('Ctrl+L')
        load_action.triggered.connect(self.load_data)
        file_menu.addAction(load_action)
        
        save_action = QAction(QIcon(resource_path("icons/save.png")), 'Save', self)
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
        undo_action = QAction(QIcon(resource_path('icons/undo.png')), '&Undo', self)
        undo_action.setStatusTip('Undo')
        undo_action.setShortcut('Ctrl+Z')
        edit_menu.addAction(undo_action)

        redo_action = QAction(QIcon(resource_path('icons/redo.png')), '&Redo', self)
        redo_action.setStatusTip('Redo')
        redo_action.setShortcut('Ctrl+Y')
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        copy_action = QAction(QIcon(resource_path('icons/copy.png')), '&Copy', self)
        edit_menu.addAction(copy_action)
        copy_action.setShortcut('Ctrl+C')
        
        cut_action = QAction(QIcon(resource_path('icons/cut.png')), '&Cut', self)
        edit_menu.addAction(cut_action)
        cut_action.setShortcut('Ctrl+X')
        
        paste_action = QAction(QIcon(resource_path('icons/paste.png')), '&Paste', self)
        edit_menu.addAction(paste_action)
        paste_action.setShortcut('Ctrl+Y')
        
        edit_menu.addSeparator()
        
        # Create Geop actions using QAction
        buffer = QAction(QIcon(resource_path('icons/buffer.png')), 'Buffer', self)
        buffer.triggered.connect(lambda: buffer_data(main_window=self))
        geop_menu.addAction(buffer)

        clipp = QAction('Clip', self)
        clipp.triggered.connect(lambda: clip(main_window=self))
        geop_menu.addAction(clipp)

        unionn = QAction('Union', self)
        unionn.triggered.connect(lambda: union(main_window=self))
        geop_menu.addAction(unionn)

        geop_menu.addSeparator()

        toolbox = QAction(QIcon(resource_path('icons/toolbox.png')), 'ToolBox', self)
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

        new_button = QAction(QIcon(resource_path("icons/new.png")), "New File", self)
        toolbar.addAction(new_button)
        
        toolbar.addSeparator()
        
        paste_button = QAction(QIcon(resource_path("icons/paste.png")), "Paste", self)
        toolbar.addAction(paste_button)

        copy_button = QAction(QIcon(resource_path("icons/copy.png")), "Copy", self)
        toolbar.addAction(copy_button)

        cut_button = QAction(QIcon(resource_path("icons/cut.png")), "Cut", self)
        toolbar.addAction(cut_button)

    def toolbar2(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.setIconSize(QSize(15, 15))

        draw_button = QAction(QIcon(resource_path("icons/polygon.png")), "Draw", self)
        draw_button.triggered.connect(self.draw_polygon)
        toolbar.addAction(draw_button)

        basemap_button = QAction(QIcon(resource_path("icons/basemap.png")), "BaseMap", self)
        basemap_button.triggered.connect(self.open_basemap_dialog)
        toolbar.addAction(basemap_button)

        add_button = QAction(QIcon(resource_path("icons/plus.png")), "Add Data", self)
        add_button.triggered.connect(self.load_data)
        toolbar.addAction(add_button)
    
    def toolbar3(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.setIconSize(QSize(15, 15))

        toolbox_button = QAction(QIcon(resource_path("icons/toolbox.png")), "ToolBox", self)
        toolbox_button.triggered.connect(self.toolbox_dialog)
        toolbar.addAction(toolbox_button)

        interpreter_button = QAction(QIcon(resource_path("icons/python.png")), "Python Interpreter", self)
        interpreter_button.triggered.connect(self.open_python_interpreter)
        toolbar.addAction(interpreter_button)

    def toolbar4(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.setIconSize(QSize(15, 15))
        
        zoomin_button = QAction(QIcon(resource_path("icons/zoom-in.png")), "Zoom In", self)
        toolbar.addAction(zoomin_button)

        zoomout_button = QAction(QIcon(resource_path("icons/zoom-out.png")), "Zoom Out", self)
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
