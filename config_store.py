"""Đọc/ghi cấu hình người dùng và lịch sử tải (thuần I/O, không phụ thuộc GUI).

Tách riêng để dễ kiểm thử và để main.py chỉ còn phần giao diện.
"""

import json
import os

# Đường dẫn mặc định trong thư mục home của người dùng
CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.univideo_config.json')
HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.univideo_history.json')

MAX_HISTORY = 100


def load_config(path=CONFIG_FILE):
    """Nạp cấu hình đã lưu; trả về dict rỗng nếu chưa có hoặc lỗi."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(data, path=CONFIG_FILE):
    """Lưu dict cấu hình ra file JSON. Trả về True nếu thành công."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False


def load_history(path=HISTORY_FILE):
    """Nạp danh sách lịch sử tải; trả về list (rỗng nếu chưa có hoặc lỗi)."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


def add_history(title, folder, path=HISTORY_FILE, max_items=MAX_HISTORY):
    """Thêm 1 mục vào đầu lịch sử, giới hạn max_items. Trả về list sau khi cập nhật."""
    data = load_history(path)
    data.insert(0, {'title': title, 'path': folder})
    if len(data) > max_items:
        data = data[:max_items]
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass
    return data


def clear_history(path=HISTORY_FILE):
    """Xóa file lịch sử nếu có. Trả về True nếu đã xóa (hoặc không có gì để xóa)."""
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception:
        return False
