import json
import os
from datetime import datetime
from pathlib import Path
import html

def generate_html_report(results, output_file="report.html"):
    """
    Tạo báo cáo HTML đẹp mắt với hình ảnh evidence.
    """
    
    # CSS styles
    css_styles = """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); margin-bottom: 30px; text-align: center; }
        .header h1 { color: #333; font-size: 2.5em; margin-bottom: 10px; }
        .header .timestamp { color: #666; font-size: 1.1em; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .summary-card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); text-align: center; }
        .summary-card h3 { color: #666; font-size: 0.9em; text-transform: uppercase; margin-bottom: 10px; }
        .summary-card .number { font-size: 3em; font-weight: bold; margin-bottom: 5px; }
        .summary-card.total .number { color: #667eea; }
        .summary-card.pass .number { color: #10b981; }
        .summary-card.fail .number { color: #ef4444; }
        .site-card { background: white; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); margin-bottom: 20px; overflow: hidden; transition: transform 0.3s ease; }
        .site-card:hover { transform: translateY(-5px); box-shadow: 0 10px 25px rgba(0,0,0,0.15); }
        .site-header { padding: 20px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f0f0f0; }
        .site-header.pass { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; }
        .site-header.fail { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; }
        .site-url { font-size: 1.3em; font-weight: bold; word-break: break-all; }
        .status-badge { padding: 8px 20px; border-radius: 25px; font-weight: bold; font-size: 1.1em; background: rgba(255,255,255,0.3); }
        .site-body { padding: 30px; }
        .detail-row { margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #e5e7eb; }
        .detail-row:last-child { border-bottom: none; }
        .detail-label { font-weight: bold; color: #374151; margin-bottom: 8px; font-size: 0.95em; text-transform: uppercase; letter-spacing: 0.5px; }
        .detail-value { color: #6b7280; word-break: break-all; line-height: 1.6; }
        .detail-value code { background: #f3f4f6; padding: 2px 8px; border-radius: 4px; font-family: 'Courier New', monospace; font-size: 0.9em; }
        .screenshot { margin-top: 15px; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        .screenshot img { width: 100%; height: auto; display: block; }
        .error-list { background: #fef2f2; border-left: 4px solid #ef4444; padding: 15px 20px; border-radius: 8px; }
        .error-list li { margin-left: 20px; margin-bottom: 8px; color: #991b1b; }
        .bounding-box { background: #f0f9ff; border-left: 4px solid #0284c7; padding: 15px 20px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 0.9em; }
        @media (max-width: 768px) {
            .header h1 { font-size: 1.8em; }
            .summary { grid-template-columns: 1fr; }
            .site-header { flex-direction: column; gap: 10px; text-align: center; }
        }
    """
    
    # Tạo HTML cho từng site
    site_cards_html = ""
    
    for result in results:
        status = result["status"]
        url = result["url"]
        errors = result.get("errors", [])
        details = result.get("details", {})
        banners = details.get("banners", [])
        domains_found = details.get("domains_found", [])
        
        # Errors HTML
        errors_html = ""
        if errors:
            error_items = "".join([f"<li>{error}</li>" for error in errors])
            errors_html = f"""
            <div class="detail-row">
                <div class="detail-label">⚠️ Lỗi</div>
                <ul class="error-list">
                    {error_items}
                </ul>
            </div>
            """
        
        # Details HTML
        details_html = ""
        
        if details.get("selector_used"):
            details_html += f"""
            <div class="detail-row">
                <div class="detail-label">🎯 Selector Sử Dụng</div>
                <div class="detail-value"><code>{details['selector_used']}</code></div>
            </div>
            """
        
        # Domains found summary
        if domains_found:
            domains_list = ", ".join(domains_found)
            details_html += f"""
            <div class="detail-row">
                <div class="detail-label">� Các Domain Tìm Thấy ({len(domains_found)})</div>
                <div class="detail-value"><strong>{domains_list}</strong></div>
            </div>
            """
        
        # Banner details
        if banners:
            details_html += f"""
            <div class="detail-row">
                <div class="detail-label">� Chi Tiết {len(banners)} Banner</div>
            </div>
            """
            
            for banner in banners:
                idx = banner.get("index", "?")
                domain = banner.get("domain", "N/A")
                status_code = banner.get("status_code", "N/A")
                original_url = banner.get("original_url", "N/A")
                screenshot_path = banner.get("screenshot_path")
                box = banner.get("bounding_box")
                error = banner.get("error")
                
                # Status badge for each banner
                status_badge = ""
                if status_code == 200:
                    status_badge = '<span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85em;">✅ OK</span>'
                elif status_code == "N/A" or original_url == "NO_LINK":
                    status_badge = '<span style="background: #6b7280; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85em;">⚠️ NO LINK</span>'
                else:
                    status_badge = f'<span style="background: #ef4444; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.85em;">❌ {status_code}</span>'
                
                banner_html = f"""
                <div style="background: #f9fafb; padding: 20px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #667eea;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin: 0; color: #374151;">Banner #{idx}</h4>
                        {status_badge}
                    </div>
                """
                
                if domain and domain != "N/A":
                    banner_html += f'<div style="margin-bottom: 8px;"><strong>🌐 Domain:</strong> <code style="background: #e5e7eb; padding: 2px 8px; border-radius: 4px;">{domain}</code></div>'
                
                if original_url and original_url != "NO_LINK":
                    # Escape URL for safe HTML output and make it clickable (open in new tab)
                    safe_url = html.escape(original_url)
                    banner_html += f'<div style="margin-bottom: 8px; word-break: break-all;"><strong>🔗 URL:</strong> <a href="{safe_url}" target="_blank" rel="noopener noreferrer" style="font-size: 0.85em; color: #1f2937; word-break: break-all; text-decoration: underline;">{safe_url}</a></div>'
                
                if box:
                    banner_html += f'<div style="margin-bottom: 8px;"><strong>📐 Vị trí:</strong> X: {box["x"]:.0f}px, Y: {box["y"]:.0f}px, W: {box["width"]:.0f}px, H: {box["height"]:.0f}px</div>'
                
                if error:
                    banner_html += f'<div style="color: #dc2626; margin-bottom: 8px;"><strong>⚠️ Lỗi:</strong> {error}</div>'
                
                if screenshot_path and os.path.exists(screenshot_path):
                    banner_html += f"""
                    <div style="margin-top: 10px;">
                        <div style="border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                            <img src="{screenshot_path}" alt="Banner #{idx}" style="width: 100%; height: auto; display: block;">
                        </div>
                    </div>
                    """
                
                banner_html += "</div>"
                details_html += banner_html
        
        # Tạo card cho site
        status_class = "pass" if status == "PASS" else "fail"
        status_icon = "✅" if status == "PASS" else "❌"
        
        site_card = f"""
        <div class="site-card">
            <div class="site-header {status_class}">
                <div class="site-url">{url}</div>
                <div class="status-badge">{status_icon} {status}</div>
            </div>
            <div class="site-body">
                {details_html}
                {errors_html}
            </div>
        </div>
        """
        
        site_cards_html += site_card
    
    # Tính toán summary
    total_sites = len(results)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = total_sites - pass_count
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Render HTML
    final_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo Cáo Kiểm Tra Banner Quảng Cáo</title>
    <style>{css_styles}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Báo Cáo Kiểm Tra Banner Quảng Cáo</h1>
            <div class="timestamp">🕐 {timestamp}</div>
        </div>
        
        <div class="summary">
            <div class="summary-card total">
                <h3>Tổng Số Sites</h3>
                <div class="number">{total_sites}</div>
            </div>
            <div class="summary-card pass">
                <h3>✅ Thành Công</h3>
                <div class="number">{pass_count}</div>
            </div>
            <div class="summary-card fail">
                <h3>❌ Thất Bại</h3>
                <div class="number">{fail_count}</div>
            </div>
        </div>
        
        {site_cards_html}
    </div>
</body>
</html>
"""
    
    # Ghi file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_html)
    
    print(f"✅ Đã tạo báo cáo HTML tại: {output_file}")
    return output_file
