import os
from curl_cffi import requests
from dotenv import load_dotenv

load_dotenv()

# Target ZID to inspect
zid = "1714370"

# Setup session with your env cookies
session = requests.Session(impersonate="chrome120")
session.cookies.update(
    {
        "phpbb3_lswlk_sid": os.getenv("PHPBB3_SID"),
        "phpbb3_lswlk_u": os.getenv("PHPBB3_U"),
        "CloudFront-Key-Pair-Id": os.getenv("CLOUDFRONT_KEY_PAIR_ID"),
        "CloudFront-Policy": os.getenv("CLOUDFRONT_POLICY"),
        "CloudFront-Signature": os.getenv("CLOUDFRONT_SIGNATURE"),
    }
)

# Fetch raw HTML
url = f"https://zwiftpower.com/profile.php?z={zid}"
response = session.get(url)

# Save to disk
with open("debug_profile.html", "w", encoding="utf-8") as f:
    f.write(response.text)

print(f"Status Code: {response.status_code}")
print("Done! Open 'debug_profile.html' in VS Code or your browser.")