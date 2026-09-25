from typing import Iterable
import schedule
import json
import logging
import os
import re
import time
from logging.handlers import TimedRotatingFileHandler
from bs4 import BeautifulSoup
from curl_cffi import requests
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from cookie_refresher import refresh_zwiftpower_cookies
from database import engine, init_db, psql_insert_do_nothing, Base,RiderEvent,RiderProfile  # Import the new DB logic

import logging
from datetime import datetime
import os

# --- Logging Configuration ---
# 1. Create the logs directory in your CasaOS mapped folder
os.makedirs("logs", exist_ok=True)

# 2. Set up a daily rotating file handler
# This automatically cuts a new log file every midnight (ready for the 2:00 AM run)
file_handler = TimedRotatingFileHandler(
    filename="logs/pipeline.log",
    when="midnight",
    interval=1,
    backupCount=30  # Automatically deletes logs older than 30 days to save server space
)
# Adds the date to the end of yesterday's file (e.g., pipeline.log.2026-09-24.txt)
file_handler.suffix = "%Y-%m-%d.txt" 

# 3. Apply handlers to both the file and the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        file_handler,
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)

load_dotenv()

class CookieExpiredError(Exception):
    """Raised when ZwiftPower cookies are missing or expired."""
    pass


class ZwiftPowerClient:
    """Headless HTTP Client for ZwiftPower using browser impersonation

    and CloudFront/phpBB cookies to bypass 403 blocks.
    """

    BASE_URL = "https://zwiftpower.com"

    def __init__(self):
        # Initialize curl_cffi session impersonating Chrome TLS fingerprint
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                ),
            }
        )
        self.authenticate()

    def authenticate(self) -> None:
        """Loads phpBB and CloudFront cookies directly from environment variables."""
        cookies = {
            "phpbb3_lswlk_sid": os.getenv("PHPBB3_SID"),
            "phpbb3_lswlk_u": os.getenv("PHPBB3_U"),
            "CloudFront-Key-Pair-Id": os.getenv("CLOUDFRONT_KEY_PAIR_ID"),
            "CloudFront-Policy": os.getenv("CLOUDFRONT_POLICY"),
            "CloudFront-Signature": os.getenv("CLOUDFRONT_SIGNATURE"),
        }

        # Filter out empty or missing environment variables
        valid_cookies = {k: v for k, v in cookies.items() if v}

        if valid_cookies:
            self.session.cookies.update(valid_cookies)
            logger.info(
                f"Successfully loaded {len(valid_cookies)} cookies into session."
            )
        else:
            logger.warning("No cookies were found in environment variables.")

    def get_profiles(self, zids: Iterable[int | str]) -> pd.DataFrame:
        """Fetches and parses HTML profile data using key-value table matching and JS regex."""
        riders_data = []

        for zid in zids:
            profile_url = f"{self.BASE_URL}/profile.php?z={zid}"

            try:
                res = self.session.get(profile_url, timeout=10)
                if res.status_code == 200:
                    # DEBUG: Save HTML to check what we're receiving
                    if zid == 1714370:  # Only save for first rider
                        with open("debug_received_html.html", "w", encoding="utf-8") as f:
                            f.write(res.text)
                        logger.info(f"DEBUG: Saved HTML for ZID {zid} to debug_received_html.html")
                        logger.info(f"DEBUG: HTML length: {len(res.text)} characters")
                        logger.info(f"DEBUG: HTML preview (first 500 chars): {res.text[:500]}")
                    
                    # Pass the raw HTML and ZID to our new parser
                    rider_info = self._parse_profile_html(res.text, zid)
                    logger.info(f"DEBUG: Parsed profile for ZID {zid}: {rider_info}")
                    riders_data.append(rider_info)
                else:
                    logger.warning(
                        f"Non-200 response for ZID {zid}: {res.status_code}"
                    )
                    riders_data.append({"zid": int(zid)})

            except Exception as e:
                logger.error(f"Error fetching profile for ZID {zid}: {str(e)}")
                riders_data.append({"zid": int(zid)})

            time.sleep(0.5)

        return pd.DataFrame(riders_data)
    
    @staticmethod
    def _parse_profile_html(html_content: str, zid: int | str) -> dict:
        """Extracts HTML table metadata and Highcharts JS power metrics into a flat dictionary."""
        soup = BeautifulSoup(html_content, "html.parser")
        data = {"zid": int(zid)}
        
        # Check if we received a login page instead of profile data
        if "Login" in html_content and "zwift_id : ''" in html_content:
            logger.error(f"Received login page for ZID {zid} - authentication failed")
            return data  # Return minimal data to trigger validation failure

        # --- 1. Parse HTML Table Data ---
        table_map = {}
        for tr in soup.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                label = th.get_text(strip=True).lower()
                table_map[label] = td
        
        # Log warning if no table data found
        if not table_map:
            logger.warning(f"No profile table data found for ZID {zid}")
        
        logger.info(f"DEBUG: Found {len(table_map)} table rows for ZID {zid}")
        logger.info(f"DEBUG: Table labels found: {list(table_map.keys())}")

        for label, td in table_map.items():
            if "category" in label:
                badge = td.find("span", class_="label-as-badge")
                data["cat"] = badge.get_text(strip=True) if badge else td.get_text(strip=True)
            elif "racing score" in label:
                data["racing_score"] = td.get_text(strip=True).split()[0]
            elif "zpoints" in label:
                b_tag = td.find("b")
                data["zpoints"] = b_tag.get_text(strip=True) if b_tag else td.get_text(strip=True)
            elif "country" in label:
                data["country"] = td.get_text(strip=True)
            elif "team" in label:
                data["team"] = td.get_text(strip=True)
            elif "zftp" in label:
                data["zftp"] = td.get_text(strip=True)
            elif "weight" in label:
                data["weight"] = td.get_text(strip=True)
            elif "age" in label:
                data["age"] = td.get_text(strip=True)

        # --- 2. Extract Power Watts & Percentiles from Inline JS ---
        duration_key_map = {
            "15 seconds": "15s",
            "1 minute": "1m",
            "5 minutes": "5m",
            "20 minutes": "20m",
        }

        # Regex matches duration, watts, and percentile (y) inside the Highcharts JS block
        js_pattern = r"<b>(15 seconds|1 minute|5 minutes|20 minutes)</b>:\s*(\d+)\s*<rsmall>watts</rsmall>.*?y:\s*([\d.]+)"
        matches = re.findall(js_pattern, html_content, re.DOTALL)

        for duration, watts, percentile in matches:
            suffix = duration_key_map.get(duration)
            if suffix:
                data[f"watts_{suffix}"] = int(watts)
                data[f"pct_{suffix}"] = float(percentile)

        return data

    def get_event_histories(self, zids: Iterable[int | str]) -> pd.DataFrame:
        """Fetches profile JSON event histories using CloudFront cookies and required AJAX headers."""
        all_frames = []

        for zid in zids:
            json_url = f"{self.BASE_URL}/cache3/profile/{zid}_all.json"

            # Mandatory AJAX and Referer headers
            headers = {
                "Referer": f"{self.BASE_URL}/profile.php?z={zid}",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }

            try:
                res = self.session.get(json_url, headers=headers, timeout=10)

                if res.status_code == 200:
                    payload = res.json()
                    data = payload.get("data", [])

                    if data:
                        df_temp = pd.DataFrame(data)
                        df_temp["query_zid"] = str(zid)
                        all_frames.append(df_temp)
                else:
                    logger.warning(
                        f"JSON cache not found for ZID {zid} (Status"
                        f" {res.status_code})"
                    )

            except json.JSONDecodeError:
                logger.error(f"Malformed JSON payload returned for ZID {zid}")
            except Exception as e:
                logger.error(
                    f"Unexpected error fetching events for ZID {zid}: {str(e)}"
                )

            time.sleep(0.5)

        if all_frames:
            return pd.concat(all_frames, ignore_index=True)
        return pd.DataFrame()

    @staticmethod
    def _extract_regex(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1) if match else None

    @staticmethod
    def _find_in_rows(rows: list, label: str) -> str | None:
        for r in rows:
            if label in r.text:
                cells = r.find_all("td")
                if len(cells) > 1:
                    return cells[1].text.strip()
        return None

    @staticmethod
    def _get_span_text(spans: list, index: int) -> str | None:
        try:
            return spans[index].text.strip()
        except IndexError:
            return None
    
    def verify_session(self) -> None:
        """Tests the cookies against a lightweight protected endpoint."""
        # Use your own ZID or a known static ZID for the test
        test_url = f"{self.BASE_URL}/cache3/profile/1714370_all.json"
        
        headers = {
            "Referer": f"{self.BASE_URL}/profile.php?z=1714370",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        }
        
        # We only need the headers to verify authentication, not the full payload
        res = self.session.head(test_url, headers=headers, timeout=5)
        
        if res.status_code == 403:
            logger.error("Session verification failed (403 Forbidden). Cookies have expired.")
            raise CookieExpiredError("ZwiftPower cookies are obsolete. Please update the .env file.")
        elif res.status_code == 200:
            logger.info("Session verified successfully. Cookies are active.")
        else:
            logger.warning(f"Unexpected status code during verification: {res.status_code}")


