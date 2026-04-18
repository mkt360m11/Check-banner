# Banner QC (Standalone)

Project này tách riêng phần kiểm tra banner khỏi `auto_detect_site`, có dashboard và API độc lập.

> ⚠️ **Ghi chú hiện tại (Sprint 1):**
> Có trường hợp hệ thống trả về **FAIL dù thực tế site có nhiều banner QC** (false-negative).
> Vấn đề này đã được ghi nhận để tiếp tục cải thiện rule và selector.

## Tính năng

- Check banner theo danh sách site.
- Cấu hình số lần refresh, concurrency.
- Rule fail-case theo kích thước zone (`size_rules`) và tolerance.
- Kiểm tra link/domain/http status và match keyword adserver.
- Kiểm tra domain mới nhất qua API ngoài (nếu cấu hình `BANNER_DOMAIN_API`).
- Lưu lịch sử kết quả vào thư mục `history/` và load lại từ dashboard.

## Đã phát triển được (Sprint 1)

- Tách riêng dự án banner check thành module độc lập.
- Có dashboard riêng để chạy check, xem summary, xem history, export CSV.
- Có rule engine đánh giá fail-case cơ bản:
  - Sai kích thước so với zone (`size_rules` + `size_tolerance`).
  - Thiếu link / link lỗi HTTP.
  - Không match keyword adserver.
  - Domain không nằm trong danh sách latest domain (nếu có API).
- Có API cache/refresh domain source để đối chiếu domain mới nhất.

## Known Issues

- **False-negative FAIL:** Một số site có banner thực tế nhưng kết quả vẫn FAIL.
- **Nguyên nhân khả dĩ hiện tại:**
  - Selector chưa phủ đủ các layout custom theo site.
  - Banner lazy-load/rotate theo thời điểm, 1 lần load đầu chưa thấy hết.
  - Rule match keyword/domain còn chặt với một số site đặc thù.
  - Link lấy từ parent/child chưa bắt được hết dạng redirect script.
- **Hướng xử lý tiếp theo:**
  - Mở rộng selector theo từng nhóm layout.
  - Tăng `refreshes` theo profile site và lưu thêm fail evidence.
  - Bổ sung click-flow thật để lấy final redirect URL.
  - Thêm chế độ PASS theo ngưỡng (ví dụ có banner hợp lệ ở >= N lần refresh).

## Cấu trúc

- `app.py`: Flask app + API + dashboard route.
- `banner_checker.py`: Selenium crawler/checker.
- `rule_engine.py`: Rule PASS/FAIL cho fail-case.
- `history_store.py`: Lưu và đọc history JSON.
- `templates/dashboard.html`: Dashboard riêng.

## Chạy local

```bash
cd /Users/user/Documents/workspace/auto_detect_site/banner_qc
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Mở dashboard tại `http://127.0.0.1:8011`.

## API chính

- `POST /api/banner/check`
- `GET /api/history`
- `GET /api/history/<filename>`
- `GET /api/domain_source`
- `POST /api/domain_source/refresh`
- `POST /api/domain_source/action` (action call API thủ công, sẵn sàng cho D5AT-5)

## Domain API action mode (phù hợp khi API chưa có ngay)

- Có thể để `BANNER_DOMAIN_API` trống, hệ thống vẫn chạy banner check bình thường.
- Khi chưa có API, `state.status` sẽ là `no_api` và dùng fallback rỗng.
- Khi API lỗi tạm thời, hệ thống chuyển `cache_fallback` nếu đã có cache domain từ lần gọi trước.
- Có thể trigger action thủ công:

```bash
curl -X POST http://127.0.0.1:8011/api/domain_source/action
```

- Có thể tinh chỉnh call API qua biến môi trường:
  - `BANNER_DOMAIN_API_TIMEOUT`
  - `BANNER_DOMAIN_API_RETRIES`
  - `BANNER_DOMAIN_API_RETRY_DELAY`

## Payload mẫu

```json
{
  "sites": "https://example.com\nhttps://abc.com",
  "adserver_keyword": "haywin,febet",
  "size_rules": "300x250,728x90",
  "refreshes": 1,
  "concurrency": 2,
  "size_tolerance": 10
}
```

## MVP Demo Mode (khuyến nghị để trình cấp trên)

Giai đoạn demo có thể chạy theo hướng thu thập evidence/link, không siết rule:

- Để trống `adserver_keyword` để lấy banner/link không phụ thuộc keyword.
- Đặt `enable_size_check=false` để bỏ check `size_mismatch`.
- Có thể để trống `size_rules`.

Ví dụ payload MVP:

```json
{
  "sites": "http://vebo.cx",
  "adserver_keyword": "",
  "size_rules": "",
  "refreshes": 1,
  "concurrency": 1,
  "size_tolerance": 10,
  "enable_size_check": false,
  "resolve_redirect_target": true,
  "capture_destination_screenshot": true
}
```

Trong mode này hệ thống sẽ cố gắng:

- Quét banner theo nhiều vị trí trên trang (kể cả khi cần scroll).
- Resolve trang đích redirect (ưu tiên qua HTTP, fallback bằng browser tab).
- Lưu ảnh bằng chứng: `element_screenshot`, `page_screenshot`, và `destination_screenshot` (nếu bắt được).

## Changelog

- Xem chi tiết tại `CHANGELOG.md`.
