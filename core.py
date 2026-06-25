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

# Nhãn lựa chọn "không dùng cookie" và tiền tố các lựa chọn cookie theo trình duyệt
NO_COOKIE_LABEL = "Không Dùng Cookie"
COOKIE_PREFIX = "Tài khoản "

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


def get_format_string(format_choice: Optional[str], container: str = "mp4") -> str:
    """Trả về mã format chuẩn của yt-dlp tương ứng với lựa chọn của người dùng.

    container: định dạng hộp chứa mong muốn ('mp4', 'mkv', 'webm'). Với 'mp4'
    sẽ ưu tiên ext mp4/m4a; với mkv/webm thì không ép ext để merge linh hoạt.
    """
    if format_choice == "Âm thanh (MP3)":
        return 'bestaudio/best'

    container = (container or "mp4").lower()
    m = re.search(r'(\d+)p', format_choice or "")

    if container == "mp4":
        if m:
            h = m.group(1)
            return (f'bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/'
                    f'best[height<={h}][ext=mp4]/best')
        # Video - Tốt nhất (hoặc không xác định)
        return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    # mkv / webm: không ép ext mp4 để hộp chứa nhận mọi codec
    if m:
        h = m.group(1)
        return f'bestvideo[height<={h}]+bestaudio/best[height<={h}]/best'
    return 'bestvideo+bestaudio/best'


def parse_rate_limit(text: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    """Chuyển chuỗi giới hạn tốc độ (vd '500K', '1.5M', '2M', '1024') thành byte/giây.

    Trả về tuple (rate | None, error | None).
    - Bỏ trống là hợp lệ (không giới hạn) -> (None, None)
    - Sai định dạng -> (None, "<thông báo lỗi>")
    """
    text = (text or "").strip()
    if not text:
        return None, None
    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*([kmg]?)b?(?:/s)?', text, re.IGNORECASE)
    if not m:
        return None, f"Tốc độ '{text}' sai định dạng (vd: 500K, 1.5M, 2M)"
    value = float(m.group(1))
    unit = m.group(2).upper()
    mult = {'': 1, 'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3}[unit]
    rate = int(value * mult)
    if rate <= 0:
        return None, "Tốc độ phải lớn hơn 0"
    return rate, None


def update_recent_folders(folders: Optional[list], new_folder: Optional[str],
                          max_n: int = 5) -> list:
    """Cập nhật danh sách thư mục tải gần đây: đưa new_folder lên đầu, bỏ trùng, giới hạn max_n."""
    new_folder = (new_folder or "").strip()
    result = [f for f in (folders or []) if f and f != new_folder]
    if new_folder:
        result.insert(0, new_folder)
    return result[:max_n]


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


def cookie_opts_from_choice(choice: Optional[str]) -> Optional[tuple]:
    """Chuyển lựa chọn cookie của người dùng thành tham số 'cookiesfrombrowser' của yt-dlp.

    "Không Dùng Cookie" hoặc rỗng -> None.
    "Tài khoản Chrome" -> ('chrome',)
    """
    choice = (choice or "").strip()
    if not choice or choice == NO_COOKIE_LABEL:
        return None
    browser = choice.replace(COOKIE_PREFIX, "").strip().lower()
    if not browser:
        return None
    return (browser,)


def total_filesize_bytes(info: Optional[dict]) -> int:
    """Tính tổng dung lượng (byte) ước tính của 1 video từ info dict của yt-dlp.

    Gộp các 'requested_formats' (video + audio tách rời) nếu có, ngược lại dùng
    'filesize'/'filesize_approx' của chính info. Trả về 0 nếu không xác định được.
    """
    info = info or {}
    requested = info.get('requested_formats')
    if requested:
        total = 0
        for f in requested:
            total += f.get('filesize') or f.get('filesize_approx') or 0
        return total
    return info.get('filesize') or info.get('filesize_approx') or 0


def human_size_label(file_size_bytes: int) -> str:
    """Tạo nhãn dung lượng hiển thị từ số byte.

    > 0  -> "Dung lượng cỡ: ~12.3 MB"
    <= 0 -> "Dung lượng: [Chưa rõ]"
    """
    if file_size_bytes and file_size_bytes > 0:
        mb_size = file_size_bytes / (1024 * 1024)
        return f"Dung lượng cỡ: ~{mb_size:.1f} MB"
    return "Dung lượng: [Chưa rõ]"


def format_duration(seconds: Optional[float]) -> str:
    """Định dạng thời lượng (giây) thành chuỗi 'Thời lượng: X phút Y giây'."""
    total = int(seconds or 0)
    mins, secs = divmod(total, 60)
    return f"Thời lượng: {mins} phút {secs} giây"


def resolve_final_filepath(info: Optional[dict], is_audio: bool,
                           exists=os.path.exists) -> Optional[str]:
    """Suy ra đường dẫn file cuối cùng sau khi tải từ info dict của yt-dlp.

    is_audio: True nếu tải dạng MP3 (yt-dlp đổi đuôi sau hậu xử lý).
    exists:   hàm kiểm tra tồn tại file (tiêm vào để dễ kiểm thử).
    Trả về đường dẫn file (str) hoặc None nếu không suy ra được.
    """
    try:
        info = info or {}
        candidate = None
        requested = info.get('requested_downloads')
        if requested and isinstance(requested, list):
            candidate = requested[0].get('filepath') or requested[0].get('_filename')
        if not candidate:
            candidate = info.get('_filename') or info.get('filename')

        if not candidate:
            return None

        # Nếu là MP3: yt-dlp đổi đuôi sau hậu xử lý
        if is_audio:
            mp3 = os.path.splitext(candidate)[0] + ".mp3"
            if exists(mp3):
                return mp3
        # Nếu file gốc (đã merge) còn đó
        if exists(candidate):
            return candidate
        # Dò các đuôi khả dĩ khác
        base = os.path.splitext(candidate)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.m4a', '.mp3']:
            if exists(base + ext):
                return base + ext
        return candidate
    except Exception:
        return None


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
