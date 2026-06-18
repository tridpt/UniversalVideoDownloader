# Đóng góp cho Universal Video Downloader

Cảm ơn bạn đã quan tâm đến việc đóng góp! Dưới đây là hướng dẫn ngắn gọn.

## Thiết lập môi trường

```bash
git clone https://github.com/tridpt/UniversalVideoDownloader.git
cd UniversalVideoDownloader
pip install -r requirements-dev.txt
```

## Trước khi gửi Pull Request

Hãy đảm bảo cả lint và test đều pass cục bộ:

```bash
ruff check .
pytest -v
```

CI sẽ tự chạy lại các bước này trên Python 3.10–3.13 khi bạn mở PR.

## Quy ước code

- Giữ phần logic thuần (không phụ thuộc GUI) trong `core.py`, `downloader.py`,
  `config_store.py`, `queue_logic.py` để có thể kiểm thử. `main.py` chỉ nên chứa
  giao diện và phần điều phối.
- Thêm test cho mọi logic mới trong các module thuần.
- Tuân theo cấu hình `ruff.toml` (đã bỏ qua giới hạn độ dài dòng cho chuỗi tiếng Việt).
- Cập nhật `CHANGELOG.md` trong mục `[Unreleased]` cho các thay đổi đáng chú ý.

## Báo lỗi

Mở một issue kèm: các bước tái hiện, kết quả mong đợi, kết quả thực tế,
và hệ điều hành + phiên bản Python bạn đang dùng.
