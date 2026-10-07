import json
import logging
import os
import re
import time
from typing import Iterable
from bs4 import BeautifulSoup
from curl_cffi import requests
import pandas as pd

logger = logging.getLogger(__name__)



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
                        logger.debug(f"DEBUG: Saved HTML for ZID {zid} to debug_received_html.html")
                        logger.debug(f"DEBUG: HTML length: {len(res.text)} characters")
                        logger.debug(f"DEBUG: HTML preview (first 500 chars): {res.text[:500]}")
                    
                    # Pass the raw HTML and ZID to our new parser
                    rider_info = self._parse_profile_html(res.text, zid)
                    logger.debug(f"DEBUG: Parsed profile for ZID {zid}: {rider_info}")
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
        
        logger.debug(f"DEBUG: Found {len(table_map)} table rows for ZID {zid}")
        logger.debug(f"DEBUG: Table labels found: {list(table_map.keys())}")

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