"""Đọc/ghi cấu hình người dùng và lịch sử tải (thuần I/O, không phụ thuộc GUI).

Tách riêng để dễ kiểm thử và để main.py chỉ còn phần giao diện.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Optional

# Đường dẫn mặc định trong thư mục home của người dùng
CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.univideo_config.json')
HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.univideo_history.json')

MAX_HISTORY = 100


def load_config(path: str = CONFIG_FILE) -> dict:
    """Nạp cấu hình đã lưu; trả về dict rỗng nếu chưa có hoặc lỗi."""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(data: dict, path: str = CONFIG_FILE) -> bool:
    """Lưu dict cấu hình ra file JSON. Trả về True nếu thành công."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False


def load_history(path: str = HISTORY_FILE) -> list:
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


def add_history(title: str, folder: str, filepath: Optional[str] = None,
                path: str = HISTORY_FILE, max_items: int = MAX_HISTORY) -> list:
    """Thêm 1 mục vào đầu lịch sử, giới hạn max_items. Trả về list sau khi cập nhật.

    filepath (tùy chọn): đường dẫn file thật để có thể mở trực tiếp.
    """
    data = load_history(path)
    item = {'title': title, 'path': folder}
    if filepath:
        item['filepath'] = filepath
    data.insert(0, item)
    if len(data) > max_items:
        data = data[:max_items]
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass
    return data


def clear_history(path: str = HISTORY_FILE) -> bool:
    """Xóa file lịch sử nếu có. Trả về True nếu đã xóa (hoặc không có gì để xóa)."""
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception:
        return False


def export_history_csv(csv_path: str, history_path: str = HISTORY_FILE) -> bool:
    """Xuất lịch sử tải ra file CSV (cột: title, path, filepath).

    Dùng encoding utf-8-sig để Excel hiển thị đúng tiếng Việt.
    Trả về True nếu ghi thành công.
    """
    try:
        data = load_history(history_path)
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['title', 'path', 'filepath'])
            for item in data:
                writer.writerow([
                    item.get('title', ''),
                    item.get('path', ''),
                    item.get('filepath', ''),
                ])
        return True
    except Exception:
        return False
