import logging

import pandas as pd


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(lambda x: x.replace("\x00", "") if isinstance(x, str) else x)
    return df


def apply_transformations(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    logger = logging.getLogger("etl_virtuellaherbariet")
    transformations = config.get("transformations", [])

    for transform in transformations:
        col = transform.get("column")
        t_type = transform.get("type")
        logger.info("Running Transformation function %s", t_type)

        if t_type == "construct_url":
            if col not in df.columns:
                continue
            prefix = transform.get("prefix", "")
            suffix = transform.get("suffix", "")
            logger.info("Applying URL construction to column: %s", col)

            def construct_url(val):
                if pd.isna(val) or val == "":
                    return val
                return f"{prefix}{val}{suffix}"

            df[col] = df[col].apply(construct_url)

        elif t_type == "copy_column":
            source = transform.get("source")
            if source in df.columns:
                logger.info("Copying column %s to %s", source, col)
                df[col] = df[source]
            else:
                logger.warning("Source column %s not found for copy_column transformation.", source)

        elif t_type == "combine_columns":
            columns = transform.get("columns", [])
            separator = transform.get("separator", "")
            logger.info("Combining columns %s to %s", columns, col)
            valid_cols = [c for c in columns if c in df.columns]
            if len(valid_cols) != len(columns):
                logger.warning("Some columns in %s not found. Using %s", columns, valid_cols)
            if valid_cols:
                df[col] = df[valid_cols].astype(str).agg(separator.join, axis=1)
        else:
            logger.info("Transformation function %s not found. Skipping.", t_type)

    return df
