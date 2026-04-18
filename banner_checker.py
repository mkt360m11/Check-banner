from __future__ import annotations

import base64
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from rule_engine import evaluate_banner, parse_size_rules, summarize_site_result


HIGH_CONFIDENCE = [
    "ins[data-revive-zoneid]",
    "ins[data-revive-id]",
    "ins[data-z]",
    "ins[id*='revive']",
    "ins[class*='ads']",
    "a[href*='c-cl.php']",
    "div[id*='header_bar']",
    "div[class*='header_bar']",
    "div[id*='pc_header_bar']",
    "iframe[src*='ads']",
    "iframe[src*='adserver']",
    "iframe[id*='google_ads']",
]

COMMON_SELECTORS = [
    "div[class*='banner_ads']",
    "div[id*='ads_banner']",
    "img[class*='img-ads']",
    "div[id*='banner']",
    "div[class*='banner']",
    "div[id*='ad-']",
    "div[class*='ad-']",
    "div[class*='advertisement']",
    "img[src*='banner']",
]


def parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def normalize_http_url(raw_url: str, base_url: str = "") -> str:
    value = (raw_url or "").strip()
    if not value or value in {"#", "javascript:void(0)", "javascript:;"}:
        return ""
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if base_url:
        try:
            joined = urljoin(base_url, value)
            if joined.startswith("http://") or joined.startswith("https://"):
                return joined
        except Exception:
            return ""
    return ""


def extract_first_url_from_text(text: str, base_url: str = "") -> str:
    if not text:
        return ""
    match = re.search(r"(https?:\\/\\/[^'\"\\s)]+|https?://[^'\"\\s)]+|//[^'\"\\s)]+)", text, flags=re.IGNORECASE)
    if not match:
        return ""
    raw = match.group(1).replace("\\/", "/")
    return normalize_http_url(raw, base_url=base_url)


def get_page_height(driver: webdriver.Chrome) -> int:
    try:
        return int(driver.execute_script("return document.body.scrollHeight"))
    except Exception:
        return 1


def classify_position(y: int, page_height: int) -> str:
    ratio = y / max(page_height, 1)
    if ratio < 0.33:
        return "Top"
    if ratio < 0.66:
        return "Middle"
    return "Bottom"


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def resolve_link(element, base_url: str = "") -> str:
    candidate_attrs = [
        "href",
        "src",
        "data-href",
        "data-url",
        "data-link",
        "data-dest",
        "data-destination",
        "data-redirect",
    ]

    ad_link = ""
    for attr in candidate_attrs:
        try:
            value = element.get_attribute(attr) or ""
        except Exception:
            value = ""
        normalized = normalize_http_url(value, base_url=base_url)
        if normalized:
            ad_link = normalized
            break

    if not ad_link:
        try:
            onclick = element.get_attribute("onclick") or ""
            ad_link = extract_first_url_from_text(onclick, base_url=base_url)
        except Exception:
            ad_link = ""

    if not ad_link:
        current = element
        for _ in range(3):
            try:
                current = current.find_element(By.XPATH, "..")
                parent_link = ""
                for attr in candidate_attrs:
                    value = current.get_attribute(attr) or ""
                    normalized = normalize_http_url(value, base_url=base_url)
                    if normalized:
                        parent_link = normalized
                        break
                if not parent_link:
                    parent_link = extract_first_url_from_text(current.get_attribute("onclick") or "", base_url=base_url)
                if parent_link:
                    ad_link = parent_link
                    break
            except Exception:
                break

    if not ad_link:
        anchors = element.find_elements(By.TAG_NAME, "a")
        for anchor in anchors:
            try:
                href = normalize_http_url(anchor.get_attribute("href") or "", base_url=base_url)
                if href:
                    ad_link = href
                    break
                onclick_href = extract_first_url_from_text(anchor.get_attribute("onclick") or "", base_url=base_url)
                if onclick_href:
                    ad_link = onclick_href
                    break
            except Exception:
                continue

    if not ad_link:
        images = element.find_elements(By.TAG_NAME, "img")
        for image in images:
            try:
                src = normalize_http_url(image.get_attribute("src") or "", base_url=base_url)
                if src:
                    ad_link = src
                    break
            except Exception:
                continue

    return ad_link or "—"


