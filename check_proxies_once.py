from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

PROXY_DB = os.getenv("PROXY_DB", os.path.join(os.path.dirname(__file__), "proxies.db"))
CHECK_TIMEOUT = int(os.getenv("PROXY_CHECK_TIMEOUT", "10"))


# ── Proxy check ────────────────────────────────────────────────────────────────

def _parse(proxy_str: str) -> dict | None:
    parts = proxy_str.strip().split(":", 3)
    if len(parts) < 2:
        return None
    return {
        "raw": proxy_str,
        "ip": parts[0],
        "port": parts[1],
        "user": parts[2] if len(parts) > 2 else "",
        "pass": parts[3] if len(parts) > 3 else "",
    }


def check_and_detect(proxy_str: str, timeout: int = 10) -> dict:
    p = _parse(proxy_str)
    if not p:
        return {"raw": proxy_str, "alive": False, "isp": "Invalid", "country": ""}

    auth = f"{p['user']}:{p['pass']}@" if p["user"] else ""
    proxy_url = f"http://{auth}{p['ip']}:{p['port']}"
    proxies = {"http": proxy_url, "https": proxy_url}

    for test_url in ["https://ipinfo.io/json", "http://ip-api.com/json"]:
        try:
            r = requests.get(test_url, proxies=proxies, timeout=timeout,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                return {
                    "raw": proxy_str,
                    "alive": True,
                    "isp": data.get("isp", data.get("org", "?")),
                    "country": data.get("country", data.get("countryCode", "?")),
                }
        except Exception:
            continue

    return {"raw": proxy_str, "alive": False, "isp": "?", "country": "?"}


# ── Load from DB ───────────────────────────────────────────────────────────────

def load_proxies() -> list[str]:
    """Load dashboard proxies (chat_id='') from proxies.db."""
    try:
        with sqlite3.connect(PROXY_DB) as conn:
            rows = conn.execute(
                "SELECT proxy FROM proxies WHERE chat_id = '' ORDER BY id"
            ).fetchall()
        return [r[0] for r in rows]
    except Exception as e:
        print(f"[DB] Error: {e}")
        return []


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    proxies = load_proxies()
    if not proxies:
        print("No proxies found in proxies.db.")
        return

    print(f"Checking {len(proxies)} proxy(ies) — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    alive_count = 0
    dead_count = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(check_and_detect, p, CHECK_TIMEOUT): p for p in proxies}
        for future in as_completed(futures):
            result = future.result()
            alive = result.get("alive", False)
            status = "✅ alive" if alive else "❌ dead "
            print(f"  {status}  {result['raw']}  —  {result['isp']}, {result['country']}")
            if alive:
                alive_count += 1
            else:
                dead_count += 1

    print(f"\nResult: {alive_count} alive, {dead_count} dead out of {len(proxies)} total.")


if __name__ == "__main__":
    main()
