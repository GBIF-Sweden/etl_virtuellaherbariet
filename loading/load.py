import logging
import os
import random
import time
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker


def save_to_database(df: pd.DataFrame, config: dict[str, Any], inst_code: str) -> None:
    logger = logging.getLogger("etl_virtuellaherbariet")

    load_cfg = config.get("load", {})
    if not load_cfg:
        load_cfg = config.get("database", {})

    write_flag = bool(load_cfg.get("write_to_db", load_cfg.get("writeToDatabase", False)))
    if not write_flag:
        logger.info("Database write is disabled; skipping.")
        return

    host = os.getenv("ETL_DB_HOST") or load_cfg.get("database_hostname")
    port_env = os.getenv("ETL_DB_PORT")
    port = int(port_env) if port_env else int(load_cfg.get("database_port", 3306))
    dbname = os.getenv("ETL_DB_NAME") or load_cfg.get("database_name") or load_cfg.get("dbname")
    user = os.getenv("ETL_DB_USER")
    password = os.getenv("ETL_DB_PASSWORD")

    if not all([host, dbname, user, password]):
        logger.error(
            "Missing database connection details (host=%s, db=%s, user=%s, pwd=%s)",
            host,
            dbname,
            user,
            "SET" if password else "MISSING",
        )
        raise KeyError(
            "Missing database credentials. Set ETL_DB_USER and ETL_DB_PASSWORD environment variables. "
            "Host and DB Name can be in config or env."
        )

    table_name = load_cfg.get("database_table") or load_cfg.get("table") or f"{inst_code.lower()}_records"
    pk = load_cfg.get("database_table_pk_column") or load_cfg.get("pk_column")
    write_mode = load_cfg.get("database_mode") or load_cfg.get("mode", "ignore")
    batch_size = int(load_cfg.get("database_batch_size") or load_cfg.get("batch_size", 1000))
    db_max_retries = int(load_cfg.get("database_max_retries", 3))
    db_retry_initial_backoff = float(load_cfg.get("database_retry_initial_backoff_seconds", 1.0))
    db_retry_max_backoff = float(load_cfg.get("database_retry_max_backoff_seconds", 10.0))

    if write_mode not in {"ignore", "upsert"}:
        raise ValueError("database_mode must be 'ignore' or 'upsert'")

    connection_url = URL.create(
        drivername="mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=port,
        database=dbname,
        query={"charset": "utf8mb4"},
    )

    engine = create_engine(
        connection_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=30,
        future=True,
        connect_args={"connect_timeout": 10},
    )
    # Batch processing will be added in the next micro-commit.
    engine.dispose()
