import csv
import io
import logging
import random
import time
from typing import Any

import requests
import urllib3


def download_csv(
    url: str,
    payload: dict,
    output_file: str,
    page_size: int = 5000,
    max_pages: int | None = 10000,
    max_retries: int = 5,
    connect_timeout: int = 10,
    read_timeout: int = 120,
    initial_backoff_seconds: float = 2.0,
    max_backoff_seconds: float = 30.0,
) -> None:
    """Download data from API in CSV format with pagination and retries."""
