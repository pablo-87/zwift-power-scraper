from selenium import webdriver
from pathlib import Path
from scrap_functions import zpower_login, get_rider_all, get_zwiftpower_profiles, clean_numeric_columns,extract_first_element
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
from check_chromedriver import update_chromedriver
load_dotenv()

# Zwift credentials
username = os.getenv('zwift_username')
password = os.getenv('zwift_password')

# Get the chromedriver folder dir
current_dir = Path(__file__).resolve().parent

## Make sure to pass in the folder used for storing/downloading chromedriver
update_chromedriver(DIR = current_dir)

# Setup the driver
driver = webdriver.Chrome("chromedriver")

# Guard Check
if username is None:
    raise ValueError("ZWIFT_USER environment variable is not set")
if password is None:
    raise ValueError("ZWIFT_USER environment variable is not set")

# Zwift Login
zpower_login(username, password, driver)

# --- Target ZID List ---
zid_list = [1714370, 1815308, 1002137]

try:
    # 1. Fetch profile metrics (1 row per rider)
    df_profiles = get_zwiftpower_profiles(driver, zid_list)

    # 2. Fetch full event histories (Multiple rows per rider)
    df_events = get_rider_all(driver, zid_list)

    # 3. View Results
    print("=== Profiles DataFrame ===")
    print(df_profiles[["zid", "cat", "zftp", "weight", "wkg_20m"]])

    print("\n=== Events History DataFrame ===")
    print(df_events[["query_zid", "event_title", "category", "avg_power", "time"]].head())

finally:
    driver.quit()
    
    
# Para hacer: Hay que llevarlo a una base SQL
# engine = create_engine("postgresql://postgres:tr0t5kyvgn@localhost/ZWIFT_POWER")

# Cleaning steps
cols_to_clean = ['weight', 'zftp', 'wkg_15s', 'wkg_1m', 'wkg_5m', 'wkg_20m', 'w_15s', 'w_1m', 'w_5m', 'w_20m']

# Apply function to update DataFrame
df_profiles = clean_numeric_columns(df_profiles, cols_to_clean)

list_cols = [col for col in df_events.columns if not df_events[col].dropna().empty and isinstance(df_events[col].dropna().iloc[0], (list, tuple))]
df_events = extract_first_element(df_events, list_cols)
df_events.sort_values(by='event_date', inplace=True,ascending=False)
df_events['event_date'] = pd.to_datetime(df_events['event_date'], unit='s').dt.strftime('%Y/%m/%d')