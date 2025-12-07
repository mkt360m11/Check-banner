import asyncio
import httpx
from playwright.async_api import async_playwright
import logging
from generate_report import generate_html_report
import os
from urllib.parse import urlparse

# --- 1. Cấu hình & Dữ liệu đầu vào ---

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Danh sách các selector phổ biến để tự động dò tìm quảng cáo
# Ưu tiên các selector "chắc chắn" là quảng cáo trước
HIGH_CONFIDENCE_SELECTORS = [
    "ins[data-revive-zoneid]", # Revive Adserver
    "ins[class*='ads']",
    "div[id*='header_bar']", "div[class*='header_bar']", # User specific
    "div[id*='pc_header_bar']",
    "iframe[src*='ads']", "iframe[id*='google_ads']",
]

COMMON_AD_SELECTORS = [
    "div[id*='banner']", "div[class*='banner']",
    "div[id*='ad-']", "div[class*='ad-']",
    "div[class*='advertisement']",
    "a[href*='doubleclick']", "a[href*='tracking']",
    "img[src*='banner']",
]

# Dữ liệu mẫu (Lẽ ra sẽ được query từ Database)
TEST_SITES = [
    {
        "site_url": "https://v2.keonhacaimoi.io",
        "expected_landing_page_url": "https://hay.win",  # Kiểm tra có banner nào dẫn đến hay.win không
    }
    # Thêm 1000 site khác vào đây
]

# --- 2. Hàm kiểm tra Link & Redirect ---

async def check_redirect_and_status(link_url):
    """
    Kiểm tra HTTP Status của link banner.
    Không kiểm tra URL đích - chỉ kiểm tra link có hoạt động (HTTP 200).
    """
    try:
        # Sử dụng httpx (async HTTP client) để không làm block luồng chính
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            logging.info(f"   -> PING: {link_url}")
            response = await client.head(link_url, follow_redirects=True) # Dùng HEAD để tiết kiệm băng thông

            final_url = str(response.url)
            status_code = response.status_code

            # Chỉ kiểm tra HTTP 200 (OK)
            is_status_ok = status_code == 200

            logging.info(f"   -> Kết quả: Status={status_code}, Đích cuối={final_url}")
            
            return {
                "status_code": status_code,
                "final_url": final_url,
                "pass_status": is_status_ok,
            }

    except httpx.RequestError as e:
        logging.error(f"   !!! LỖI REQUEST: {e}")
        return {
            "status_code": 0,
            "final_url": "LỖI KẾT NỐI",
            "pass_status": False,
            "pass_url": False
        }

# --- 3. Logic Kiểm tra Từng Site ---