def resolve_image_src(element, base_url: str = "") -> str:
    try:
        tag_name = (element.tag_name or "").lower()
    except Exception:
        tag_name = ""

    if tag_name == "img":
        try:
            src = normalize_http_url(element.get_attribute("src") or "", base_url=base_url)
            if src:
                return src
            data_src = normalize_http_url(element.get_attribute("data-src") or "", base_url=base_url)
            if data_src:
                return data_src
            srcset = (element.get_attribute("srcset") or element.get_attribute("data-srcset") or "").strip()
            if srcset:
                first_src = srcset.split(",")[0].strip().split(" ")[0]
                normalized = normalize_http_url(first_src, base_url=base_url)
                if normalized:
                    return normalized
        except Exception:
            pass

    try:
        images = element.find_elements(By.TAG_NAME, "img")
        for img in images:
            try:
                src = normalize_http_url(img.get_attribute("src") or "", base_url=base_url)
                if src:
                    return src
                data_src = normalize_http_url(img.get_attribute("data-src") or "", base_url=base_url)
                if data_src:
                    return data_src
                srcset = (img.get_attribute("srcset") or img.get_attribute("data-srcset") or "").strip()
                if srcset:
                    first_src = srcset.split(",")[0].strip().split(" ")[0]
                    normalized = normalize_http_url(first_src, base_url=base_url)
                    if normalized:
                        return normalized
            except Exception:
                continue
    except Exception:
        pass

    return ""


def check_link_status(link: str) -> tuple[str, int | str, bool]:
    if not link or link == "—" or not link.startswith("http"):
        return "", "—", False

    try:
        domain = urlparse(link).netloc.replace("www.", "").lower()
        response = requests.head(link, timeout=8, allow_redirects=True)
        return domain, response.status_code, True
    except Exception:
        return "", "—", False


