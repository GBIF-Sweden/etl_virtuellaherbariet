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
    session_cls = sessionmaker(bind=engine, future=True)

    try:
        with session_cls() as session:
            table = Table(table_name, MetaData(), autoload_with=engine)
            table_cols = {c.name for c in table.c}
            keep_cols = [c for c in df.columns if c in table_cols]
            df_filtered = df[keep_cols].copy().replace({np.nan: None})

            total_rows = len(df_filtered)
            logger.info(
                "Writing to MySQL host=%s db=%s table=%s rows=%s batch_size=%s cols=%s mode=%s",
                host,
                dbname,
                table_name,
                f"{total_rows:,}",
                batch_size,
                len(keep_cols),
                write_mode,
            )

            if pk and pk in df_filtered.columns:
                unique_pk = df_filtered[pk].nunique(dropna=True)
                logger.info("Unique %s values: %s", pk, f"{unique_pk:,}")
                logger.info("Duplicate %s rows: %s", pk, f"{(total_rows - unique_pk):,}")

            for start in range(0, total_rows, batch_size):
                end = min(start + batch_size, total_rows)
                records = df_filtered.iloc[start:end].to_dict(orient="records")
                if not records:
                    continue

                attempt = 0
                backoff = max(0.1, db_retry_initial_backoff)
                while True:
                    try:
                        ins = mysql_insert(table).values(records)
                        if write_mode == "ignore":
                            stmt = ins.prefix_with("IGNORE")
                        else:
                            excluded = {pk} if pk else set()
                            update_cols = {c.name: ins.inserted[c.name] for c in table.c if c.name not in excluded}
                            stmt = ins.on_duplicate_key_update(**update_cols)

                        result = session.execute(stmt)
                        session.commit()
                        logger.info("Batch %s:%s rowcount=%s", start, end, getattr(result, "rowcount", None))

                        warns = session.execute(text("SHOW WARNINGS")).fetchall()
                        if warns:
                            logger.warning("Batch %s:%s warnings (up to 10): %s", start, end, warns[:10])
                        break
                    except SQLAlchemyError as e:
                        session.rollback()
                        attempt += 1
                        if attempt >= db_max_retries:
                            logger.error(
                                "Error in batch rows %s:%s after %s attempts: %s",
                                start,
                                end,
                                db_max_retries,
                                e,
                                exc_info=True,
                            )
                            raise
                        sleep_time = min(backoff, db_retry_max_backoff) + random.uniform(0, 0.5)
                        logger.warning(
                            "DB batch %s:%s failed (attempt %s/%s). Retrying in %.1fs: %s",
                            start,
                            end,
                            attempt,
                            db_max_retries,
                            sleep_time,
                            e,
                        )
                        time.sleep(sleep_time)
                        backoff = min(backoff * 2, db_retry_max_backoff)
    finally:
        engine.dispose()


def save_to_csv(df: pd.DataFrame, processed_dir: str, filename: str = "occurrence.txt", mode: str = "w", header: bool = True) -> None:
    logger = logging.getLogger("etl_virtuellaherbariet")
    os.makedirs(processed_dir, exist_ok=True)
    outfile = os.path.join(processed_dir, filename)
    try:
        logger.info("Writing processed data to: %s", outfile)
        df.to_csv(
            outfile,
            mode=mode,
            header=header,
            index=False,
            encoding="utf-8",
            sep="\t",
            lineterminator="\n",
        )
        logger.info("Processed CSV saved successfully (%s bytes)", f"{os.path.getsize(outfile):,}")
    except Exception as e:
        logger.error("Error writing CSV file: %s", e, exc_info=True)
        raise