async def run_test_for_site(browser, site_data):
    """
    Thực thi toàn bộ logic kiểm tra cho một Site URL.
    Tìm TẤT CẢ banner trên trang và kiểm tra từng banner.
    """
    url = site_data["site_url"]
    zone_selector = site_data.get("zone_id") # Có thể None
    expected_url = site_data.get("expected_landing_page_url") # Có thể None
    
    results = {
        "url": url, 
        "status": "PASS", 
        "errors": [],
        "details": {
            "banners": [],  # Danh sách tất cả banner tìm thấy
            "domains_found": [],  # Danh sách các domain tìm thấy
        }
    }
    
    context = await browser.new_context()
    page = await context.new_page()

    try:
        logging.info(f"*** BẮT ĐẦU: {url}")
        
        # 5. Access: Mở URL của site
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # 6. Locate Ads: Tìm TẤT CẢ banner quảng cáo
        banner_elements = []
        selector_used = None
        
        if zone_selector:
            # Nếu có zone_id, tìm chính xác
            banner_elements = await page.locator(zone_selector).all()
            selector_used = zone_selector
            logging.info(f"   -> Tìm thấy {len(banner_elements)} banner với zone_id")
        else:
            # Nếu KHÔNG có zone_id, thử dò tìm (Auto-detect)
            logging.info(f"   -> Không có zone_id, đang tự động dò tìm TẤT CẢ banner...")
            
            # Wait for ads to load (Async/Lazy load)
            logging.info(f"   -> Chờ 3s để quảng cáo load...")
            await page.wait_for_timeout(3000)
            
            # Strategy 1: High Confidence Selectors (Revive, etc.)
            for selector in HIGH_CONFIDENCE_SELECTORS:
                possible_elements = await page.locator(selector).all()
                visible_elements = []
                for elem in possible_elements:
                    if await elem.is_visible():
                        visible_elements.append(elem)
                
                if visible_elements:
                    logging.info(f"   -> Đã tìm thấy {len(visible_elements)} banner (High Confidence) với selector: {selector}")
                    banner_elements = visible_elements
                    selector_used = selector
                    break
            
            # Strategy 2: Common Selectors (Fallback)
            if not banner_elements:
                for selector in COMMON_AD_SELECTORS:
                    possible_elements = await page.locator(selector).all()
                    visible_elements = []
                    for elem in possible_elements:
                        if await elem.is_visible():
                            visible_elements.append(elem)
                    
                    if visible_elements:
                        logging.info(f"   -> Đã tìm thấy {len(visible_elements)} banner khả nghi với selector: {selector}")
                        banner_elements = visible_elements
                        selector_used = selector
                        break
        
        if not banner_elements:
             results["status"] = "FAIL"
             results["errors"].append("VISIBILITY_FAIL: Không tìm thấy banner quảng cáo (hoặc zone_id sai).")
             await context.close()
             return results

        results["details"]["selector_used"] = selector_used
        logging.info(f"   -> Tổng cộng tìm thấy {len(banner_elements)} banner")

        # 7-8. Kiểm tra TỪNG banner
        domains_found = set()
        expected_domain_found = False
        
        for idx, banner_element in enumerate(banner_elements, 1):
            logging.info(f"   -> Đang kiểm tra banner #{idx}...")
            
            banner_info = {
                "index": idx,
                "bounding_box": None,
                "original_url": None,
                "final_url": None,
                "domain": None,
                "status_code": None,
                "screenshot_path": None,
            }
            
            try:
                # Get Bounding Box
                box = await banner_element.bounding_box()
                banner_info["bounding_box"] = box
                
                # Chụp ảnh từng banner
                evidence_path = f"evidence/{url.split('//')[-1].replace('/', '_')}_banner_{idx}.png"
                os.makedirs(os.path.dirname(evidence_path), exist_ok=True)
                await banner_element.screenshot(path=evidence_path)
                banner_info["screenshot_path"] = evidence_path
                logging.info(f"      - Đã chụp ảnh tại: {evidence_path}")
                
                # Lấy Link
                ad_link = await banner_element.get_attribute("href")
                if not ad_link:
                    # Try to find a child 'a' tag
                    try:
                        ad_link = await banner_element.locator("a").first.get_attribute("href")
                    except:
                        pass
                
                if not ad_link:
                    logging.warning(f"      - Banner #{idx}: Không lấy được link")
                    banner_info["original_url"] = "NO_LINK"
                    results["details"]["banners"].append(banner_info)
                    continue
                
                banner_info["original_url"] = ad_link
                logging.info(f"      - Original URL: {ad_link}")
                
                # Check Redirect
                redirect_info = await check_redirect_and_status(ad_link)
                banner_info["status_code"] = redirect_info["status_code"]
                banner_info["final_url"] = redirect_info["final_url"]
                
                # Extract domain
                final_domain = urlparse(redirect_info["final_url"]).netloc.replace("www.", "")
                banner_info["domain"] = final_domain
                domains_found.add(final_domain)
                
                logging.info(f"      - Domain: {final_domain}, Status: {redirect_info['status_code']}")
                
                # Kiểm tra expected_url nếu có
                if expected_url:
                    expected_domain = urlparse(expected_url).netloc.replace("www.", "")
                    if final_domain == expected_domain:
                        expected_domain_found = True
                        logging.info(f"      - ✅ Tìm thấy banner khớp với expected domain: {expected_domain}")
                
                # Kiểm tra HTTP status
                if not redirect_info["pass_status"]:
                    logging.warning(f"      - ⚠️ Banner #{idx}: HTTP {redirect_info['status_code']}")
                
            except Exception as e:
                logging.error(f"      - Lỗi khi kiểm tra banner #{idx}: {e}")
                banner_info["error"] = str(e)
            
            results["details"]["banners"].append(banner_info)
        
        # Lưu danh sách domains
        results["details"]["domains_found"] = sorted(list(domains_found))
        logging.info(f"   -> Các domain tìm thấy: {', '.join(results['details']['domains_found'])}")
        
        # Đánh giá kết quả
        if expected_url:
            # Nếu có expected_url, kiểm tra có ít nhất 1 banner khớp không
            if not expected_domain_found:
                results["status"] = "FAIL"
                expected_domain = urlparse(expected_url).netloc.replace("www.", "")
                results["errors"].append(f"EXPECTED_URL_NOT_FOUND: Không tìm thấy banner nào dẫn đến {expected_domain}. Tìm thấy: {', '.join(results['details']['domains_found'])}")
            else:
                logging.info(f"   -> ✅ PASS: Tìm thấy banner khớp với expected URL")
        else:
            # Nếu không có expected_url, chỉ cần có ít nhất 1 banner hoạt động
            working_banners = [b for b in results["details"]["banners"] if b.get("status_code") == 200]
            if not working_banners:
                results["status"] = "FAIL"
                results["errors"].append("NO_WORKING_BANNER: Không có banner nào hoạt động (HTTP 200).")
            else:
                logging.info(f"   -> ✅ PASS: Tìm thấy {len(working_banners)}/{len(banner_elements)} banner hoạt động")

    except Exception as e:
        # Lỗi chung (Ví dụ: Timeout, Element không tìm thấy)
        results["status"] = "FAIL"
        results["errors"].append(f"GENERAL_ERROR: {str(e)}")
        logging.error(f"!!! Site {url} LỖI TỔNG QUÁT: {e}")

    finally:
        # Đóng Context/Page
        await context.close()

    logging.info(f"*** KẾT THÚC: {url} -> {results['status']}")
    
    # 9/10. Xử lý Báo cáo/Alert (Sẽ được xử lý trong hàm chính)
    return results

# --- 4. Chạy Song Song (Parallel Execution) & Báo cáo ---

async def main_runner():
    all_results = []
    
    # 3. Chuẩn bị Tool (Khởi tạo Playwright)
    async with async_playwright() as p:
        # Chọn trình duyệt (ví dụ: Chromium)
        browser = await p.chromium.launch(headless=True) 
        
        logging.info(f"Khởi tạo {len(TEST_SITES)} tác vụ kiểm tra...")
        
        # 4. Chạy song song (Parallel execution)
        # Tạo danh sách các tác vụ (Tasks)
        tasks = [run_test_for_site(browser, site) for site in TEST_SITES]
        
        # Chạy tất cả tasks cùng lúc
        all_results = await asyncio.gather(*tasks)

        await browser.close()
        
    # 9. Xử lý Báo cáo & Cảnh báo (Reporting)
    
    fail_count = 0
    logging.info("\n--- BÁO CÁO TỔNG KẾT ---")
    
    for result in all_results:
        if result["status"] == "FAIL":
            fail_count += 1
            logging.error(f"🚨🚨🚨 FAIL SITE: {result['url']}")
            for error in result['errors']:
                logging.error(f"    - Lỗi: {error}")
            
            # --- Tích hợp Telegram Alert ở đây ---
            # Ví dụ: send_telegram_alert(result)
            
        else:
            logging.info(f"✅ PASS SITE: {result['url']}")

    logging.info(f"\n--- KẾT QUẢ CUỐI CÙNG: {fail_count}/{len(TEST_SITES)} sites FAILED. ---")
    
    # Tạo báo cáo HTML
    report_file = generate_html_report(all_results)
    logging.info(f"\n📄 Mở file báo cáo để xem: {report_file}")
    
    return all_results


if __name__ == "__main__":
    # Đảm bảo bạn đã cài đặt các thư viện:
    # pip install playwright httpx
    # playwright install chromium
    
    asyncio.run(main_runner())
