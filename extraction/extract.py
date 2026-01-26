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
    logger = logging.getLogger("etl_virtuellaherbariet")

    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be greater than zero when provided")

    filters = payload.get("filters", [])
    if not isinstance(filters, list):
        raise ValueError("payload.filters must be a list")

    base_filters = [f for f in filters if f.get("variabel") not in ("take", "skip")]

    retryable_statuses = {429, 500, 502, 503, 504}
    logger.info("Starting download to %s", output_file)

    with requests.Session() as session:
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")

            header_written = False
            page_number = 1
            offset = 0
            total_data_rows = 0

            while True:
                if max_pages is not None and page_number > max_pages:
                    raise RuntimeError(
                        f"Reached max_pages={max_pages} without a terminating page. "
                        "Aborting to prevent an infinite download loop."
                    )
                logger.info("Attempting to download page %s...", page_number)
                page_rows = _download_page_with_retry(
                    session=session,
                    url=url,
                    payload=payload,
                    base_filters=base_filters,
                    offset=offset,
                    page_size=page_size,
                    max_retries=max_retries,
                    connect_timeout=connect_timeout,
                    read_timeout=read_timeout,
                    initial_backoff_seconds=initial_backoff_seconds,
                    max_backoff_seconds=max_backoff_seconds,
                    retryable_statuses=retryable_statuses,
                    logger=logger,
                )
                if not page_rows:
                    logger.info("No more valid files found after page %s.", page_number - 1)
                    break

                data_rows, header_written = _write_page_rows(
                    writer=writer,
                    page_rows=page_rows,
                    header_written=header_written,
                )
                if data_rows <= 0:
                    logger.info("No more valid files found after page %s.", page_number - 1)
                    break

                total_data_rows += data_rows

                if data_rows != page_size:
                    if data_rows > page_size:
                        logger.info(
                            "Received %s rows on page %s with take=%s; assuming API returned all remaining data in one response.",
                            data_rows,
                            page_number,
                            page_size,
                        )
                    logger.info("No more valid files found after page %s.", page_number)
                    break

                offset += page_size
                page_number += 1

    logger.info("Download complete: %s records saved to %s", f"{total_data_rows:,}", output_file)


def _download_page_with_retry(*args, **kwargs):
    """Stub for the next micro-commit."""
    return []


def _write_page_rows(*args, **kwargs):
    """Stub for the next micro-commit."""
    return 0, False
