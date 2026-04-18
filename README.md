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

## 2. Development Status & Action Plan

This section outlines the current state of the project based on the D5AT task board and provides a clear roadmap for future development.

### Current Sprint: Core Validation Engine (Epic A & B)

Our immediate focus is on perfecting the core logic for banner validation and ensuring a reliable data source for domain checks.

| Task ID | Feature | Status | Details |
| :--- | :--- | :--- | :--- |
| **D5AT-5** | **Newest Domain Check** | **Done** | The system successfully integrates with the domain API. A resilient, non-blocking client with caching and retry logic has been implemented to handle potential API downtime. |
| **D5AT-4** | **Link & Domain Extraction** | **Done** | The engine robustly extracts destination links from various HTML attributes (`href`, `onclick`, `data-*`) and accurately resolves the final domain from complex redirect chains. |
| **D5AT-2** | **Domain List Receiver** | **Done** | A service to pull and cache the latest domain list from the API is complete. This ensures the checker always has access to up-to-date information. |
| **D5AT-3** | **Banner Size Validation** | **In Progress** | The logic to measure banner dimensions is implemented. The next step is to enable the rule and provide clear `expected vs. actual size` reporting in the failure reasons. |
| **D5AT-9** | **Domain Logic Regression** | **To Do** | The QC team will build a comprehensive test suite with valid, invalid, and outdated domains to ensure the validation rules have no false positives or negatives. |

### Next Sprint: CMS Integration & Operations (Epic C)

Once the core engine is stable, we will focus on operationalizing the data and integrating it with the central CMS.

| Task ID | Feature | Status | Details |
| :--- | :--- | :--- | :--- |
| **D5AT-8** | **Report Export** | **Done** | A CSV export feature has been implemented in the dashboard, allowing teams to download a summary of test runs. |
| **D5AT-6** | **Database Structure** | **To Do** | The backend team will finalize the JSON output schema, which will serve as the blueprint for the CMS team to design the database tables for storing results. |
| **D5AT-7** | **CMS User Management** | **To Do** | The CMS team will develop user and role management features after the database structure is finalized. |

### Future Scope (Phase 2)

*   **AI/OCR Integration**: Implement OCR to read text content from banner images, verifying brand messaging and promotional details.
*   **Advanced Reporting**: Develop automated daily email/Slack reports with key metrics and alerts for high-risk sites.

---

## 3. How to Run Locally

1.  **Navigate to the project directory:**
    ```bash
    cd /Users/user/Documents/workspace/Check-banner
    ```

2.  **Set up a Python virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment:**
    ```bash
    cp .env.example .env
    ```

5.  **Run the application:**
    ```bash
    python3 app.py
    ```

The dashboard will be available at `http://127.0.0.1:8011`.

---

## 4. API Endpoints

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

