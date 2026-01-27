import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from config import ConfigError, load_config
from extraction import download_csv
from pipeline import process_csv
from utils import setup_logging

URL = "https://api.virtuellaherbariet.se/vhapi/data/export"


def run_pipeline(config_path: str, action: str, strict: bool = False, url: str = URL) -> None:
    """Coordinate the download and processing of herbarium data."""
    logger = logging.getLogger("etl_virtuellaherbariet")
    # Implementation will be added in the next micro-commit.