def resolve_redirect_with_requests(link: str) -> tuple[str, str, int | str]:
    if not link or link == "—" or not link.startswith("http"):
        return "", "", "—"

    try:
        response = requests.get(
            link,
            timeout=12,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        final_url = response.url if isinstance(response.url, str) else ""
        final_domain = urlparse(final_url).netloc.replace("www.", "").lower() if final_url else ""
        return final_url, final_domain, response.status_code
    except Exception:
        return "", "", "—"


def fetch_image_as_base64(image_url: str) -> str:
    if not image_url or not image_url.startswith("http"):
        return ""
    try:
        response = requests.get(
            image_url,
            timeout=12,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "image" not in content_type:
            return ""
        return base64.b64encode(response.content).decode("utf-8")
    except Exception:
        return ""


def resolve_redirect_with_browser(
    driver: webdriver.Chrome,
    link: str,
    capture_destination_screenshot: bool,
) -> tuple[str, str, str]:
    if not link or link == "—" or not link.startswith("http"):
        return "", "", ""

    origin_handle = driver.current_window_handle
    before_handles = set(driver.window_handles)
    new_handle = ""
    screenshot_b64 = ""

    try:
        driver.execute_script("window.open(arguments[0], '_blank');", link)
        time.sleep(1)
        after_handles = set(driver.window_handles)
        created = list(after_handles - before_handles)
        if created:
            new_handle = created[0]
        elif len(driver.window_handles) > 1:
            new_handle = driver.window_handles[-1]
        else:
            return "", "", ""

        driver.switch_to.window(new_handle)
        time.sleep(4)
        final_url = driver.current_url or ""
        final_domain = urlparse(final_url).netloc.replace("www.", "").lower() if final_url else ""

        if capture_destination_screenshot:
            try:
                screenshot_b64 = base64.b64encode(driver.get_screenshot_as_png()).decode("utf-8")
            except Exception:
                screenshot_b64 = ""

        return final_url, final_domain, screenshot_b64
    except Exception:
        return "", "", ""
    finally:
        try:
            if new_handle:
                driver.close()
        except Exception:
            pass
        try:
            driver.switch_to.window(origin_handle)
        except Exception:
            pass


def extract_destination_link(link: str) -> str:
    if not link or link == "—" or not link.startswith("http"):
        return ""
    try:
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        dest_values = (
            query.get("dest")
            or query.get("url")
            or query.get("redirect")
            or query.get("target")
            or query.get("to")
            or query.get("u")
            or query.get("rd")
            or query.get("next")
            or query.get("continue")
            or query.get("out")
            or query.get("goto")
            or query.get("link")
        )
        if dest_values and dest_values[0]:
            value = dest_values[0]
            for _ in range(3):
                decoded = unquote(value)
                if decoded == value:
                    break
                value = decoded
            normalized = normalize_http_url(value)
            return normalized or value
    except Exception:
        return ""
    return ""


def build_selectors(adserver_kws: list[str]) -> list[str]:
    selectors = list(HIGH_CONFIDENCE)
    if adserver_kws:
        kw_selectors: list[str] = []
        for keyword in adserver_kws:
            kw_selectors.extend(
                [
                    f"iframe[src*='{keyword}']",
                    f"a[href*='{keyword}']",
                    f"img[src*='{keyword}']",
                    f"div[id*='{keyword}']",
                    f"div[class*='{keyword}']",
                ]
            )
        selectors = kw_selectors + selectors
    selectors.extend(COMMON_SELECTORS)
    return selectors


def collect_visible_elements(
    driver: webdriver.Chrome,
    selectors: list[str],
    seen_keys: set[str] | None = None,
) -> tuple[list[dict], list[str], set[str]]:
    collected: list[dict] = []
    selected: list[str] = []
    seen_keys = seen_keys or set()

    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue

        for element in elements:
            try:
                if not element.is_displayed():
                    continue

                element_id = ""
                try:
                    element_id = str(element.get_attribute("id") or "")
                except Exception:
                    element_id = ""

                if element_id:
                    dedupe_key = f"id:{element_id}"
                else:
                    try:
                        rect = element.rect or {}
                    except Exception:
                        rect = {}
                    x = int(rect.get("x", 0))
                    y = int(rect.get("y", 0))
                    w = int(rect.get("width", 0))
                    h = int(rect.get("height", 0))
                    try:
                        tag_name = (element.tag_name or "").lower()
                    except Exception:
                        tag_name = ""
                    try:
                        class_name = (element.get_attribute("class") or "").strip()[:120]
                    except Exception:
                        class_name = ""
                    dedupe_key = f"{selector}|{tag_name}|{class_name}|{x}|{y}|{w}|{h}"

                if dedupe_key in seen_keys:
                    continue

                seen_keys.add(dedupe_key)
                collected.append({"element": element, "selector": selector})
                if selector not in selected:
                    selected.append(selector)
            except Exception:
                continue

    return collected, selected, seen_keys


def collect_visible_elements_by_scrolling(
    driver: webdriver.Chrome,
    selectors: list[str],
    max_steps: int = 14,
    pause_seconds: float = 2.0,
) -> tuple[list[dict], list[str]]:
    all_items: list[dict] = []
    all_selectors: list[str] = []
    seen_keys: set[str] = set()

    try:
        viewport_h = int(driver.execute_script("return Math.max(window.innerHeight || 0, 1);") or 900)
        page_h = int(driver.execute_script("return Math.max(document.body.scrollHeight || 0, 1);") or 2000)
    except Exception:
        viewport_h = 900
        page_h = 2000

    positions = [0]
    y = viewport_h
    while y < page_h and len(positions) < max_steps:
        positions.append(y)
        y += viewport_h

    if positions[-1] != max(page_h - viewport_h, 0):
        positions.append(max(page_h - viewport_h, 0))

    for pos in positions[:max_steps]:
        try:
            driver.execute_script("window.scrollTo(0, arguments[0]);", pos)
            time.sleep(pause_seconds)
        except Exception:
            pass

        batch, matched, seen_keys = collect_visible_elements(driver, selectors, seen_keys=seen_keys)
        if batch:
            all_items.extend(batch)
        for selector in matched:
            if selector not in all_selectors:
                all_selectors.append(selector)

    try:
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass

    return all_items, all_selectors


def run_banner_check(payload: dict, latest_domains: set[str] | None = None) -> dict:
    sites_raw = payload.get("sites", "")
    keyword_raw = str(payload.get("adserver_keyword", "")).strip().lower()
    adserver_kws = [item.strip() for item in keyword_raw.split(",") if item.strip()]
    refresh_count = max(1, min(int(payload.get("refreshes", 1)), 30))
    concurrency = max(1, min(int(payload.get("concurrency", 2)), 8))
    size_rules = parse_size_rules(str(payload.get("size_rules", "")))
    tolerance = max(0, min(int(payload.get("size_tolerance", 10)), 50))
    enable_size_check = parse_bool(payload.get("enable_size_check"), default=False)
    resolve_redirect_target = parse_bool(payload.get("resolve_redirect_target"), default=True)
    capture_destination_screenshot = parse_bool(payload.get("capture_destination_screenshot"), default=True)
    max_redirect_checks_per_site = max(0, min(int(payload.get("max_redirect_checks_per_site", 20)), 200))
    banner_load_delay_seconds = max(2.0, min(float(payload.get("banner_load_delay_seconds", 2.0)), 10.0))

    site_list = [line.strip() for line in sites_raw.splitlines() if line.strip()]
    latest_domains = latest_domains or set()

    def check_one_site(site_url: str) -> dict:
        site_result: dict = {"site": site_url, "refreshes": []}
        driver = None
        redirect_checks_count = 0

        try:
            driver = build_driver()
        except Exception as exc:
            site_result["error"] = f"Driver Error: {exc}"
            return site_result

        url = site_url if site_url.startswith("http") else f"https://{site_url}"

        try:
            for refresh_index in range(1, refresh_count + 1):
                refresh_result: dict = {
                    "refresh": refresh_index,
                    "banners": [],
                    "banner_count": 0,
                    "selector_used": None,
                    "selectors_matched": [],
                }

                try:
                    driver.get(url)
                    time.sleep(banner_load_delay_seconds)
                    page_h = get_page_height(driver)

                    selectors = build_selectors(adserver_kws)
                    found_elements, matched_selectors = collect_visible_elements_by_scrolling(
                        driver,
                        selectors,
                        pause_seconds=banner_load_delay_seconds,
                    )
                    selector_used = matched_selectors[0] if matched_selectors else None

                    refresh_result["selector_used"] = selector_used
                    refresh_result["selectors_matched"] = matched_selectors
                    refresh_result["banner_count"] = len(found_elements)

                    for index, item in enumerate(found_elements, start=1):
                        element = item["element"]
                        source_selector = item["selector"]
                        banner_info: dict = {"index": index}
                        banner_info["source_selector"] = source_selector

                        try:
                            location = element.location
                            size = element.size
                            banner_info["x"] = int(location.get("x", 0))
                            banner_info["y"] = int(location.get("y", 0))
                            banner_info["w"] = int(size.get("width", 0))
                            banner_info["h"] = int(size.get("height", 0))
                            banner_info["position"] = classify_position(int(location.get("y", 0)), page_h)
                        except Exception:
                            banner_info["x"] = 0
                            banner_info["y"] = 0
                            banner_info["w"] = 0
                            banner_info["h"] = 0
                            banner_info["position"] = "Unknown"

                        try:
                            banner_info["text"] = (element.text or "")[:200].strip()
                        except Exception:
                            banner_info["text"] = ""

                        link = resolve_link(element, base_url=url)
                        banner_info["link"] = link
                        banner_info["destination_link"] = extract_destination_link(link)
                        domain, http_status, has_http = check_link_status(link)
                        banner_info["domain"] = domain or ""
                        banner_info["http_status"] = http_status
                        banner_info["match_adserver"] = (
                            any(keyword in (domain or "") for keyword in adserver_kws)
                            if adserver_kws
                            else has_http
                        )

                        redirect_target = banner_info["destination_link"] or ""
                        redirect_domain = urlparse(redirect_target).netloc.replace("www.", "").lower() if redirect_target else ""
                        redirect_status: int | str = "—"
                        redirect_resolved_by = "query_param" if redirect_target else ""
                        destination_screenshot = ""
                        redirect_resolution_skipped = False

                        if resolve_redirect_target and redirect_checks_count < max_redirect_checks_per_site:
                            redirect_checks_count += 1
                            req_final_url, req_final_domain, req_status = resolve_redirect_with_requests(link)
                            if req_final_url and req_final_url != link:
                                redirect_target = req_final_url
                                redirect_domain = req_final_domain
                                redirect_status = req_status
                                redirect_resolved_by = "http_redirect"

                            should_use_browser = (
                                not redirect_target
                                or redirect_target == link
                            )

                            if should_use_browser:
                                browser_final_url, browser_final_domain, browser_shot = resolve_redirect_with_browser(
                                    driver,
                                    link,
                                    capture_destination_screenshot=capture_destination_screenshot,
                                )
                                if browser_final_url and browser_final_url not in {"about:blank", link}:
                                    redirect_target = browser_final_url
                                    redirect_domain = browser_final_domain
                                    redirect_resolved_by = "browser_redirect"
                                    _, final_status, _ = check_link_status(redirect_target)
                                    redirect_status = final_status
                                if browser_shot:
                                    destination_screenshot = browser_shot
                        elif resolve_redirect_target:
                            redirect_resolution_skipped = True

                        banner_info["redirect_target"] = redirect_target
                        banner_info["redirect_domain"] = redirect_domain
                        banner_info["redirect_http_status"] = redirect_status
                        banner_info["redirect_resolved_by"] = redirect_resolved_by or "none"
                        banner_info["destination_screenshot"] = destination_screenshot
                        banner_info["redirect_resolution_skipped"] = redirect_resolution_skipped
                        banner_info["final_destination_link"] = (
                            redirect_target or banner_info["destination_link"] or link or "—"
                        )

                        try:
                            element_png = element.screenshot_as_png
                            banner_info["element_screenshot"] = base64.b64encode(element_png).decode("utf-8")
                        except Exception:
                            banner_info["element_screenshot"] = ""

                        if not banner_info["element_screenshot"]:
                            image_src = resolve_image_src(element, base_url=url)
                            banner_info["element_image_src"] = image_src
                            banner_info["element_screenshot"] = fetch_image_as_base64(image_src)
                        else:
                            banner_info["element_image_src"] = ""

                        if not banner_info["element_screenshot"]:
                            try:
                                fallback_page_png = driver.get_screenshot_as_png()
                                banner_info["element_screenshot"] = base64.b64encode(fallback_page_png).decode("utf-8")
                            except Exception:
                                banner_info["element_screenshot"] = ""

                        qc = evaluate_banner(
                            banner=banner_info,
                            size_rules=size_rules,
                            tolerance=tolerance,
                            required_keyword=keyword_raw,
                            latest_domains=latest_domains,
                            enable_size_check=enable_size_check,
                        )
                        banner_info["qc_status"] = qc["status"]
                        banner_info["qc_reasons"] = qc["reasons"]

                        if index == 1:
                            try:
                                driver.execute_script(
                                    "arguments[0].style.outline='4px solid #f59e0b'; arguments[0].style.outlineOffset='2px';",
                                    element,
                                )
                                page_png = driver.get_screenshot_as_png()
                                refresh_result["page_screenshot"] = base64.b64encode(page_png).decode("utf-8")
                                driver.execute_script(
                                    "arguments[0].style.outline=''; arguments[0].style.outlineOffset='';",
                                    element,
                                )
                            except Exception:
                                refresh_result["page_screenshot"] = ""

                        refresh_result["banners"].append(banner_info)
                except Exception as exc:
                    refresh_result["error"] = str(exc)

                site_result["refreshes"].append(refresh_result)
        finally:
            if driver:
                driver.quit()

        summary = summarize_site_result(site_result)
        site_result.update(summary)

        links = set()
        redirects = set()
        for refresh in site_result.get("refreshes", []):
            for banner in refresh.get("banners", []):
                link_val = str(banner.get("link") or "").strip()
                if link_val and link_val != "—":
                    links.add(link_val)
                redirect_val = str(banner.get("redirect_target") or "").strip()
                if redirect_val and redirect_val != "—":
                    redirects.add(redirect_val)

        site_result["links_found"] = sorted(links)
        site_result["redirect_targets_found"] = sorted(redirects)
        return site_result

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(check_one_site, site): site for site in site_list}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"site": futures[future], "error": str(exc), "refreshes": []})

    total_sites = len(results)
    pass_sites = sum(1 for item in results if item.get("site_status") == "PASS")
    fail_sites = total_sites - pass_sites
    total_banners = sum(item.get("banner_total", 0) for item in results)

    return {
        "results": results,
        "summary": {
            "total_sites": total_sites,
            "pass_sites": pass_sites,
            "fail_sites": fail_sites,
            "total_banners": total_banners,
            "refreshes": refresh_count,
            "size_rules": [f"{rule.width}x{rule.height}" for rule in size_rules],
            "size_tolerance": tolerance,
            "enable_size_check": enable_size_check,
            "resolve_redirect_target": resolve_redirect_target,
            "capture_destination_screenshot": capture_destination_screenshot,
            "max_redirect_checks_per_site": max_redirect_checks_per_site,
            "banner_load_delay_seconds": banner_load_delay_seconds,
            "keyword": keyword_raw,
        },
    }
