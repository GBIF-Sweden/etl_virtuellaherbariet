import logging
import os
from datetime import datetime


class VerboseFormatter(logging.Formatter):
    """Custom formatter for the ETL pipeline."""
