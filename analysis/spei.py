# spei() + thornthwaite_pet() + openMeteo()
import pandas as pd
from scipy import stats as st
import matplotlib.dates as mdates
import numpy as np
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QPushButton, QWidget, QFileDialog, QLabel, QHBoxLayout, QMessageBox
from PyQt6.QtWidgets import QDialog, QPushButton, QComboBox, QProgressBar, QLineEdit, QStatusBar
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from analysis.openmeteo_fetch import openMeteo
from utils.paths import resource_path

import logging
logger = logging.getLogger('meteogis')

def SPEI(self):
    dialog = QDialog()
    dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
    dialog.setWindowTitle("Standard Precipitation Evapotranspiration Index(SPEI)")
    dialog.resize(600, 550)
    layout = QVBoxLayout(dialog)
    
    def update_progress(value):
        progress_bar.setValue(value)
        QApplication.processEvents()
        
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

        update_progress(100)
        return pd.Series(spei, index=precipitation.index)
        
    
    def update_spei():
        try:
            progress_bar.setVisible(True)
            latitude = float(latitude_input.text())
            longitude = float(longitude_input.text())
            start_date = str(start_input_field.text())
            end_date = str(end_input_field.text())

            csv_path = openMeteo(
                latitude, longitude, start_date, end_date, 
                status_callback=lambda msg, duration: self.status_bar.showMessage(msg, duration)
            )
            if not csv_path:
                logger.debug("No CSV file path returned from openMeteo")
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
            logger.debug("SPEI failed")
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
                self.main_window.status(f"SPEI data saved to {save_path}", 9000)
        elif selected_option == "Save as Image":
            file_dialog = QFileDialog()
            save_path, _ = file_dialog.getSaveFileName(dialog, "Save SPEI Plot", "", "Portable Network Graphics (*.png)")
            if save_path:
                figure.savefig(save_path)
                self.main_window.status(f"SPEI data saved to {save_path}", 9000)
    
    save_button = QComboBox()
    save_button.setEnabled(False)
    save_button.addItem(QIcon(resource_path("icons/save.png")), "Save as CSV")
    save_button.addItem(QIcon(resource_path("icons/save.png")), "Save as Image")
    buttons.addWidget(save_button)
    
    status_bar = QStatusBar(dialog)
    layout.addWidget(status_bar)
    
    progress_bar = QProgressBar(dialog)
    progress_bar.setValue(0)
    status_bar.addPermanentWidget(progress_bar)

    dialog.exec()
