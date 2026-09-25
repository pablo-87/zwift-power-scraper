import os
import re
import sys
import zipfile
import shutil
import subprocess
from pathlib import Path
import requests

def get_chrome_browser_version() -> str:
    """Helper function to find the installed Chrome browser version."""
    try:
        if sys.platform.startswith('win'):
            cmd = r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version'
            output = subprocess.check_output(cmd, shell=True, text=True)
            match = re.search(r'version\s+REG_SZ\s+([\d.]+)', output)
            if match:
                return match.group(1)
        elif sys.platform.startswith('darwin'):
            cmd = r'/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version'
            output = subprocess.check_output(cmd, shell=True, text=True)
            match = re.search(r'Google Chrome\s+([\d.]+)', output)
            if match:
                return match.group(1)
        else:
            for binary in ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']:
                try:
                    output = subprocess.check_output([binary, '--version'], text=True)
                    match = re.search(r'(?:Google Chrome|Chromium)\s+([\d.]+)', output)
                    if match:
                        return match.group(1)
                except FileNotFoundError:
                    continue
    except Exception as e:
        print(f"Warning: Could not detect Chrome browser version automatically: {e}")
    return None

def update_chromedriver(DIR: Path) -> Path:
    """
    Checks the local Chrome browser version, matches it with the correct 
    ChromeDriver version via the CfT API, and updates DIR if necessary.
    
    Args:
        DIR (Path): A pathlib.Path object pointing to the target directory.
        
    Returns:
        Path: A pathlib.Path object pointing to the updated executable.
    """
    # Create the directory if it doesn't exist
    DIR.mkdir(parents=True, exist_ok=True)
    
    # OS-specific binary naming & platform keys
    if sys.platform.startswith('win'):
        driver_name = "chromedriver.exe"
        platform_key = "win64"
    elif sys.platform.startswith('darwin'):
        driver_name = "chromedriver"
        platform_key = "mac-arm64" if sys.maxsize > 2**32 and os.uname().machine == 'arm64' else "mac-x64"
    else:
        driver_name = "chromedriver"
        platform_key = "linux64"

    # Using pathlib's / operator to join paths
    chromedriver_path = DIR / driver_name
    local_driver_version = None

    # 1. Get current local ChromeDriver version (if it exists)
    if chromedriver_path.exists():
        try:
            if not sys.platform.startswith('win'):
                chromedriver_path.chmod(0o755)
            result = subprocess.run([str(chromedriver_path), '--version'], capture_output=True, text=True, check=True)
            match = re.search(r'ChromeDriver\s+([\d.]+)', result.stdout)
            if match:
                local_driver_version = match.group(1)
                print(f"Current local ChromeDriver: {local_driver_version}")
        except Exception as e:
            print(f"Could not determine local ChromeDriver version: {e}")

    # 2. Get local Chrome Browser version
    browser_version = get_chrome_browser_version()
    if not browser_version:
        print("Fallback: Could not find Chrome browser version. Defaulting to latest stable.")
        browser_major = None
    else:
        print(f"Detected Chrome Browser version: {browser_version}")
        browser_major = browser_version.split('.')[0]

    # 3. Query the Chrome for Testing API
    try:
        if browser_major:
            api_url = "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json"
            response = requests.get(api_url).json()
            
            if browser_major in response['milestones']:
                milestone_data = response['milestones'][browser_major]
                target_version = milestone_data['version']
                downloads = milestone_data['downloads']['chromedriver']
            else:
                raise ValueError(f"Milestone {browser_major} not found in CfT API.")
        else:
            api_url = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
            response = requests.get(api_url).json()
            target_version = response['channels']['Stable']['version']
            downloads = response['channels']['Stable']['downloads']['chromedriver']

        download_url = next(item['url'] for item in downloads if item['platform'] == platform_key)
        print(f"Target ChromeDriver version required: {target_version}")
        
    except Exception as e:
        raise RuntimeError(f"Failed to fetch matching ChromeDriver metadata from API: {e}")

    # 4. Compare and Update if versions don't match
    if local_driver_version != target_version:
        print(f"Version mismatch! Updating Driver ({local_driver_version}) -> Target ({target_version})...")
        zip_path = DIR / "chromedriver.zip"
        
        # Download
        res = requests.get(download_url, stream=True)
        res.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
                
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(DIR)
        zip_path.unlink()  # pathlib replacement for os.remove()
        
        # Structure adjustment (pulling it out of the extracted subfolder)
        extracted_dir_name = f"chromedriver-{platform_key}"
        extracted_binary_path = DIR / extracted_dir_name / driver_name
        
        if extracted_binary_path.exists():
            if chromedriver_path.exists():
                chromedriver_path.unlink()
            
            # shutil still handles moving files, but accepts Path objects natively
            shutil.move(extracted_binary_path, chromedriver_path)
            shutil.rmtree(DIR / extracted_dir_name)
            
        print("ChromeDriver updated successfully to match your browser!")
    else:
        print("ChromeDriver is already perfectly aligned with your browser version.")

    if not sys.platform.startswith('win'):
        chromedriver_path.chmod(0o755)

    return chromedriver_path.resolve()