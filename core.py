"""Các hàm logic thuần (không phụ thuộc GUI) của Universal Video Downloader.

Tách riêng ra đây để có thể kiểm thử (pytest) mà không cần khởi tạo cửa sổ Tkinter.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional

# Danh sách lựa chọn chất lượng mặc định khi chưa biết format thật của video
DEFAULT_FORMAT_VALUES = [
    "Video - Tốt nhất",
    "Video - 1080p",
    "Video - 720p",
    "Video - 480p",
    "Âm thanh (MP3)",
]

# Bản đồ tên miền -> tên thư mục phân loại
DOMAIN_MAP = {
    'youtube.com': 'YouTube', 'youtu.be': 'YouTube',
    'tiktok.com': 'TikTok',
    'facebook.com': 'Facebook', 'fb.watch': 'Facebook',
    'instagram.com': 'Instagram',
    'twitter.com': 'Twitter_X', 'x.com': 'Twitter_X',
    'soundcloud.com': 'SoundCloud',
}


def parse_time(t_str: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """Chuyển chuỗi thời gian (HH:MM:SS / MM:SS / SS) thành giây.

    Trả về tuple (seconds | None, error_message | None).
    - Bỏ trống là hợp lệ (không cắt) -> (None, None)
    - Sai định dạng -> (None, "<thông báo lỗi>")
    """
    t_str = (t_str or "").strip()
    if not t_str:
        return None, None  # Bỏ trống là hợp lệ (không cắt)

    parts = t_str.split(':')
    if len(parts) > 3:
        return None, f"Thời gian '{t_str}' sai định dạng (dùng HH:MM:SS, MM:SS hoặc SS)"

    sec = 0.0
    for i, part in enumerate(reversed(parts)):
        part = part.strip()
        if part == "":
            return None, f"Thời gian '{t_str}' sai định dạng (có ô trống)"
        try:
            value = float(part)
        except ValueError:
            return None, f"Thời gian '{t_str}' chứa ký tự không hợp lệ"
        if value < 0:
            return None, f"Thời gian '{t_str}' không được âm"
        sec += value * (60 ** i)
    return sec, None


def get_format_string(format_choice: Optional[str]) -> str:
    """Trả về mã format chuẩn của yt-dlp tương ứng với lựa chọn của người dùng."""
    if format_choice == "Âm thanh (MP3)":
        return 'bestaudio/best'
    # Bắt mọi nhãn dạng "Video - <số>p" (1080p, 1440p, 2160p, ...) một cách tổng quát
    m = re.search(r'(\d+)p', format_choice or "")
    if m:
        h = m.group(1)
        return (f'bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/'
                f'best[height<={h}][ext=mp4]/best')
    # Video - Tốt nhất (hoặc không xác định)
    return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'


def heights_from_info(info: Optional[dict]) -> set[int]:
    """Lấy tập các độ phân giải (chiều cao) thật sự có của 1 video từ info dict của yt-dlp."""
    heights: set[int] = set()
    for f in (info or {}).get('formats', []):
        # Chỉ lấy format có hình ảnh (vcodec khác 'none')
        if f.get('vcodec') and f.get('vcodec') != 'none':
            h = f.get('height')
            if h:
                heights.add(int(h))
    return heights


def format_values_from_info(info: Optional[dict]) -> list[str]:
    """Dựng danh sách lựa chọn chất lượng dựa trên độ phân giải thật sự có của video.

    Nếu không đọc được độ phân giải nào -> trả về danh sách mặc định.
    """
    heights = heights_from_info(info)
    if not heights:
        return list(DEFAULT_FORMAT_VALUES)
    sorted_h = sorted(heights, reverse=True)
    return ["Video - Tốt nhất"] + [f"Video - {h}p" for h in sorted_h] + ["Âm thanh (MP3)"]


def classify_folder(url: Optional[str]) -> str:
    """Trả về tên thư mục phân loại theo tên miền của url (mặc định 'Others')."""
    low = (url or "").lower()
    for dom, name in DOMAIN_MAP.items():
        if dom in low:
            return name
    return 'Others'


def get_ffmpeg_path() -> Optional[str]:
    """Tìm đường dẫn thư mục chứa ffmpeg theo thứ tự ưu tiên.

    1. Khi đã đóng gói (PyInstaller): dùng ffmpeg nhúng kèm.
    2. Lấy từ package static_ffmpeg (khả chuyển, không phụ thuộc máy).
    3. None -> để yt-dlp tự dò ffmpeg trong PATH hệ thống.
    """
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'ffmpeg_bin')

    try:
        import static_ffmpeg
        pkg_dir = os.path.dirname(static_ffmpeg.__file__)
        for sub in ('bin/win32', 'bin/linux', 'bin/darwin', 'bin'):
            candidate = os.path.join(pkg_dir, *sub.split('/'))
            if os.path.isdir(candidate):
                exe = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
                if os.path.exists(os.path.join(candidate, exe)):
                    return candidate
    except Exception:
        pass

    return None
