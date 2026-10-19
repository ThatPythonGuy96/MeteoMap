# entry point — QApplication + splash + GISApp
import sys
import os

os.environ["QT_OPENGL"] = "software"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QTWEBENGINE_DISABLE_GPU"] = "1"

from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, 
from app.gis_app import GISApp
from utils.logger import setup_logger
from utils.paths import resource_path

logger = setup_logger()

if __name__ == "__main__":
    logger.info("Starting MeteoGis application...")
    app = QApplication(sys.argv)
    pixmap = QPiQSplashScreenxmap(resource_path("icons/loading.png")).scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    window = GISApp()
    window.show()
    splash.finish(window)
    sys.exit(app.exec())