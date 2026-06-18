"""Logic thuần cho hàng đợi tải và quyết định retry (không phụ thuộc GUI).

Tách ra để kiểm thử được phần dễ sai: chia batch theo số luồng song song,
chuẩn hóa số luồng, và quyết định có nên thử lại (tắt phụ đề) khi gặp lỗi.
"""

from __future__ import annotations

from typing import Optional


def clamp_concurrency(value, lo: int = 1, hi: int = 4) -> int:
    """Chuẩn hóa số luồng song song về khoảng [lo, hi]. Lỗi -> lo."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def make_batches(items: list, size: int) -> list[list]:
    """Chia danh sách thành các batch tối đa `size` phần tử (giữ thứ tự)."""
    size = max(1, size)
    return [items[i:i + size] for i in range(0, len(items), size)]


def should_retry_without_subtitles(task: dict, error_message: str) -> bool:
    """Quyết định có nên tải lại với phụ đề bị tắt hay không.

    Đúng khi: task đang bật phụ đề VÀ lỗi liên quan tới phụ đề hoặc bị giới hạn 429.
    """
    if not task.get('subtitle_opt'):
        return False
    msg = (error_message or "").lower()
    return ("subtitles" in msg) or ("429" in msg)


def is_cancel_error(error_message: Optional[str]) -> bool:
    """Lỗi có phải do người dùng hủy không."""
    return "CANCELLED_BY_USER" in (error_message or "")


def summarize_queue_result(total: int, failed: int, cancelled: bool) -> str:
    """Tạo thông điệp tổng kết sau khi xử lý xong hàng đợi."""
    if cancelled:
        return "Đã hủy tải."
    if failed == 0:
        return "Tuyệt vời! Toàn bộ Hàng Đợi đã được tải xong."
    if failed == total:
        return "Tất cả các mục đều tải lỗi. Xem mục 'Tải lỗi' để thử lại."
    return f"Hoàn tất với {failed}/{total} mục lỗi. Xem mục 'Tải lỗi' để thử lại."
