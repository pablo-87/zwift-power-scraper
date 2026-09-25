from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
import pandas as pd
import json
from typing import Iterable
from selenium.common.exceptions import NoSuchElementException, WebDriverException



def clean_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Extracts numeric values (floats/ints) from specified string columns 
    and converts them to float type.
    """
    df_clean = df.copy()
    
    for col in columns:
        if col in df_clean.columns:
            df_clean[col] = (
                df_clean[col]
                .astype(str)
                .str.extract(r'([-+]?\d*\.?\d+)', expand=False)
                .astype(float)
            )
            
    return df_clean

def extract_first_element(df: pd.DataFrame, columns: list[str], convert_numeric: bool = True) -> pd.DataFrame:
    """
    Extracts the first element from list-like cells (e.g., ['218', 0] -> '218')
    for specified columns in a Pandas DataFrame.
    """
    df_clean = df.copy()
    
    for col in columns:
        if col in df_clean.columns:
            # Unpack first element if cell is a non-empty list/tuple
            df_clean[col] = df_clean[col].apply(
                lambda x: x[0] if isinstance(x, (list, tuple)) and len(x) > 0 else x
            )
            
            # Convert extracted string numbers to numeric float/int types
            if convert_numeric:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                
    return df_clean


def zpower_login(username:str,password:str,driver):
    
    login_url = 'https://zwiftpower.com/ucp.php?mode=login&amp;login=external&amp;oauth_service=oauthzpsso'
    driver.get(login_url)
    driver.find_element(By.XPATH,'//*[@id="login"]/fieldset/div/div[1]/div/a').click()
    # Username
    driver.find_element(By.XPATH,'//*[@id="username"]').send_keys(username)
    # Password
    driver.find_element(By.XPATH,'//*[@id="password"]').send_keys(password)
    # submit login
    driver.find_element(By.XPATH,'//*[@id="submit-button"]').click()
    # filter for past results
    driver.find_element(By.XPATH,'//*[@id="button_event_results"]').click()
    # take last 7 day results and iterate across pages
    ## Filters
    driver.find_element(By.XPATH,'//*[@id="button_event_filter"]').click()
    """Button 2 for 1 day, 3 for 3 days and 4 for 7 days"""
    driver.find_element(By.XPATH,'//*[@id="filter_options"]/div/div[9]/button[2]').click()

def get_zwiftpower_profiles(
    driver, zids: Iterable[int | str] | int | str
) -> pd.DataFrame:
    """Fetches user profile data from ZwiftPower for single or multiple ZIDs

    and returns a Pandas DataFrame.
    """
    if isinstance(zids, (int, str)):
        zids = [zids]

    riders_data = []

    def get_text_safe(xpath: str) -> str | None:
        """Safely extract element text or return None if not found/empty."""
        try:
            text = driver.find_element(By.XPATH, xpath).text
            return text if text else None
        except NoSuchElementException:
            return None

    for zid in zids:
        url_profile = f"https://zwiftpower.com/profile.php?z={zid}"

        try:
            driver.get(url_profile)

            cat_xpath_1 = "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[1]/div[2]/table/tbody/tr[8]/td/span"
            cat_xpath_2 = "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[1]/div[2]/table/tbody/tr[9]/td/span[1]"

            # Check primary cat location
            cat = get_text_safe(cat_xpath_1)

            if cat is not None:
                # Default row positions
                zftp_xpath = "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[1]/div[2]/table/tbody/tr[15]/td"
                weight_xpath = "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[1]/div[2]/table/tbody/tr[16]/td"
            else:
                # Check secondary cat location
                cat = get_text_safe(cat_xpath_2)
                if cat is not None:
                    # Shifted row positions (tr[16] and tr[17])
                    zftp_xpath = "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[1]/div[2]/table/tbody/tr[16]/td"
                    weight_xpath = "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[1]/div[2]/table/tbody/tr[17]/td"
                else:
                    # Fallback defaults if category is completely missing
                    zftp_xpath = "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[1]/div[2]/table/tbody/tr[15]/td"
                    weight_xpath = "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[1]/div[2]/table/tbody/tr[16]/td"

            rider_data = {
                "zid": zid,
                "cat": cat,
                "zftp": get_text_safe(zftp_xpath),
                "weight": get_text_safe(weight_xpath),
                "wkg_15s": get_text_safe(
                    "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[2]/div[2]/div/div/div[1]/div[1]/span"
                ),
                "wkg_1m": get_text_safe(
                    "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[2]/div[2]/div/div/div[1]/div[2]/span"
                ),
                "wkg_5m": get_text_safe(
                    "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[2]/div[2]/div/div/div[1]/div[3]/span"
                ),
                "wkg_20m": get_text_safe(
                    "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[2]/div[2]/div/div/div[1]/div[4]/span"
                ),
                "w_15s": get_text_safe(
                    "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[2]/div[3]/div/div/div[1]/div[1]/span"
                ),
                "w_1m": get_text_safe(
                    "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[2]/div[3]/div/div/div[1]/div[2]/span"
                ),
                "w_5m": get_text_safe(
                    "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[2]/div[3]/div/div/div[1]/div[3]/span"
                ),
                "w_20m": get_text_safe(
                    "/html/body/div[2]/div[2]/div/div/div[1]/div[1]/div[1]/div/div[3]/div[2]/div[3]/div/div/div[1]/div[4]/span"
                ),
            }
            riders_data.append(rider_data)

        except WebDriverException as e:
            print(f"Failed to load or parse profile for ZID {zid}: {e}")
            riders_data.append({"zid": zid})

    return pd.DataFrame(riders_data)

def get_rider_all(
    driver, zids: Iterable[int | str] | int | str
) -> pd.DataFrame:
    """Fetches full event history JSON data from ZwiftPower for single or

    multiple ZIDs and concatenates them into a single Pandas DataFrame.
    """
    if isinstance(zids, (int, str)):
        zids = [zids]

    all_dfs = []

    for zid in zids:
        url = f"https://zwiftpower.com/cache3/profile/{zid}_all.json"

        try:
            driver.get(url)

            # Extract raw JSON from browser view
            raw_text = driver.find_element(By.TAG_NAME, "body").text
            json_object = json.loads(raw_text)

            # Convert 'data' key array to DataFrame
            data = json_object.get("data", [])
            if data:
                df = pd.DataFrame(data)
                df["query_zid"] = (
                    zid  # Ensure the querying ZID is tracked per record
                )
                all_dfs.append(df)

        except (WebDriverException, json.JSONDecodeError, KeyError) as e:
            print(f"Failed to fetch or parse JSON for ZID {zid}: {e}")
            continue

    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)

    return pd.DataFrame()