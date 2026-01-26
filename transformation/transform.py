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
        # Other transformation types will be added in the next micro-commit.

    return df
