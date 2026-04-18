# Banner QC Automation Engine

This project provides a standalone service for automated banner quality control, complete with an independent API and a web-based dashboard for running tests and reviewing results.

## 1. Project Overview

The primary goal of this engine is to automate the verification of advertising banners across a portfolio of websites. It addresses key quality control challenges by ensuring banners are correctly displayed, functional, and compliant with brand guidelines. The system is designed to be robust, handling dynamic content and complex redirect chains, while providing detailed evidence for every check.

### Key Capabilities

*   **Banner Validation**: Verifies the existence, count, and size of banners against predefined zone rules. It can detect discrepancies such as incorrect dimensions or missing elements.
*   **Link Processing**: Ensures each banner has a valid, functional link. The engine resolves redirect chains to identify the final destination URL and verifies its status.
*   **Domain Verification**: Checks if the banner's destination domain matches the latest approved brand domain. This is achieved by integrating with an external API that serves as the single source of truth for domain lists.
*   **Optimized Data Collection**: Supports configurable page reloads and scrolling to effectively capture banners that are loaded dynamically or rotated on each page view.
*   **Automated System**: The worker can be scheduled (e.g., via cronjob) to run checks automatically. All results, including screenshots and detailed logs, are saved as structured JSON for reporting and historical analysis.

---

## 2. 
*   `POST /api/banner/check`: The main endpoint to trigger a banner check.
*   `GET /api/history`: Lists all available history files.
*   `GET /api/history/<filename>`: Retrieves a specific test result.
*   `GET /api/domain_source`: Checks the status of the domain API connection.
*   `POST /api/domain_source/refresh`: Manually triggers a refresh of the domain cache.

---

## 5. Sample API Payload

```json
{
  "sites": "https://example.com\nhttps://abc.com",
  "adserver_keyword": "haywin,febet",
  "size_rules": "300x250,728x90",
  "refreshes": 1,
  "concurrency": 2,
  "size_tolerance": 10,
  "enable_size_check": true,
  "resolve_redirect_target": true,
  "capture_destination_screenshot": true
}
```

