# spi() function + openMeteo() fetcher
import pandas as pd
from scipy import stats as st
import matplotlib.dates as mdates
import numpy as np
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QPushButton, QWidget, QFileDialog, QLabel, QHBoxLayout
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

def SPI(self):
    dialog = QDialog()
    dialog.setWindowIcon(QIcon(resource_path("icons/buffer.png")))
    dialog.setWindowTitle("Standard Precipitation Index(SPI)")
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
        update_progress(100)
        return norm_spi
    
    def update_spi():
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
            logger.debug("SPI failed")
            self.main_window.status(f"SPI Error: {e}", 10000)
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
                self.main_window.status(f"SPI data saved to {save_path}.", 9000)
        elif selected_option == "Save as Image":
            file_dialog = QFileDialog()
            save_path, _ = file_dialog.getSaveFileName(dialog, "Save SPI Plot", "", "PNG Files (*.png)")
            if save_path:
                figure.savefig(save_path)
                self.main_window.status(f"SPI data saved to {save_path}", 9000)
        
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
