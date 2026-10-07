import pandas as pd
import logging

# Initialize a standard logger for this module
logger = logging.getLogger(__name__)

class DataPipeline:

    @staticmethod
    def unpack_list_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Detects and extracts the primary item from list/tuple cells like ['218', 0]."""
        if df.empty:
            return df
        df_clean = df.copy()

        for col in df_clean.columns:
            valid_series = df_clean[col].dropna()
            if not valid_series.empty and isinstance(
                valid_series.iloc[0], (list, tuple)
            ):
                df_clean[col] = df_clean[col].apply(
                    lambda x: (
                        x[0] if isinstance(x, (list, tuple)) and len(x) > 0 else x
                    )
                )
                df_clean[col] = pd.to_numeric(df_clean[col], errors="ignore")

        return df_clean

    @staticmethod
    def clean_numeric_columns(
        df: pd.DataFrame, columns: list[str]
    ) -> pd.DataFrame:
        """Extracts float numbers from string values (e.g., '67.4 kg' -> 67.4)."""
        if df.empty:
            return df
        df_clean = df.copy()
        for col in columns:
            if col in df_clean.columns:
                df_clean[col] = (
                    df_clean[col]
                    .astype(str)
                    .str.extract(r"([-+]?\d*\.?\d+)", expand=False)
                    .astype(float)
                )
        return df_clean

    @staticmethod
    def format_event_dates(
        df: pd.DataFrame, date_column: str = "event_date"
    ) -> pd.DataFrame:
        """Converts Unix timestamps to YYYY/MM/DD date format and sorts descending."""
        if df.empty:
            return df
        df_clean = df.copy()
        if date_column in df_clean.columns:
            df_clean[date_column] = pd.to_datetime(
                pd.to_numeric(df_clean[date_column], errors="coerce"), unit="s"
            )
            df_clean = df_clean.sort_values(by=date_column, ascending=False)

        return df_clean
