# ToolDialog — all 12+ tools
from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtWidgets import QDialog, QTreeWidget, QTreeWidgetItem
from PyQt6.QtGui import QIcon
from tools.conversion import *
from tools.geoprocessing import *
from analysis.spi import SPI
from analysis.spei import SPEI
from analysis.idw import IDW
from utils.paths import resource_path

class ToolDialog(QDialog):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.status_bar = main_window.statusBar()  # Access the status bar from the main window
        self.setWindowIcon(QIcon(resource_path('icons/toolbox.png')))
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
            category_item.setIcon(0, QIcon(resource_path("icons/toolbox.png")))
            for tool, icon_path in tools.items():
                tool_item = QTreeWidgetItem([tool])
                tool_item.setIcon(0, QIcon(resource_path(icon_path)))
                category_item.addChild(tool_item)
            self.tool_tree.addTopLevelItem(category_item)

        self.tool_tree.itemClicked.connect(self.tool_selected)

        layout.addWidget(self.tool_tree)
        self.setLayout(layout)
    
    def tool_selected(self, item):
        if item.parent():  # Ensure it's a tool (not a category)
            selected_tool = item.text(0)
            
            if selected_tool == "Raster to Point":
                raster_to_point(self)
            elif selected_tool == "Vector to GeoJSON":
                shapefile_to_geojson(self)
            elif selected_tool == "netCDF to CSV":
                netCDF_to_csv(self)
            elif selected_tool == "Buffer":
                buffer_data(self.main_window)
            elif selected_tool == "Clip":
                clip(self)
            elif selected_tool == "Union":
                union(self)
            elif selected_tool == "IDW":
                IDW(self)
            elif selected_tool == "Extract By Mask":
                extract_by_mask(self)
            elif selected_tool == "netCDF to Raster":
                netCDF_to_raster(self)
            elif selected_tool == "SPI":
                SPI(self)
            elif selected_tool == "SPEI":
                SPEI(self)
            elif selected_tool == "netCDF to Point":
                netcdf_to_shp(self)
