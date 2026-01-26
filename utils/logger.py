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
