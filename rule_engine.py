from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SizeRule:
    width: int
    height: int


def parse_size_rules(raw: str) -> list[SizeRule]:
    rules: list[SizeRule] = []
    for part in (raw or "").split(","):
        token = part.strip().lower().replace(" ", "")
        if "x" not in token:
            continue
        left, right = token.split("x", 1)
        if left.isdigit() and right.isdigit():
            rules.append(SizeRule(width=int(left), height=int(right)))
    return rules


def is_size_match(width: int, height: int, rules: list[SizeRule], tolerance: int) -> bool:
    if not rules:
        return True
    for rule in rules:
        if abs(width - rule.width) <= tolerance and abs(height - rule.height) <= tolerance:
            return True
    return False


def evaluate_banner(
    banner: dict[str, Any],
    size_rules: list[SizeRule],
    tolerance: int,
    required_keyword: str,
    latest_domains: set[str],
    enable_size_check: bool = True,
) -> dict[str, Any]:
    width = int(banner.get("w") or 0)
    height = int(banner.get("h") or 0)
    link = str(banner.get("link") or "").strip()
    domain = str(banner.get("domain") or "").strip().lower()
    match_adserver = bool(banner.get("match_adserver"))

    reasons: list[str] = []

    if enable_size_check:
        if width <= 0 or height <= 0:
            reasons.append("invalid_size")
        elif not is_size_match(width, height, size_rules, tolerance):
            reasons.append("size_mismatch")

    if not link or link == "—":
        reasons.append("missing_link")

    http_status = banner.get("http_status")
    # For MVP, we are more lenient. A status is only "bad" if it's a client/server error (>=400),
    # but we will allow redirects (3xx) as they are common.
    # The `requests` library follows redirects, so we usually get the final status code.
    # A status of '—' means the check failed, which we will ignore for now.
    if isinstance(http_status, int):
        if http_status >= 400:
            reasons.append("bad_http_status")
    # Allow redirects (301, 302, 307, 308) and other 3xx statuses by not flagging them.

    redirect_http_status = banner.get("redirect_http_status")
    if isinstance(redirect_http_status, int):
        if redirect_http_status >= 400:
            reasons.append("bad_redirect_http_status")

    if required_keyword and not match_adserver:
        reasons.append("keyword_not_match")

    if latest_domains and domain and domain not in latest_domains:
        reasons.append("outdated_domain")

    if latest_domains and not domain:
        reasons.append("missing_domain")

    status = "PASS" if not reasons else "FAIL"
    return {
        "status": status,
        "reasons": reasons,
    }


def summarize_site_result(site_result: dict[str, Any]) -> dict[str, Any]:
    refreshes = site_result.get("refreshes", [])
    fail_cases = 0
    banner_total = 0
    pass_banners = 0

    for refresh in refreshes:
        for banner in refresh.get("banners", []):
            banner_total += 1
            if banner.get("qc_status") == "PASS":
                pass_banners += 1
            else:
                fail_cases += 1

    if banner_total == 0:
        site_status = "FAIL"
        fail_cases += 1
    elif fail_cases == 0:
        site_status = "PASS"
    else:
        site_status = "FAIL"

    return {
        "site_status": site_status,
        "banner_total": banner_total,
        "pass_banners": pass_banners,
        "fail_cases": fail_cases,
    }
