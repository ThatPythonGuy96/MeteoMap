# get_app_temp_dir(), packaging-safe paths
import sys, os, tempfile

def get_app_data_dir() -> str:
    """Base writable directory for all app data — works installed or in dev."""
    if getattr(sys, 'frozen', False):
        base = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'MeteoMap')
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    os.makedirs(base, exist_ok=True)
    return base

def get_app_temp_dir() -> str:
    path = os.path.join(get_app_data_dir(), 'temp')
    os.makedirs(path, exist_ok=True)
    return path

def get_cache_path() -> str:
    path = os.path.join(get_app_data_dir(), 'cache', 'omcache')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

def resource_path(relative: str) -> str:
    """Works both in dev and inside a PyInstaller bundle."""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(__file__), '..', relative)