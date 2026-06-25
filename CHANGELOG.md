# Changelog

Tất cả các thay đổi đáng chú ý của dự án được ghi lại trong file này.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/),
và dự án tuân theo [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-06-26

### Added
- Thông báo hệ thống (toast) khi tải xong toàn bộ hàng đợi.
- Tải song song nhiều video cùng lúc (chọn 1–4 luồng).
- Kéo-thả link/đường dẫn vào cửa sổ (cần `tkinterdnd2`).
- Nút mở trực tiếp file vừa tải từ lịch sử (không chỉ mở thư mục).
- Tự dán link từ clipboard khi mở app hoặc khi focus cửa sổ.
- Nút mở thư mục tải ngay cạnh ô chọn thư mục.
- Menu chọn chất lượng động theo độ phân giải thật của video.
- Thanh tiến trình riêng cho playlist (x/y video).
- Nút "Thử lại" cho các mục tải lỗi.
- Lưu cấu hình người dùng (thư mục, định dạng, tùy chọn, giao diện) giữa các lần dùng.
- Bộ test pytest (108 test) cho các module logic thuần.
- Tích hợp liên tục (GitHub Actions) chạy ruff + pytest trên Python 3.10–3.13.

### Changed
- Đổi tên ứng dụng thành **Universal Video Downloader**: class `UniversalVideoDownloaderApp`,
  file build `UniversalVideoDownloader.spec` (tên exe tương ứng).
- Tách `main.py` thành các module: `core.py`, `downloader.py`, `config_store.py`, `queue_logic.py`.
- Tách thêm logic thuần từ `main.py` để kiểm thử được: chuyển lựa chọn cookie
  (`cookie_opts_from_choice`), tính dung lượng (`total_filesize_bytes`, `human_size_label`),
  định dạng thời lượng (`format_duration`), và dựng khoảng cắt (`build_download_ranges`).
- Thêm type hints cho các module logic.
- FFmpeg được tự động định vị qua `static_ffmpeg` hoặc PATH (không còn hardcode đường dẫn).

### Fixed
- Sửa lỗi an toàn luồng của Tkinter: mọi cập nhật giao diện từ thread phụ đều qua main thread.
- Sửa thiếu `import downloader` (phát hiện nhờ ruff) gây lỗi khi tải.
- Thêm timeout khi tải ảnh thumbnail để tránh treo.
- Sửa cảnh báo CTkLabel khi xóa ảnh (dùng `None` thay cho chuỗi rỗng).
- Gỡ hàm `_notify` định nghĩa trùng và `import os` thừa.

[Unreleased]: https://github.com/tridpt/UniversalVideoDownloader/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tridpt/UniversalVideoDownloader/releases/tag/v1.0.0
