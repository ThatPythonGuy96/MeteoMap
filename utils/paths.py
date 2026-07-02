# get_app_temp_dir(), packaging-safe paths
import sys, os, tempfile

def get_app_temp_dir():
    """Returns a writable temp directory that works both as script and .exe"""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        # sys._MEIPASS is the unpacked bundle dir (read-only in --onefile)
        # Use the user's actual temp dir instead
        base = tempfile.gettempdir()
    else:
        # Running as script
        base = tempfile.gettempdir()
    
    app_temp = os.path.join(base, "MeteoMap")
    os.makedirs(app_temp, exist_ok=True)
    return app_temp

def resource_path(relative: str) -> str:
    """Works both in dev and inside a PyInstaller bundle."""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(__file__), '..', relative)