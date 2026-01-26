import logging

import pandas as pd


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(lambda x: x.replace("\x00", "") if isinstance(x, str) else x)
    return df
