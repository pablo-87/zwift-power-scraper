import logging
import os
from dotenv import load_dotenv, set_key
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("CookieRefresher")

def refresh_zwiftpower_cookies(env_path: str = ".env") -> bool:
    load_dotenv(env_path, override=True)
    username = os.getenv("ZWIFT_USER")
    password = os.getenv("ZWIFT_PASS")

    if not username or not password:
        logger.error("ZWIFT_USER and ZWIFT_PASS must be configured in your .env file.")
        return False

    logger.info("Launching headless browser to generate fresh ZwiftPower session...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        try:
            logger.info("Navigating to ZwiftPower login endpoint...")
            page.goto("https://zwiftpower.com/ucp.php?mode=login")

            # 1. Attempt to dismiss Cookie/Consent Banners if they block clicks
            try:
                cookie_btn = page.locator('button#truste-consent-button, button:has-text("Accept")').first
                cookie_btn.click(timeout=2000)
                logger.info("Dismissed cookie consent banner.")
            except PlaywrightTimeoutError:
                pass  # No banner found, continue

            # 2. Look for the intermediate "Login with Zwift" bridge button
            try:
                # Target the exact link structure revealed in your error logs
                bridge_btn = page.locator('a.btn-warning[href*="oauthzpsso"]').first
                
                # Use a raw JavaScript click to bypass ALL Playwright visibility and overlay checks
                bridge_btn.evaluate("node => node.click()")
                
                logger.info("Clicked SSO bridge button. Redirecting to Zwift SSO...")
            except Exception as e:
                logger.warning(
                    "Could not click the bridge button. Waiting to see if it auto-redirects..."
                )

            # 3. Wait for the actual email field on secure.zwift.com
            logger.info("Waiting for Zwift SSO redirect to render...")
            username_field = page.wait_for_selector(
                'input[type="email"], input[name="username"]', timeout=20000
            )

            # Fill credentials
            logger.info("Zwift SSO login page detected. Submitting credentials...")
            username_field.fill(username)
            page.locator('input[type="password"], input[name="password"]').first.fill(password)
            
            # Submit (force=True bypasses any UI overlays)
            page.locator('button[type="submit"], input[type="submit"]').first.click(force=True)

            logger.info("Waiting for authentication redirect back to ZwiftPower...")
            page.wait_for_url("https://zwiftpower.com/**", timeout=30000)

            # 4. Force CloudFront to issue tokens
            logger.info("Establishing CloudFront CDN session tokens...")
            page.goto("https://zwiftpower.com/profile.php", wait_until="domcontentloaded")
            page.goto("https://zwiftpower.com/cache3/profile/1714370_all.json", wait_until="domcontentloaded")

            # Extract Cookies
            all_cookies = context.cookies()
            cookie_map = {c["name"]: c["value"] for c in all_cookies}

            required_keys = {
                "PHPBB3_SID": "phpbb3_lswlk_sid",
                "PHPBB3_U": "phpbb3_lswlk_u",
                "CLOUDFRONT_KEY_PAIR_ID": "CloudFront-Key-Pair-Id",
                "CLOUDFRONT_POLICY": "CloudFront-Policy",
                "CLOUDFRONT_SIGNATURE": "CloudFront-Signature",
            }

            updated_count = 0
            for env_var, cookie_name in required_keys.items():
                val = cookie_map.get(cookie_name)
                if val:
                    set_key(env_path, env_var, val)
                    updated_count += 1
                else:
                    logger.warning(f"Expected cookie '{cookie_name}' was not found in browser context.")

            browser.close()

            if updated_count >= 3:
                logger.info(f"Successfully updated {updated_count} authentication keys in {env_path}!")
                return True
            else:
                logger.error("Failed to extract enough required cookies from session.")
                return False

        except PlaywrightTimeoutError:
            # SAVE A SCREENSHOT ON TIMEOUT TO DEBUG
            screenshot_path = "debug_playwright_timeout.png"
            page.screenshot(path=screenshot_path)
            logger.error(f"Timeout occurred. Current URL: {page.url}")
            logger.error(f">>> SAVED SCREENSHOT TO '{screenshot_path}'. Open it to see what blocked the script (e.g., Cloudflare check, missing button).")
            browser.close()
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Playwright execution: {e}")
            browser.close()
            return False

if __name__ == "__main__":
    refresh_zwiftpower_cookies()