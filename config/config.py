import logging

import yaml


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""


def validate_config(config):
    required_fields = ["herbarium", "mappings"]
    for field in required_fields:
        if field not in config:
            return False, f"Missing required field: {field}"

    herbarium = config.get("herbarium")
    if not isinstance(herbarium, str) or not herbarium.strip():
        return False, "Field 'herbarium' must be a non-empty string"

    mappings = config.get("mappings")
    if not isinstance(mappings, dict):
        return False, "Field 'mappings' must be a dictionary"
    if not mappings:
        return False, "Field 'mappings' cannot be empty"
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in mappings.items()):
        return False, "All mapping keys and values must be strings"

    chunk_size = config.get("chunkSize", 50000)
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        return False, "Field 'chunkSize' must be a positive integer"

    download_page_size = config.get("downloadPageSize", 5000)
    if not isinstance(download_page_size, int) or download_page_size <= 0:
        return False, "Field 'downloadPageSize' must be a positive integer"

    download_max_pages = config.get("downloadMaxPages", 10000)
    if not isinstance(download_max_pages, int) or download_max_pages <= 0:
        return False, "Field 'downloadMaxPages' must be a positive integer"

    download_dir = config.get("downloadDir", "data/verbatim")
    if not isinstance(download_dir, str) or not download_dir.strip():
        return False, "Field 'downloadDir' must be a non-empty string"

    processed_dir = config.get("processedDir", "data/processed")
    if not isinstance(processed_dir, str) or not processed_dir.strip():
        return False, "Field 'processedDir' must be a non-empty string"

    csv_settings = config.get("csv_settings", {})
    if not isinstance(csv_settings, dict):
        return False, "Field 'csv_settings' must be a dictionary"

    defaults = config.get("defaults", {})
    if not isinstance(defaults, dict):
        return False, "Field 'defaults' must be a dictionary"
    if not all(isinstance(k, str) for k in defaults.keys()):
        return False, "All default keys must be strings"

    transformations = config.get("transformations", [])
    if not isinstance(transformations, list):
        return False, "Field 'transformations' must be a list"
    allowed_types = {"construct_url", "copy_column", "combine_columns"}
    for idx, transform in enumerate(transformations):
        if not isinstance(transform, dict):
            return False, f"Transformation at index {idx} must be an object"
        t_type = transform.get("type")
        col = transform.get("column")
        if t_type not in allowed_types:
            return False, f"Transformation at index {idx} has invalid type '{t_type}'"
        if not isinstance(col, str) or not col:
            return False, f"Transformation at index {idx} must define non-empty 'column'"
        if t_type == "copy_column" and not isinstance(transform.get("source"), str):
            return False, f"copy_column transformation at index {idx} must define string 'source'"
        if t_type == "combine_columns":
            cols = transform.get("columns")
            if not isinstance(cols, list) or not cols or not all(isinstance(c, str) for c in cols):
                return False, f"combine_columns transformation at index {idx} must define non-empty string list 'columns'"

    database = config.get("database")
    if database is not None and not isinstance(database, dict):
        return False, "Field 'database' must be an object"

    load_cfg = config.get("load", {})
    if not isinstance(load_cfg, dict):
        return False, "Field 'load' must be an object"

    write_flag = load_cfg.get("write_to_db", False)
    if not isinstance(write_flag, bool):
        if database and "writeToDatabase" in database:
            write_flag = database.get("writeToDatabase", False)
        else:
            return False, "Field 'load.write_to_db' must be a boolean"

    db_mode = load_cfg.get("database_mode", "ignore")
    if db_mode not in {"ignore", "upsert"}:
        return False, "load.database_mode must be 'ignore' or 'upsert'"

    duplicate_policy = (
        load_cfg.get("duplicatePolicy")
        or (database.get("duplicatePolicy") if isinstance(database, dict) else None)
        or "keep_first"
    )
    if duplicate_policy not in {"drop_all_duplicates", "keep_first", "keep_last", "write_only"}:
        return False, (
            "duplicatePolicy must be one of: "
            "drop_all_duplicates, keep_first, keep_last, write_only"
        )

    if isinstance(database, dict) and "mode" in database:
        legacy_mode = database.get("mode")
        if legacy_mode not in {"ignore", "upsert"}:
            return False, "database.mode must be 'ignore' or 'upsert'"

    if write_flag:
        pass

    return True, None
