import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def get_log_path() -> str:
    """Packaging-safe log file location."""
    if getattr(sys, 'frozen', False):
        # Packaged exe — write next to the exe
        base = os.path.dirname(sys.executable)
    else:
        # Running as script — write next to main.py
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, '..')  # up from utils/

    log_dir = os.path.join(base, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'meteogis.log')


def setup_logger() -> logging.Logger:
    """
    Call once in main.py before QApplication starts.
    Returns the root logger configured for MeteoGis.
    """
    logger = logging.getLogger('meteogis')
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger  # already configured, don't add duplicate handlers

    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(module)s.%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Rotating file — max 2MB, keeps last 3 files
    file_handler = RotatingFileHandler(
        get_log_path(),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (visible when running as script)
    if not getattr(sys, 'frozen', False):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger