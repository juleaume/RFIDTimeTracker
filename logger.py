import logging
import sys
import os
from logging.handlers import RotatingFileHandler

_log_file_name = 'log/time_tracker.log'
if not os.path.isdir("log"):
    os.mkdir("log")

_log_handler = RotatingFileHandler(
    _log_file_name, maxBytes=0xfffff, backupCount=5
)  # 1 Mio - 1 o, 5 old log files
_log_handler.setLevel(logging.DEBUG)

logger = logging.Logger("logger")

_format = logging.Formatter(
    '%(levelname)s: %(thread)d: %(asctime)s: %(message)s'
)
_log_handler.setFormatter(_format)
logger.addHandler(_log_handler)
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setLevel(logging.DEBUG)
logger.addHandler(_stdout_handler)
logger.debug("Logger setup")
