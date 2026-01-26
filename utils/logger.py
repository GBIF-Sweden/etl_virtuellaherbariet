import logging
import os
from datetime import datetime


class VerboseFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def formatTime(self, record, datefmt=None):
        base = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        millis = int(record.msecs)
        return f"{base},{millis:03d}"


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"etl_{timestamp}.log")

    formatter = VerboseFormatter()

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger("etl_virtuellaherbariet")
    if logger.handlers:
        logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