# --- Data Transformation & Pipeline Helpers ---


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
            df_clean[date_column] = df_clean[date_column].dt.strftime(
                "%Y/%m/%d"
            )
        return df_clean

    @staticmethod
    def export_to_csv(
        df: pd.DataFrame, filename: str, output_dir: str = "output"
    ) -> str:
        """Saves a DataFrame to CSV with proper UTF-8 encoding and folder creation."""
        if df.empty:
            logger.warning(
                f"DataFrame for '{filename}' is empty. Skipping CSV export."
            )
            return ""

        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        df.to_csv(filepath, index=False, encoding="utf-8")
        logger.info(f"Successfully exported {len(df)} rows to: {filepath}")
        return filepath


# --- Execution Entry Point ---
def run_nightly_pipeline():
    logger.info("Starting nightly Zwift data pipeline...")

    # 1. Read target_zids from the text file (reads fresh every night!)
    target_zids = []
    try:
        with open('zids.txt', 'r') as file:
            for line in file:
                clean_line = line.strip()
                if clean_line:
                    target_zids.append(int(clean_line))
    except FileNotFoundError:
        logger.error("zids.txt not found. Skipping run.")
        return

    # Initialize the database tables on startup
    init_db()

    # Initialize client
    client = ZwiftPowerClient()
    
   
    # Automatic Failover Check
    try:
        client.verify_session()
    except CookieExpiredError:
        logger.warning(
            "Expired cookies detected. Executing Playwright auto-refresh..."
        )
        success = refresh_zwiftpower_cookies(".env")

        if success:
            # Reload environment variables and re-authenticate client session
            load_dotenv(".env", override=True)
            client.authenticate()
            client.verify_session()
        else:
            logger.error(
                "Cookie auto-refresh failed. Stopping execution to prevent invalid exports."
            )
            exit(1)

    logger.info("=== Extracting Profile Data ===")
    raw_profiles = client.get_profiles(target_zids)
    logger.info(f"DEBUG: raw_profiles columns after scraping: {list(raw_profiles.columns)}")
    logger.info(f"DEBUG: raw_profiles shape: {raw_profiles.shape}")
    logger.info(f"DEBUG: raw_profiles.head():\n{raw_profiles.head()}")

    # Validate that we got meaningful profile data
    expected_cols = ['zid', 'cat', 'racing_score', 'zpoints', 'country', 'team', 'zftp', 'weight', 'age']
    missing_cols = [col for col in expected_cols if col not in raw_profiles.columns]

    if missing_cols:
        logger.error(f"Profile scraping incomplete. Missing columns: {missing_cols}")
        logger.error(f"Only found columns: {list(raw_profiles.columns)}")
        logger.warning("This usually indicates expired cookies. Attempting cookie refresh...")
        
        # Trigger cookie refresh
        success = refresh_zwiftpower_cookies(".env")
        
        if success:
            logger.info("Cookie refresh successful. Re-authenticating and retrying profile scraping...")
            load_dotenv(".env", override=True)
            client.authenticate()
            client.verify_session()
            
            # Retry profile scraping
            raw_profiles = client.get_profiles(target_zids)
            
            # Validate again
            missing_cols = [col for col in expected_cols if col not in raw_profiles.columns]
            if missing_cols:
                logger.error("Profile scraping still incomplete after cookie refresh. Exiting.")
                exit(1)
            else:
                logger.info("Profile scraping successful after cookie refresh!")
        else:
            logger.error("Cookie refresh failed. Cannot proceed with incomplete profile data.")
            exit(1)

    logger.info("=== Extracting Event Histories ===")
    raw_events = client.get_event_histories(target_zids)

    # Process and clean profiles
    numeric_cols = ["weight", "zftp", "zpoints", "racing_score"]
    
    # Remove commas from zpoints (e.g. '7,301' -> '7301') before numeric cleaning
    if "zpoints" in raw_profiles.columns:
        raw_profiles["zpoints"] = raw_profiles["zpoints"].astype(str).str.replace(",", "")
        
    df_profiles_clean = DataPipeline.clean_numeric_columns(
        raw_profiles, numeric_cols
    )
    logger.info(f"DEBUG: df_profiles_clean columns after clean_numeric_columns: {list(df_profiles_clean.columns)}")
    logger.info(f"DEBUG: df_profiles_clean shape: {df_profiles_clean.shape}")

    # ADD TIMESTAMP COLUMN HERE
    # Creates a 'fetched_at' column with the current date and time
    df_profiles_clean["fetched_at"] = pd.Timestamp.now()
    logger.info(f"DEBUG: df_profiles_clean columns after adding fetched_at: {list(df_profiles_clean.columns)}")

    # Process and clean event histories
    df_events_unpacked = DataPipeline.unpack_list_columns(raw_events)
    df_events_clean = DataPipeline.format_event_dates(
        df_events_unpacked, date_column="event_date"
    )
    
    # ==========================================
    # DATABASE EXPORT LOGIC
    # ==========================================
    logger.info("Exporting Events to PostgreSQL (Incremental Load in Chunks)...")
    try:
        # 1. Force SQLAlchemy to construct the table with the Primary Keys first
        # (If the table already exists, this does nothing, but ensures the schema is correct)
        Base.metadata.create_all(engine)

        # 2. Dynamically get only the columns defined in your RiderEvent model
        model_columns = [c.name for c in RiderEvent.__table__.columns]
    
        # 3. Filter your dataframe to drop all the extra ZwiftPower metadata (DT_RowId, friend, etc.)
        # We only keep columns that exist in BOTH the raw dataframe and your DB model
        valid_cols = [col for col in model_columns if col in df_events_clean.columns]
        df_filtered = df_events_clean[valid_cols]
        
        # Replace empty strings (and purely whitespace strings) with NaN so PostgreSQL receives NULL
        df_filtered = df_filtered.replace(r'^\s*$', np.nan, regex=True)
        
        df_filtered = df_filtered.dropna(subset=['zid', 'res_id'])# Watch out for this
        logger.info(f"Filtered to {len(df_filtered)} rows with valid primary keys.")

        # 4. Chunk and Insert
        chunk_size = 100
        for i in range(0, len(df_filtered), chunk_size):
            chunk = df_filtered.iloc[i : i + chunk_size]
        
            chunk.to_sql(
                name="rider_events",
                con=engine,
                if_exists="append",
                index=False,
                method=psql_insert_do_nothing 
                )
        
        logger.info(f"Successfully stored event rows in chunks.")
    except Exception as e:
        logger.error(f"Database insertion failed. Details: {e}")

    # ==========================================
    # PROFILE DATABASE EXPORT LOGIC
    # ==========================================
    logger.info("Exporting Profiles to PostgreSQL...")
    try:
        # Get columns from RiderProfile model (excluding auto-increment 'id')
        profile_model_columns = [c.name for c in RiderProfile.__table__.columns if c.name != 'id']
        
        # Filter dataframe to only include columns that exist in the model
        valid_profile_cols = [col for col in profile_model_columns if col in df_profiles_clean.columns]
        logger.info(f"DEBUG: profile_model_columns: {profile_model_columns}")
        logger.info(f"DEBUG: valid_profile_cols: {valid_profile_cols}")
        logger.info(f"DEBUG: df_profiles_clean.columns before filtering: {list(df_profiles_clean.columns)}")
        df_profiles_filtered = df_profiles_clean[valid_profile_cols]
        logger.info(f"DEBUG: df_profiles_filtered columns after filtering: {list(df_profiles_filtered.columns)}")
        logger.info(f"DEBUG: df_profiles_filtered shape: {df_profiles_filtered.shape}")
        
        # Replace empty strings with NaN
        df_profiles_filtered = df_profiles_filtered.replace(r'^\s*$', np.nan, regex=True)
        
        # Validate primary data exists
        df_profiles_filtered = df_profiles_filtered.dropna(subset=['zid', 'fetched_at'])
        logger.info(f"Filtered to {len(df_profiles_filtered)} profile rows with valid data.")
        
        # Insert profiles
        df_profiles_filtered.to_sql(
            name="rider_profiles",
            con=engine,
            if_exists="append",
            index=False,
            method=psql_insert_do_nothing
        )
        
        logger.info(f"Successfully stored {len(df_profiles_filtered)} profile rows.")
    except Exception as e:
        logger.error(f"Profile database insertion failed. Details: {e}")
        
# Schedule the job to run every day at 2:00 AM
schedule.every().day.at("02:00").do(run_nightly_pipeline)

if __name__ == "__main__":
    logger.info("Pipeline scheduler started. Waiting for 2:00 AM...")
    
    # Optional: run once immediately on startup to test it
    # run_nightly_pipeline() 
    
    # Keep the script alive and checking the time
    while True:
        schedule.run_pending()
        time.sleep(60) # check every minute
        
"""     # Export to CSV
    timestamp_filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info(f"DEBUG: df_profiles_clean columns before CSV export: {list(df_profiles_clean.columns)}")
    logger.info(f"DEBUG: df_profiles_clean shape before CSV export: {df_profiles_clean.shape}")
    DataPipeline.export_to_csv(
        df_profiles_clean, f"zwift_profiles_{timestamp_filename}.csv"
    )
    DataPipeline.export_to_csv(
        df_events_clean, f"zwift_event_history_{timestamp_filename}.csv"
    ) """