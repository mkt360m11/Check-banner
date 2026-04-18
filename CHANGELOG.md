# Changelog

Tất cả thay đổi đáng chú ý của project `banner_qc` sẽ được ghi tại đây.

## [0.1.0] - 2026-04-16

### Added

- Tách riêng dự án Banner QC từ hệ thống cũ thành project độc lập `auto_detect_site/banner_qc`.
- Backend `Flask` riêng với dashboard route `/`.
- API riêng cho banner QC:
  - `POST /api/banner/check`
  - `GET /api/history`
  - `GET /api/history/<filename>`
  - `GET /api/domain_source`
  - `POST /api/domain_source/refresh`
- Engine check banner (`banner_checker.py`) gồm:
  - Quét banner theo selector + keyword.
  - Hỗ trợ `refreshes`, `concurrency`.
  - Thu thập vị trí/kích thước/link/domain/status.
  - Chụp screenshot banner (base64) và page highlight.
- Rule engine (`rule_engine.py`) để đánh giá PASS/FAIL theo fail-case.
- History store (`history_store.py`) lưu/load kết quả JSON trong `history/`.
- Dashboard riêng (`templates/dashboard.html`) có:
  - Form chạy check.
  - Summary PASS/FAIL.
  - Bảng kết quả site.
  - Load history.
  - Export CSV.
- Tài liệu khởi tạo/chạy project trong `README.md`.
- `smoke_test.py` để test nhanh rule engine.

### Known Issues

- Có trường hợp **FAIL false-negative**: site thực tế có banner nhưng hệ thống vẫn báo FAIL.
- Các trường hợp có thể gây false-negative:
  - Selector chưa phủ đủ layout custom của từng site.
  - Banner hiển thị theo lazy-load/rotation, lần load đầu chưa xuất hiện.
  - Match keyword/domain quá chặt với một số redirect flow.
  - Chưa mô phỏng click-flow đầy đủ để xác định final URL.

### Next

- Bổ sung profile selector theo từng nhóm layout.
- Thêm chiến lược PASS theo ngưỡng refresh.
- Bổ sung click verification end-to-end cho redirect/final URL.
- Tăng lưu evidence fail-case để debug nhanh hơn.
