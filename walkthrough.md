# Tool Walkthroughs

## 1. Google Bot Checker
**Script Location:** `/Users/user/Documents/app/tool/check_google_bot/google_bot_checker.py`

### How to Use
```bash
python3 /Users/user/Documents/app/tool/check_google_bot/google_bot_checker.py [URL]
```
Checks if a site is accessible to Google Bot by simulating its User-Agent.

## 2. Banner Ad Checker
**Script Location:** `/Users/user/Documents/app/tool/check_banner_playwright/banner_checker.py`

### Purpose
Automates the checking of banner ads on multiple sites. It verifies:
1.  **Visibility**: The banner element exists and is visible.
2.  **Link Reachability**: The banner's link redirects to a valid page (HTTP 200).
3.  **Destination Match (Optional)**: If provided, checks if the final URL matches the expected one.
4.  **Auto-Detection**: If `zone_id` is missing, it tries to find the ad using common selectors (e.g., `div[id*='banner']`, `iframe[src*='ads']`).

### How to Use
1.  **Install Dependencies**:
    ```bash
    pip install playwright httpx
    playwright install chromium
    ```
2.  **Configure Sites**:
    Edit the `TEST_SITES` list in `banner_checker.py`.
    ```python
    TEST_SITES = [
        {
            "site_url": "https://example.com/site_a",
            "zone_id": "#ad-banner-hay-123", # Optional: Remove to use auto-detection
            # "expected_landing_page_url": "..." # Optional
        },
        ...
    ]
    ```
3.  **Run the Script**:
    ```bash
    python3 /Users/user/Documents/app/tool/check_banner_playwright/banner_checker.py
    ```

### Output
The script prints a summary of PASS/FAIL for each site and details any errors (timeouts, broken links, etc.).
