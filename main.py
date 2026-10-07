import sys
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Internal Modules
from core.logger import setup_logger
from core.client import ZwiftPowerClient, CookieExpiredError
from core.pipeline import DataPipeline
from database.engine import engine, init_db, psql_insert_do_nothing
from database.models import RiderEvent, RiderProfile
from scripts.cookie_refresher import refresh_zwiftpower_cookies

# Initialize logger globally for the main orchestrator
logger = setup_logger(log_dir="logs", days_to_keep=30)

def load_target_zids(filepath: str = "zids.txt") -> list[int]:
    """Reads target IDs from a text file, filtering out empty lines."""
    try:
        with open(filepath, 'r') as file:
            return [int(line.strip()) for line in file if line.strip()]
    except FileNotFoundError:
        logger.error(f"Target list '{filepath}' not found. Exiting.")
        sys.exit(1)

def verify_authentication(client: ZwiftPowerClient) -> None:
    """Checks session validity and attempts Playwright failover if expired."""
    try:
        client.verify_session()
    except CookieExpiredError:
        logger.warning("Expired cookies detected. Executing auto-refresh...")
        if refresh_zwiftpower_cookies(".env"):
            load_dotenv(".env", override=True)
            client.authenticate()
            client.verify_session()
        else:
            logger.error("Cookie refresh failed. Stopping execution to prevent invalid exports.")
            sys.exit(1)

def export_events_to_db(df_events: pd.DataFrame) -> None:
    """Filters valid events and chunks them into PostgreSQL."""
    model_columns = [c.name for c in RiderEvent.__table__.columns]
    valid_cols = [col for col in model_columns if col in df_events.columns]
    
    df_filtered = df_events[valid_cols].replace(r'^\s*$', np.nan, regex=True)
    df_filtered = df_filtered.dropna(subset=['zid', 'res_id'])
    
    logger.info(f"Exporting {len(df_filtered)} event rows to PostgreSQL...")
    for i in range(0, len(df_filtered), 100):
        chunk = df_filtered.iloc[i : i + 100]
        chunk.to_sql(
            name="rider_events",
            con=engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing 
        )

def export_profiles_to_db(df_profiles: pd.DataFrame) -> None:
    """Filters valid profiles and inserts them into PostgreSQL."""
    model_columns = [c.name for c in RiderProfile.__table__.columns if c.name != 'id']
    valid_cols = [col for col in model_columns if col in df_profiles.columns]
    
    df_filtered = df_profiles[valid_cols].replace(r'^\s*$', np.nan, regex=True)
    df_filtered = df_filtered.dropna(subset=['zid', 'fetched_at'])
    
    logger.info(f"Exporting {len(df_filtered)} profile rows to PostgreSQL...")
    df_filtered.to_sql(
        name="rider_profiles",
        con=engine,
        if_exists="append",
        index=False,
        method=psql_insert_do_nothing
    )

def run_nightly_pipeline():
    logger.info("Starting nightly Zwift data pipeline...")
    
    # Setup
    load_dotenv()
    init_db()
    target_zids = load_target_zids()
    
    # Authenticate
    client = ZwiftPowerClient()
    verify_authentication(client)

    # 1. Extract
    logger.info(f"Extracting data for {len(target_zids)} riders...")
    raw_profiles = client.get_profiles(target_zids)
    raw_events = client.get_event_histories(target_zids)
    
    # Validate profile scrape
    expected_cols = ['zid', 'cat', 'racing_score', 'zpoints', 'country', 'team', 'zftp', 'weight', 'age']
    if any(col not in raw_profiles.columns for col in expected_cols):
        logger.error("Profile scraping returned incomplete data. Potential structural change on ZwiftPower.")
        sys.exit(1)

    # 2. Transform
    if "zpoints" in raw_profiles.columns:
        raw_profiles["zpoints"] = raw_profiles["zpoints"].astype(str).str.replace(",", "")
        
    df_profiles_clean = DataPipeline.clean_numeric_columns(raw_profiles, ["weight", "zftp", "zpoints", "racing_score"])
    df_profiles_clean["fetched_at"] = pd.Timestamp.now()
    
    df_events_unpacked = DataPipeline.unpack_list_columns(raw_events)
    df_events_clean = DataPipeline.format_event_dates(df_events_unpacked, date_column="event_date")

    # 3. Load
    export_events_to_db(df_events_clean)
    export_profiles_to_db(df_profiles_clean)
    
    logger.info("Nightly pipeline completed successfully.")

if __name__ == "__main__":
    run_nightly_pipeline()