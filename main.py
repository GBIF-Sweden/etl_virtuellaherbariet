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
    logger = logging.getLogger("etl_virtuellaherbariet")
    logger.info("Running action '%s' for config: %s", action, config_path)
    config = load_config(config_path)
    inst_code = config.get("herbarium")
    if not inst_code:
        raise ValueError("'herbarium' not found in config.")

    download_dir = config.get("downloadDir", "data/verbatim")
    os.makedirs(download_dir, exist_ok=True)
    csv_filepath = os.path.join(download_dir, f"{inst_code.upper()}.csv")
    payload = {
        "format": "csv",
        "filters": [{"variabel": "instcode", "varde": inst_code, "typ": "="}],
    }

    if action in ["download", "all"]:
        page_size = int(config.get("downloadPageSize", 5000))
        max_pages = int(config.get("downloadMaxPages", 10000))
        logger.info("Starting download for herbarium '%s'...", inst_code)
        download_csv(url, payload, csv_filepath, page_size=page_size, max_pages=max_pages)
        logger.info("Download completed for herbarium=%s", inst_code)

    if action in ["process", "all"]:
        logger.info("Starting processing for herbarium '%s' from %s", inst_code, csv_filepath)
        process_csv(config, csv_filepath, strict=strict, config_path=config_path, action=action)
        logger.info("Process completed for herbarium=%s", inst_code)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Download and process data from Virtuella Herbariet.",
    )
    parser.add_argument("--config", required=True, nargs="+", help="Path to configuration file(s)")
    parser.add_argument("--action", choices=["download", "process", "all"], default="all")
    parser.add_argument("--strict", action="store_true", help="Fail if malformed rows or dropped duplicates are non-zero")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    logger = setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    overall_success = True

    for config_path in args.config:
        try:
            run_pipeline(config_path=config_path, action=args.action, strict=args.strict, url=URL)
        except ConfigError as e:
            logger.error("Configuration error for %s: %s", config_path, e, exc_info=True)
            overall_success = False
            continue
        except Exception as e:
            logger.error("Error processing config %s: %s", config_path, e, exc_info=True)
            overall_success = False
            continue

    if not overall_success:
        sys.exit(1)
    logger.info("ETL process completed successfully!")


if __name__ == "__main__":
    main()
