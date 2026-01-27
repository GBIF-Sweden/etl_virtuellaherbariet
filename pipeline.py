import csv
import hashlib
import json
import logging
import os
import time
from datetime import datetime

import pandas as pd

from loading import save_to_csv, save_to_database
from transformation import apply_transformations, clean_dataframe


def preprocess_csv(csv_file, inst_code, malformed_dir="data/malformed"):
    logger = logging.getLogger("etl_virtuellaherbariet")

    clean_file = csv_file.replace(".csv", "_clean.csv")
    os.makedirs(malformed_dir, exist_ok=True)
    malformed_file = os.path.join(malformed_dir, f"{inst_code.upper()}_malformed.csv")

    malformed_count = 0
    repaired_count = 0
    too_short_rows = 0
    too_long_rows = 0
    f_malformed = None
    malformed_writer = None
    csv.field_size_limit(10_000_000)

    try:
        with open(csv_file, "r", encoding="utf-8", newline="") as fin:
            reader = csv.reader(fin, delimiter=",", quotechar='"', doublequote=True)
            header = next(reader, None)
            if not header:
                logger.warning("File %s is empty.", csv_file)
                return csv_file, 0

            expected_count = len(header)
            logger.info("Preprocessing %s. Expected columns: %s", csv_file, expected_count)

            with open(clean_file, "w", encoding="utf-8", newline="") as f_clean:
                clean_writer = csv.writer(f_clean, delimiter=",", quotechar='"', doublequote=True)
                clean_writer.writerow(header)

                for row in reader:
                    row = [
                        (v.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ").strip())
                        if isinstance(v, str)
                        else v
                        for v in row
                    ]

                    if len(row) == expected_count:
                        clean_writer.writerow(row)
                    else:
                        # Repair rows that are one of the known exporter shape issues.
                        if len(row) > expected_count:
                            too_long_rows += 1
                            base = row[:expected_count]
                            extras = [v for v in row[expected_count:] if str(v).strip()]
                            if extras:
                                merged_extras = " | ".join(str(v).strip() for v in extras)
                                base[-1] = f"{base[-1]} | {merged_extras}" if str(base[-1]).strip() else merged_extras
                            clean_writer.writerow(base)
                            repaired_count += 1
                            continue

                        if len(row) < expected_count:
                            too_short_rows += 1
                            padded = row + ([""] * (expected_count - len(row)))
                            clean_writer.writerow(padded)
                            repaired_count += 1
                            continue

                        if f_malformed is None:
                            f_malformed = open(malformed_file, "w", encoding="utf-8", newline="")
                            malformed_writer = csv.writer(f_malformed, delimiter=",", quotechar='"', doublequote=True)
                            malformed_writer.writerow(header)
                        malformed_writer.writerow(row)
                        malformed_count += 1

        if f_malformed:
            f_malformed.close()
        elif os.path.exists(malformed_file):
            os.remove(malformed_file)

        if malformed_count == 0 and repaired_count == 0:
            logger.info("Preprocessing complete. No malformed rows found.")
        else:
            logger.info(
                "Preprocessing complete. repaired=%s malformed=%s malformed_file=%s",
                repaired_count,
                malformed_count,
                malformed_file,
            )
        return clean_file, {
            "malformed_rows": malformed_count,
            "repaired_rows": repaired_count,
            "too_short_rows": too_short_rows,
            "too_long_rows": too_long_rows,
            "malformed_file": malformed_file if malformed_count > 0 else None,
        }

    except csv.Error as e:
        logger.error("CSV parse error: %s", e, exc_info=True)
        return csv_file, {
            "malformed_rows": 0,
            "repaired_rows": 0,
            "too_short_rows": 0,
            "too_long_rows": 0,
            "malformed_file": None,
        }
    except Exception as e:
        logger.error("Error preprocessing CSV: %s", e, exc_info=True)
        return csv_file, {
            "malformed_rows": 0,
            "repaired_rows": 0,
            "too_short_rows": 0,
            "too_long_rows": 0,
            "malformed_file": None,
        }
    finally:
        if f_malformed and not f_malformed.closed:
            f_malformed.close()


def process_csv(config, csv_file, strict=False, config_path=None, action="process"):
    logger = logging.getLogger("etl_virtuellaherbariet")
    inst_code = config.get("herbarium")
    processed_dir = config.get("processedDir", "data/processed")
    chunk_size = int(config.get("chunkSize", 50000))
    csv_settings = config.get("csv_settings", {})

    if not inst_code:
        raise ValueError("'herbarium' not found in config.")
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    start_time = time.time()
    logger.info("Process run started. herbarium=%s run_id=%s strict=%s", inst_code, run_id, strict)

    csv_file_to_read, preprocess_stats = preprocess_csv(csv_file, inst_code)
    malformed_count = int(preprocess_stats.get("malformed_rows", 0))
    repaired_count = int(preprocess_stats.get("repaired_rows", 0))
    if repaired_count > 0:
        logger.info("Repaired %s structurally inconsistent rows in %s.", repaired_count, csv_file)
    read_kwargs = {
        "encoding": "utf-8",
        "low_memory": False,
        "dtype": str,
        "sep": ",",
        "quotechar": '"',
    }
    if csv_settings:
        read_kwargs.update(csv_settings)
    if chunk_size <= 0:
        raise ValueError("chunkSize must be a positive integer")
    logger.info("CSV read settings: %s", read_kwargs)
    logger.info("Chunk size: %s", chunk_size)

    mappings = config.get("mappings", {})
    raw_pk_column = "catalogNumber"
    for source, target in mappings.items():
        if target == "catalogNumber":
            raw_pk_column = source
            break

    os.makedirs(processed_dir, exist_ok=True)
    output_file = f"dwc_{inst_code.lower()}.csv"
    output_path = os.path.join(processed_dir, output_file)
    duplicates_path = os.path.join(processed_dir, f"duplicates_{inst_code.lower()}.csv")
    for f in (output_path, duplicates_path):
        if os.path.exists(f):
            os.remove(f)

    # Main chunking loop implementation will follow in the next micro-commit.
    return True
