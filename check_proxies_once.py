from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests
from dotenv import load_dotenv
from db_helper import DBHelper

load_dotenv()

CHECK_TIMEOUT = int(os.getenv("PROXY_CHECK_TIMEOUT", "10"))

# ── Proxy check ────────────────────────────────────────────────────────────────

def _parse_dict(p: dict) -> str:
    """Reconstruct proxy string from DB dict."""
    if p['username'] and p['password']:
        return f"{p['ip']}:{p['port']}:{p['username']}:{p['password']}"
    return f"{p['ip']}:{p['port']}"

def check_and_detect(p_dict: dict, timeout: int = 10) -> dict:
    raw = _parse_dict(p_dict)
    auth = f"{p_dict['username']}:{p_dict['password']}@" if p_dict['username'] else ""
    proxy_url = f"http://{auth}{p_dict['ip']}:{p_dict['port']}"
    proxies = {"http": proxy_url, "https": proxy_url}

    for test_url in ["https://ipinfo.io/json", "http://ip-api.com/json"]:
        try:
            r = requests.get(test_url, proxies=proxies, timeout=timeout,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                return {
                    "id": p_dict['id'],
                    "raw": raw,
                    "alive": True,
                    "isp": data.get("isp", data.get("org", "?")),
                    "country": data.get("country", data.get("countryCode", "?")),
                }
        except Exception:
            continue

    return {"id": p_dict['id'], "raw": raw, "alive": False, "isp": "?", "country": "?"}

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    db = DBHelper()
    proxies = db.get_active_proxies()
    if not proxies:
        print("No active proxies found in MariaDB.")
        return

    print(f"Checking {len(proxies)} proxy(ies) from MariaDB — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    alive_count = 0
    dead_count = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(check_and_detect, p, CHECK_TIMEOUT): p for p in proxies}
        for future in as_completed(futures):
            result = future.result()
            alive = result.get("alive", False)
            status = "✅ alive" if alive else "❌ dead "
            
            print(f"  {status}  {result['raw']}  —  {result['isp']}, {result['country']}")
            
            if not alive:
                db.update_proxy_status(result['id'], False)
                dead_count += 1
            else:
                alive_count += 1

    db.close()
    print(f"\nResult: {alive_count} alive, {dead_count} dead out of {len(proxies)} total.")
    if dead_count > 0:
        print(f"Note: {dead_count} dead proxies have been marked as 'dead' in MariaDB.")

if __name__ == "__main__":
    main()
