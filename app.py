from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from threading import Lock
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from banner_checker import run_banner_check
from history_store import HistoryStore

load_dotenv()

PORT = int(os.getenv("BANNER_QC_PORT", "8011"))
HISTORY_DIR = os.getenv("BANNER_QC_HISTORY_DIR", "history")
DOMAIN_API = os.getenv("BANNER_DOMAIN_API", "").strip()
DOMAIN_API_TIMEOUT = max(3.0, min(float(os.getenv("BANNER_DOMAIN_API_TIMEOUT", "12")), 60.0))
DOMAIN_API_RETRIES = max(1, min(int(os.getenv("BANNER_DOMAIN_API_RETRIES", "2")), 5))
DOMAIN_API_RETRY_DELAY = max(0.0, min(float(os.getenv("BANNER_DOMAIN_API_RETRY_DELAY", "0.8")), 10.0))

app = Flask(__name__, template_folder="templates")
store = HistoryStore(HISTORY_DIR)
domain_source_lock = Lock()
domain_source_cache: set[str] = set()
domain_source_state: dict[str, str | int | float] = {
    "status": "idle",
    "last_sync_at": "",
    "last_error": "",
    "source": "cache",
    "total": 0,
}


def normalize_domain(url_or_domain: str) -> str:
    value = (url_or_domain or "").strip().lower()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return urlparse(value).netloc.replace("www.", "")
    return value.replace("www.", "")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_domains_from_payload(payload: object) -> set[str]:
    items: list[object] = []

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("domains", "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                items = value
                break
        if not items and any(key in payload for key in ("domain", "url", "host", "site", "main_domain")):
            items = [payload]

    normalized: set[str] = set()
    for item in items:
        if isinstance(item, str):
            domain = normalize_domain(item)
            if domain:
                normalized.add(domain)
            continue

        if isinstance(item, dict):
            candidate = (
                item.get("domain")
                or item.get("url")
                or item.get("host")
                or item.get("site")
                or item.get("main_domain")
                or item.get("destination_domain")
            )
            domain = normalize_domain(str(candidate or ""))
            if domain:
                normalized.add(domain)

    return normalized


def action_call_domain_api() -> tuple[set[str], str]:
    if not DOMAIN_API:
        return set(), "domain_api_not_configured"

    last_error = ""
    for attempt in range(1, DOMAIN_API_RETRIES + 1):
        try:
            response = requests.get(DOMAIN_API, timeout=DOMAIN_API_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            domains = extract_domains_from_payload(payload)
            return domains, "ok"
        except Exception as exc:
            last_error = str(exc)
            if attempt < DOMAIN_API_RETRIES and DOMAIN_API_RETRY_DELAY > 0:
                time.sleep(DOMAIN_API_RETRY_DELAY)

    return set(), last_error or "domain_api_unknown_error"


def fetch_latest_domains(force: bool = False) -> set[str]:
    with domain_source_lock:
        if domain_source_cache and not force:
            return set(domain_source_cache)

        domains, call_status = action_call_domain_api()

        if call_status == "ok":
            domain_source_cache.clear()
            domain_source_cache.update(domains)
            domain_source_state["status"] = "ok"
            domain_source_state["source"] = "api_live"
            domain_source_state["last_error"] = ""
            domain_source_state["last_sync_at"] = utc_now_iso()
            domain_source_state["total"] = len(domain_source_cache)
            return set(domain_source_cache)

        if not DOMAIN_API:
            domain_source_state["status"] = "no_api"
            domain_source_state["source"] = "fallback_empty"
            domain_source_state["last_error"] = "BANNER_DOMAIN_API is empty"
            domain_source_state["last_sync_at"] = utc_now_iso()
            domain_source_state["total"] = len(domain_source_cache)
            return set(domain_source_cache)

        domain_source_state["status"] = "api_error"
        domain_source_state["source"] = "cache_fallback" if domain_source_cache else "fallback_empty"
        domain_source_state["last_error"] = call_status
        domain_source_state["last_sync_at"] = utc_now_iso()
        domain_source_state["total"] = len(domain_source_cache)
        return set(domain_source_cache)


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/domain_source")
def domain_source():
    latest_domains = sorted(fetch_latest_domains(force=False))
    return jsonify(
        {
            "domain_api": DOMAIN_API,
            "timeout_seconds": DOMAIN_API_TIMEOUT,
            "retries": DOMAIN_API_RETRIES,
            "retry_delay_seconds": DOMAIN_API_RETRY_DELAY,
            "total": len(latest_domains),
            "domains": latest_domains[:50],
            "state": domain_source_state,
        }
    )


@app.route("/api/domain_source/refresh", methods=["POST"])
def refresh_domain_source():
    latest_domains = fetch_latest_domains(force=True)
    return jsonify(
        {
            "status": "ok",
            "total": len(latest_domains),
            "state": domain_source_state,
        }
    )


@app.route("/api/domain_source/action", methods=["POST"])
def action_domain_source():
    latest_domains = fetch_latest_domains(force=True)
    return jsonify(
        {
            "status": "ok",
            "action": "call_domain_api",
            "total": len(latest_domains),
            "state": domain_source_state,
        }
    )


@app.route("/api/banner/check", methods=["POST"])
def banner_check():
    payload = request.get_json(silent=True) or {}
    latest_domains = fetch_latest_domains(force=False)
    result = run_banner_check(payload, latest_domains=latest_domains)
    filename = store.save(result)
    result["history_file"] = filename
    return jsonify(result)


@app.route("/api/history")
def history_list():
    return jsonify({"history": store.list_files(limit=100)})


@app.route("/api/history/<path:filename>")
def history_detail(filename: str):
    try:
        data = store.load(filename)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "history_not_found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
