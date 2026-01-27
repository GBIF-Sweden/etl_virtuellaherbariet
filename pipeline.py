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

    defaults = config.get("defaults", {})
    seen_ids = set()
    total_input = total_missing_pk = total_duplicates = total_output = 0
    duplicate_keys = 0
    duplicate_policy = (
        config.get("load", {}).get("duplicatePolicy")
        or config.get("database", {}).get("duplicatePolicy")
        or "keep_first"
    )
    wrote_output_header = wrote_duplicates_header = False

    reader = pd.read_csv(csv_file_to_read, chunksize=chunk_size, **read_kwargs)
    for chunk_idx, df in enumerate(reader, start=1):
        logger.info("Processing chunk %s with %s rows", chunk_idx, len(df))
        logger.info("Extracted %s rows from source file.", len(df))
        total_input += len(df)

        if raw_pk_column in df.columns:
            normalized_key = df[raw_pk_column].astype(str).str.strip()
            missing_mask = df[raw_pk_column].isna() | (normalized_key == "")
            total_missing_pk += int(missing_mask.sum())
            df = df[~missing_mask].copy()

        if df.empty:
            continue

        if mappings:
            df.rename(columns=mappings, inplace=True)
        if defaults:
            for col, val in defaults.items():
                df[col] = val
        df = apply_transformations(df, config)

        pk_col = "occurrenceID" if "occurrenceID" in df.columns else "catalogNumber"
        if pk_col in df.columns:
            normalized_id = df[pk_col].astype(str).str.strip().str.lower()
            duplicate_mask_any = normalized_id.duplicated(keep=False) | normalized_id.isin(seen_ids)
            duplicate_rows = df[duplicate_mask_any]
            if not duplicate_rows.empty:
                total_duplicates += int(len(duplicate_rows))
                duplicate_keys += int(normalized_id[duplicate_mask_any].nunique())
                duplicate_rows.to_csv(
                    duplicates_path,
                    mode="a",
                    header=not wrote_duplicates_header,
                    index=False,
                    encoding="utf-8",
                    sep="\t",
                )
                wrote_duplicates_header = True
                logger.info("Wrote %s duplicate rows to %s.", len(duplicate_rows), duplicates_path)

            if duplicate_policy == "drop_all_duplicates":
                duplicate_values = set(normalized_id[duplicate_mask_any].tolist())
                kept_mask = ~normalized_id.isin(duplicate_values)
                df = df[kept_mask].copy()
                normalized_id = normalized_id[kept_mask]
            elif duplicate_policy == "keep_first":
                kept_mask = ~(normalized_id.duplicated(keep="first") | normalized_id.isin(seen_ids))
                df = df[kept_mask].copy()
                normalized_id = normalized_id[kept_mask]
            elif duplicate_policy == "keep_last":
                kept_mask = ~(normalized_id.duplicated(keep="last") | normalized_id.isin(seen_ids))
                df = df[kept_mask].copy()
                normalized_id = normalized_id[kept_mask]
            elif duplicate_policy == "write_only":
                kept_mask = pd.Series([True] * len(df), index=df.index)
            else:
                raise ValueError(
                    "duplicatePolicy must be one of: drop_all_duplicates, keep_first, keep_last, write_only"
                )

            seen_ids.update(normalized_id.tolist())

        if df.empty:
            continue

        if "occurrenceID" in df.columns:
            cols = ["occurrenceID"] + [c for c in df.columns if c != "occurrenceID"]
            df = df[cols]

        df = clean_dataframe(df)
        logger.info("Number of rows after transformation: %s.", len(df))
        logger.info("Number of columns after transformation: %s.", len(df.columns))
        save_to_csv(df, processed_dir, filename=output_file, mode="a", header=not wrote_output_header)
        wrote_output_header = True
        save_to_database(df, config, inst_code)
        total_output += len(df)

    logger.info("Successfully read %s, %s rows.", csv_file, total_input)
    logger.info("Combined DataFrame created with %s rows.", total_input)

    quality_report = {
        "herbarium": inst_code,
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": round(time.time() - start_time, 2),
        "extraction": {
            "input_rows_after_repair": total_input,
            "repaired_rows_total": repaired_count,
            "malformed_rows_total": malformed_count,
            "too_short_rows": int(preprocess_stats.get("too_short_rows", 0)),
            "too_long_rows": int(preprocess_stats.get("too_long_rows", 0)),
            "malformed_file": preprocess_stats.get("malformed_file"),
        },
        "transformation": {
            "duplicates": {
                "policy": duplicate_policy,
                "duplicate_rows_detected": total_duplicates,
                "duplicate_keys": duplicate_keys,
                "duplicate_rows_dropped": int(total_input - total_missing_pk - total_output),
                "duplicates_file": duplicates_path if wrote_duplicates_header else None,
            },
        },
        "output": {
            "total_input_rows": total_input,
            "total_output_rows": total_output,
            "missing_primary_key_rows": total_missing_pk,
        },
        "status": "success",
    }

    report_path_run = os.path.join(processed_dir, f"quality_report_{inst_code.lower()}_{run_id}.json")
    report_path_latest = os.path.join(processed_dir, f"quality_report_{inst_code.lower()}.json")
    for p in (report_path_run, report_path_latest):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2)
    logger.info("Wrote quality reports: %s and %s", report_path_run, report_path_latest)

    output_checksum_sha256 = None
    if os.path.exists(output_path):
        h = hashlib.sha256()
        with open(output_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        output_checksum_sha256 = h.hexdigest()

    reconciliation = {
        "herbarium": inst_code,
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "input_csv": csv_file,
        "output_csv": output_path,
        "output_checksum_sha256": output_checksum_sha256,
        "row_counts": {
            "total_input_rows": total_input,
            "missing_primary_key_rows": total_missing_pk,
            "duplicate_rows_detected": total_duplicates,
            "duplicate_rows_dropped": quality_report["transformation"]["duplicates"]["duplicate_rows_dropped"],
            "total_output_rows": total_output,
        },
        "status": quality_report["status"],
    }
    reconcile_run = os.path.join(processed_dir, f"reconciliation_{inst_code.lower()}_{run_id}.json")
    reconcile_latest = os.path.join(processed_dir, f"reconciliation_{inst_code.lower()}.json")
    for p in (reconcile_run, reconcile_latest):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(reconciliation, f, indent=2)
    logger.info("Wrote reconciliation reports: %s and %s", reconcile_run, reconcile_latest)

    if strict and (malformed_count > 0 or quality_report["transformation"]["duplicates"]["duplicate_rows_dropped"] > 0):
        error_msg = (
            "STRICT MODE FAILURE: "
            f"{malformed_count} malformed rows, "
            f"{quality_report['transformation']['duplicates']['duplicate_rows_dropped']} duplicate rows dropped."
        )
        quality_report["status"] = "failed"
        quality_report["error"] = error_msg
        reconciliation["status"] = "failed"
        reconciliation["error"] = error_msg
        for p in (report_path_run, report_path_latest):
            with open(p, "w", encoding="utf-8") as f:
                json.dump(quality_report, f, indent=2)
        for p in (reconcile_run, reconcile_latest):
            with open(p, "w", encoding="utf-8") as f:
                json.dump(reconciliation, f, indent=2)
        raise ValueError(error_msg)
    if strict and repaired_count > 0:
        logger.warning("Strict mode warning: repaired_rows_total=%s (allowed).", repaired_count)

    logger.info(
        "SUMMARY config=%s action=%s repaired=%s malformed=%s dup_detected=%s dup_dropped=%s report=%s",
        config_path or "n/a",
        action,
        repaired_count,
        malformed_count,
        total_duplicates,
        quality_report["transformation"]["duplicates"]["duplicate_rows_dropped"],
        report_path_run,
    )
    logger.info("ETL process completed successfully for herbarium=%s run_id=%s", inst_code, run_id)
