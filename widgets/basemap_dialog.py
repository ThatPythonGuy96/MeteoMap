# BasemapDialog
from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QLabel, QDialog, QPushButton, QComboBox

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
    
    