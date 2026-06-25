import io
import os
import threading
import tkinter.filedialog as filedialog

import customtkinter as ctk
import requests
import yt_dlp
from PIL import Image

import config_store
import core
import downloader
import queue_logic
from core import get_ffmpeg_path

# Thiết lập giao diện hiện đại
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class UniversalVideoDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Nạp cấu hình đã lưu từ lần dùng trước (thư mục tải, định dạng, tùy chọn...)
        self.app_config = config_store.load_config()
        # Số luồng tải song song mong muốn (1 = tuần tự như cũ)
        self.concurrency_var = ctk.StringVar(value=str(self.app_config.get('concurrency', 1)))
        self._concurrent_active = 1  # Số task đang tải song song (cập nhật lúc chạy)

        self.title("Universal Video Downloader")
        self.geometry("1100x820")
        self.resizable(False, False)

        # === PHẦN BÊN TRÁI (KHU VỰC TẢI VIDEO) ===
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(side="left", fill="both", expand=True)

        # --- Tiêu đề ---
        self.title_label = ctk.CTkLabel(self.main_frame, text="Tải Video Từ Mọi Nền Tảng", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(padx=20, pady=(20, 15))

        # --- Khung nhập link ---
        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(self.main_frame, width=550, height=45, placeholder_text="Dán link video (YouTube, TikTok, Facebook,...) vào đây...", textvariable=self.url_var, font=ctk.CTkFont(size=14), justify="center")
        self.url_entry.pack(padx=20, pady=5)

        # Theo dõi sự thay đổi của url để tự map Info & Thumbnail (debouncing event)
        self.url_var.trace_add("write", self.on_url_validate)
        self.fetch_timer = None

        # --- Khung hiển thị Thumbnail và Thông tin ---
        self.info_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.info_frame.pack(padx=20, pady=10, fill="x")

        self.thumbnail_label = ctk.CTkLabel(self.info_frame, text="Nhập link để hiển thị video", width=384, height=216, fg_color="gray20", corner_radius=10)
        self.thumbnail_label.pack(pady=5)

        self.video_title_label = ctk.CTkLabel(self.info_frame, text="", font=ctk.CTkFont(size=15, weight="bold"), text_color="white", wraplength=550)
        self.video_title_label.pack(pady=(5,0))

        self.video_duration_label = ctk.CTkLabel(self.info_frame, text="", font=ctk.CTkFont(size=13), text_color="gray")
        self.video_duration_label.pack()

        # --- Khung Chọn Thư mục ---
        self.folder_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.folder_frame.pack(padx=20, pady=10)

        self.save_dir = ctk.StringVar(value=self.app_config.get('save_dir', os.path.join(os.path.expanduser('~'), 'Downloads')))

        self.dir_entry = ctk.CTkEntry(self.folder_frame, textvariable=self.save_dir, width=250, height=35, state="disabled")
        self.dir_entry.pack(side="left", padx=(0, 10))

        self.btn_browse = ctk.CTkButton(self.folder_frame, text="Chọn Thư Mục", width=110, height=35, command=self.browse_folder, fg_color="gray30", hover_color="gray40")
        self.btn_browse.pack(side="left", padx=(0, 8))

        self.btn_open_dir = ctk.CTkButton(self.folder_frame, text="📂 Mở", width=60, height=35, command=self.open_save_dir, fg_color="#2980b9", hover_color="#3498db")
        self.btn_open_dir.pack(side="left", padx=(0, 15))

        # Danh sách thư mục tải gần đây (chọn nhanh)
        self.recent_dirs = self.app_config.get('recent_dirs', [])
        self.recent_var = ctk.StringVar(value="Gần đây ▾")
        self.recent_menu = ctk.CTkOptionMenu(
            self.folder_frame, values=(self.recent_dirs or ["(trống)"]),
            variable=self.recent_var, command=self._on_recent_selected,
            width=110, height=35, font=ctk.CTkFont(size=11)
        )
        self.recent_menu.pack(side="left", padx=(0, 15))

        self.smart_folder_var = ctk.BooleanVar(value=self.app_config.get('smart_folder', True))
        self.smart_folder_cb = ctk.CTkCheckBox(self.folder_frame, text="Phân loại nền tảng ngầm (VD: /Youtube)", variable=self.smart_folder_var, font=ctk.CTkFont(size=12, weight="bold"))
        self.smart_folder_cb.pack(side="left")

        # --- Lựa chọn tùy chọn tải ---
        self.options_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.options_frame.pack(padx=20, pady=10)

        self.format_var = ctk.StringVar(value=self.app_config.get('format_choice', "Video - Tốt nhất"))
        self.format_menu = ctk.CTkOptionMenu(
            self.options_frame,
            values=["Video - Tốt nhất", "Video - 1080p", "Video - 720p", "Video - 480p", "Âm thanh (MP3)"],
            variable=self.format_var,
            width=200, height=35,
            font=ctk.CTkFont(size=13),
            anchor="center"
        )
        self.format_menu.pack(side="left", padx=(0, 10))

        self.playlist_var = ctk.BooleanVar(value=False)
        self.playlist_checkbox = ctk.CTkCheckBox(
            self.options_frame,
            text="Tải toàn bộ Playlist",
            variable=self.playlist_var,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.playlist_checkbox.pack(side="left", padx=10)

        self.cookie_var = ctk.StringVar(value=self.app_config.get('cookie_choice', "Không Dùng Cookie"))
        self.cookie_menu = ctk.CTkOptionMenu(
            self.options_frame,
            values=["Không Dùng Cookie", "Tài khoản Chrome", "Tài khoản Edge", "Tài khoản Firefox", "Tài khoản Brave"],
            variable=self.cookie_var,
            width=165, height=35,
            font=ctk.CTkFont(size=12)
        )
        self.cookie_menu.pack(side="left", padx=10)

        self.container_var = ctk.StringVar(value=self.app_config.get('container', "MP4"))
        self.container_menu = ctk.CTkOptionMenu(
            self.options_frame,
            values=["MP4", "MKV", "WEBM"],
            variable=self.container_var,
            width=90, height=35,
            font=ctk.CTkFont(size=12)
        )
        self.container_menu.pack(side="left", padx=10)

        # Thiết lập sự kiện thay đổi
        self.playlist_var.trace_add("write", self.on_playlist_toggle)
        self.cookie_var.trace_add("write", self.on_cookie_change)

        # --- Các tuỳ chọn nâng cao khác ---
        self.adv_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.adv_frame.pack(padx=20, pady=(0, 10))

        self.subtitle_var = ctk.BooleanVar(value=self.app_config.get('subtitle_opt', False))
        self.subtitle_checkbox = ctk.CTkCheckBox(
            self.adv_frame, text="Tải kèm Phụ đề (Nếu có)", variable=self.subtitle_var, font=ctk.CTkFont(size=12)
        )
        self.subtitle_checkbox.pack(side="left", padx=10)

        self.thumbnail_var = ctk.BooleanVar(value=self.app_config.get('thumbnail_opt', True))
        self.thumbnail_checkbox = ctk.CTkCheckBox(
            self.adv_frame, text="Gắn Ảnh Bìa (vào MP3/MP4)", variable=self.thumbnail_var, font=ctk.CTkFont(size=12)
        )
        self.thumbnail_checkbox.pack(side="left", padx=10)

        self.concurrency_label = ctk.CTkLabel(self.adv_frame, text=" | Tải song song:", font=ctk.CTkFont(size=12))
        self.concurrency_label.pack(side="left", padx=(5, 2))
        self.concurrency_menu = ctk.CTkOptionMenu(
            self.adv_frame, values=["1", "2", "3", "4"], variable=self.concurrency_var,
            width=55, height=28, font=ctk.CTkFont(size=12)
        )
        self.concurrency_menu.pack(side="left", padx=2)

        self.time_label = ctk.CTkLabel(self.adv_frame, text=" |  Cắt từ:", font=ctk.CTkFont(size=12))
        self.time_label.pack(side="left", padx=(5, 2))
        self.start_var = ctk.StringVar()
        self.start_entry = ctk.CTkEntry(self.adv_frame, textvariable=self.start_var, width=55, height=28, placeholder_text="00:00")
        self.start_entry.pack(side="left", padx=2)

        self.time_label2 = ctk.CTkLabel(self.adv_frame, text="đến:", font=ctk.CTkFont(size=12))
        self.time_label2.pack(side="left", padx=2)
        self.end_var = ctk.StringVar()
        self.end_entry = ctk.CTkEntry(self.adv_frame, textvariable=self.end_var, width=55, height=28, placeholder_text="05:30")
        self.end_entry.pack(side="left", padx=(2, 10))

        self.rate_label = ctk.CTkLabel(self.adv_frame, text=" |  Giới hạn:", font=ctk.CTkFont(size=12))
        self.rate_label.pack(side="left", padx=(5, 2))
        self.rate_var = ctk.StringVar(value=self.app_config.get('rate_limit_str', ''))
        self.rate_entry = ctk.CTkEntry(self.adv_frame, textvariable=self.rate_var, width=70, height=28, placeholder_text="vd: 1.5M")
        self.rate_entry.pack(side="left", padx=(2, 10))

        # Theo dõi sự thay đổi menu chọn format để tính toán lại dung lượng
        self.format_var.trace_add("write", self.on_format_change)

        # --- Nút hành động ---
        self.action_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.action_frame.pack(padx=20, pady=10)

        self.download_btn = ctk.CTkButton(self.action_frame, text="Tải / Tải Thêm", command=self.add_to_queue, width=150, height=45, font=ctk.CTkFont(size=15, weight="bold"))
        self.download_btn.pack(side="left", padx=10)

        self.cancel_btn = ctk.CTkButton(self.action_frame, text="Hủy tải (Xóa DS)", command=self.cancel_download, width=200, height=45, font=ctk.CTkFont(size=14, weight="bold"), fg_color="#c0392b", hover_color="#e74c3c", state="disabled")
        self.cancel_btn.pack(side="left", padx=10)

        self.is_cancelled = False
        self.is_downloading = False
        self.download_queue = [] # Khởi tạo danh sách hàng đợi
        self.temp_files = [] # (giữ lại cho tương thích; state tải nay theo từng task)
        self.failed_tasks = [] # Các task tải lỗi để hiển thị nút "Thử lại"

        # --- Nhãn trạng thái ---
        self.status_label = ctk.CTkLabel(self.main_frame, text="", font=ctk.CTkFont(size=13), text_color="gray")
        self.status_label.pack(padx=20, pady=(5, 0))

        # --- Thanh tiến trình (Progress Bar) cho TỪNG video ---
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=550, height=12)
        self.progress_bar.set(0) # Mặc định là 0
        self.progress_bar.pack(padx=20, pady=(10, 4))

        # --- Thanh tiến trình TỔNG cho playlist (số video đã xong / tổng) ---
        self.playlist_progress_label = ctk.CTkLabel(self.main_frame, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self.playlist_progress_bar = ctk.CTkProgressBar(self.main_frame, width=550, height=8, progress_color="#f39c12")
        self.playlist_progress_bar.set(0)
        # Mặc định ẩn, chỉ hiện khi tải playlist

        # --- Footer ---
        self.footer_label = ctk.CTkLabel(self.main_frame, text="Phát triển bởi: Trần Đức Trí  ", font=ctk.CTkFont(size=12, slant="italic"), text_color="gray")
        self.footer_label.pack(side="bottom", pady=15)

        # === PHẦN BÊN PHẢI (KHU VỰC LỊCH SỬ TẢI) ===
        self.history_frame = ctk.CTkFrame(self, width=380)
        self.history_frame.pack(side="right", fill="y", padx=(0, 20), pady=20)
        self.history_frame.pack_propagate(False) # Cố định chiều rộng không bị phình to

        # Switch thay đổi Theme (Có khung giữ vị trí cố định chống giật lệch)
        self.theme_frame = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        self.theme_frame.pack(pady=(15, 0), padx=20, anchor="ne")

        self.theme_label = ctk.CTkLabel(self.theme_frame, text="Chế độ Tối 🌙", font=ctk.CTkFont(size=12, weight="bold"), width=105, anchor="e")
        self.theme_label.pack(side="left", padx=5)

        self.appearance_mode_switch = ctk.CTkSwitch(
            self.theme_frame, text="", command=self.change_appearance_mode_event, width=40
        )
        self.appearance_mode_switch.pack(side="right")
        # Khôi phục chế độ giao diện đã lưu (mặc định: Tối)
        if self.app_config.get('appearance_mode', 'Dark') == 'Dark':
            self.appearance_mode_switch.select()
            ctk.set_appearance_mode("Dark")
            self.theme_label.configure(text="Chế độ Tối 🌙")
        else:
            self.appearance_mode_switch.deselect()
            ctk.set_appearance_mode("Light")
            self.theme_label.configure(text="Chế độ Sáng ☀️")

        self.queue_title = ctk.CTkLabel(self.history_frame, text="⏳ HÀNG ĐỢI TẢI (ĐANG CHỜ)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f39c12")
        self.queue_title.pack(pady=(5, 5))

        self.queue_scroll = ctk.CTkScrollableFrame(self.history_frame, fg_color=("gray85", "gray25"), height=110)
        self.queue_scroll.pack(fill="x", padx=10, pady=(0, 10))

        # --- Khu vực MỤC TẢI LỖI (có nút Thử lại) ---
        self.failed_title = ctk.CTkLabel(self.history_frame, text="⚠️ TẢI LỖI (BẤM ĐỂ THỬ LẠI)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#e74c3c")
        self.failed_scroll = ctk.CTkScrollableFrame(self.history_frame, fg_color=("gray85", "gray25"), height=90)
        # Mặc định ẩn, chỉ hiện khi có mục lỗi

        self.history_header_frame = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        self.history_header_frame.pack(fill="x", padx=10, pady=(5, 5))

        self.history_title = ctk.CTkLabel(self.history_header_frame, text="📁 LỊCH SỬ TẢI (HOÀN TẤT)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#2ecc71")
        self.history_title.pack(side="left")

        self.clear_history_btn = ctk.CTkButton(self.history_header_frame, text="🗑️ Xóa", width=40, height=22, fg_color="#c0392b", hover_color="#e74c3c", font=ctk.CTkFont(size=11), command=self.clear_history_data)
        self.clear_history_btn.pack(side="right")

        self.export_csv_btn = ctk.CTkButton(self.history_header_frame, text="⬇ CSV", width=48, height=22, fg_color="#16a085", hover_color="#1abc9c", font=ctk.CTkFont(size=11), command=self.export_history_csv)
        self.export_csv_btn.pack(side="right", padx=(0, 6))

        self.history_scroll = ctk.CTkScrollableFrame(self.history_frame, fg_color="transparent")
        self.history_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.load_history_from_file()

        # Lưu cấu hình khi đóng cửa sổ
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Tự dán link từ clipboard nếu phát hiện đường link hợp lệ
        self._last_clipboard = ""
        self.after(400, self._check_clipboard_for_link)
        self.bind("<FocusIn>", lambda e: self._check_clipboard_for_link())

        # Bật kéo-thả link/file vào cửa sổ (nếu có tkinterdnd2)
        self._setup_drag_drop()

    def _setup_drag_drop(self):
        """Bật kéo-thả văn bản/đường dẫn vào ô link. Bỏ qua nếu thiếu tkinterdnd2."""
        try:
            from tkinterdnd2 import DND_FILES, DND_TEXT, TkinterDnD
            TkinterDnD._require(self)  # Khởi tạo tkdnd cho cửa sổ CTk hiện có

            def on_drop(event):
                data = (event.data or "").strip().strip('{}')
                if data:
                    self.url_var.set(data)
                    self._set_status("Đã nhận link/đường dẫn được kéo vào.", "gray")

            self.url_entry.drop_target_register(DND_TEXT, DND_FILES)
            self.url_entry.dnd_bind('<<Drop>>', on_drop)
        except Exception:
            pass  # Không có tkinterdnd2 -> bỏ qua, app vẫn chạy bình thường

    def _load_config(self):
        return config_store.load_config()

    def _save_config(self):
        data = {
            'save_dir': self.save_dir.get(),
            'format_choice': self.format_var.get(),
            'smart_folder': self.smart_folder_var.get(),
            'thumbnail_opt': self.thumbnail_var.get(),
            'subtitle_opt': self.subtitle_var.get(),
            'cookie_choice': self.cookie_var.get(),
            'container': self.container_var.get(),
            'rate_limit_str': self.rate_var.get(),
            'recent_dirs': self.recent_dirs,
            'concurrency': self._get_concurrency(),
            'appearance_mode': 'Dark' if self.appearance_mode_switch.get() == 1 else 'Light',
        }
        config_store.save_config(data)

    def _on_close(self):
        self._save_config()
        self.destroy()

    def _ui(self, func):
        """Lên lịch chạy 1 hàm cập nhật giao diện trên main thread (Tkinter không an toàn đa luồng)."""
        try:
            self.after(0, func)
        except Exception:
            pass

    def _set_status(self, text, color=None):
        """Cập nhật nhãn trạng thái an toàn từ thread phụ."""
        if color is not None:
            self._ui(lambda: self.status_label.configure(text=text, text_color=color))
        else:
            self._ui(lambda: self.status_label.configure(text=text))

    def _set_progress(self, value):
        """Cập nhật thanh tiến trình an toàn từ thread phụ."""
        self._ui(lambda: self.progress_bar.set(value))

    def _notify(self, title, message):
        """Hiện thông báo hệ thống (toast). Lặng lẽ bỏ qua nếu không hỗ trợ."""
        try:
            from plyer import notification
            notification.notify(title=title, message=message,
                                 app_name="Universal Video Downloader", timeout=8)
        except Exception:
            pass

    def _show_playlist_progress(self, show):
        """Hiện/ẩn thanh tiến trình tổng của playlist."""
        def _do():
            if show:
                self.playlist_progress_label.pack(padx=20, pady=(2, 0))
                self.playlist_progress_bar.pack(padx=20, pady=(0, 8))
            else:
                self.playlist_progress_label.pack_forget()
                self.playlist_progress_bar.pack_forget()
        self._ui(_do)

    def _set_playlist_progress(self, idx, count):
        """Cập nhật thanh tổng playlist: video idx/count."""
        def _do():
            try:
                self.playlist_progress_bar.set(idx / count if count else 0)
                self.playlist_progress_label.configure(text=f"Tiến độ Playlist: {idx}/{count} video")
            except Exception:
                pass
        self._ui(_do)

    def change_appearance_mode_event(self):
        if self.appearance_mode_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
            self.theme_label.configure(text="Chế độ Tối 🌙")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_label.configure(text="Chế độ Sáng ☀️")

    def refresh_queue_ui(self):
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()

        for i, task in enumerate(self.download_queue):
            item_frame = ctk.CTkFrame(self.queue_scroll, corner_radius=5)
            item_frame.pack(fill="x", pady=2)

            short_url = task['url'][:30] + "..." if len(task['url']) > 30 else task['url']
            format_tag = "MP3" if task['format_choice'] == "Âm thanh (MP3)" else "MP4"

            lbl = ctk.CTkLabel(item_frame, text=f"#{i+1}. [{format_tag}] {short_url}", font=ctk.CTkFont(size=11))
            lbl.pack(side="left", padx=10, pady=5)

            def make_remove_func(idx):
                def remove_task():
                    if 0 <= idx < len(self.download_queue):
                        del self.download_queue[idx]
                        self.refresh_queue_ui()
                        self.status_label.configure(text=f"Đã hủy 1 mục khỏi hàng đợi! (Còn {len(self.download_queue)})", text_color="orange")
                return remove_task

            btn_remove = ctk.CTkButton(
                item_frame, text="✕", width=22, height=22,
                fg_color="transparent", hover_color="#c0392b", text_color="#e74c3c", font=ctk.CTkFont(size=12, weight="bold"),
                command=make_remove_func(i)
            )
            btn_remove.pack(side="right", padx=5)

    def _add_failed_task(self, task, reason=""):
        """Ghi nhận 1 task tải lỗi để người dùng có thể bấm Thử lại."""
        self.failed_tasks.append({'task': task, 'reason': reason})
        self._ui(self._refresh_failed_ui)

    def _refresh_failed_ui(self):
        for widget in self.failed_scroll.winfo_children():
            widget.destroy()

        if not self.failed_tasks:
            # Ẩn cả khu vực khi không có lỗi
            self.failed_title.pack_forget()
            self.failed_scroll.pack_forget()
            return

        # Hiện khu vực (đặt ngay trên phần lịch sử)
        self.failed_title.pack(pady=(5, 5), before=self.history_header_frame)
        self.failed_scroll.pack(fill="x", padx=10, pady=(0, 10), before=self.history_header_frame)

        for i, item in enumerate(self.failed_tasks):
            task = item['task']
            item_frame = ctk.CTkFrame(self.failed_scroll, corner_radius=5)
            item_frame.pack(fill="x", pady=2)

            short_url = task['url'][:26] + "..." if len(task['url']) > 26 else task['url']
            lbl = ctk.CTkLabel(item_frame, text=f"⚠️ {short_url}", font=ctk.CTkFont(size=11), text_color="#e74c3c")
            lbl.pack(side="left", padx=8, pady=5)

            def make_retry_func(idx):
                def retry():
                    self._retry_task(idx)
                return retry

            def make_remove_func(idx):
                def remove():
                    if 0 <= idx < len(self.failed_tasks):
                        del self.failed_tasks[idx]
                        self._refresh_failed_ui()
                return remove

            btn_remove = ctk.CTkButton(
                item_frame, text="✕", width=22, height=22,
                fg_color="transparent", hover_color="#c0392b", text_color="#e74c3c",
                font=ctk.CTkFont(size=12, weight="bold"), command=make_remove_func(i)
            )
            btn_remove.pack(side="right", padx=(2, 5))

            btn_retry = ctk.CTkButton(
                item_frame, text="🔄 Thử lại", width=70, height=22,
                fg_color="#e67e22", hover_color="#f39c12", font=ctk.CTkFont(size=11),
                command=make_retry_func(i)
            )
            btn_retry.pack(side="right", padx=2)

    def _retry_task(self, idx):
        """Đưa 1 task lỗi trở lại hàng đợi tải."""
        if not (0 <= idx < len(self.failed_tasks)):
            return
        item = self.failed_tasks.pop(idx)
        self._refresh_failed_ui()
        self._enqueue_task(item['task'])

    def load_history_from_file(self):
        for item in config_store.load_history():
            self._render_history_item(item.get('title', ''), item.get('path', ''), item.get('filepath'))

    def save_history_to_file(self, title, path, filepath=None):
        config_store.add_history(title, path, filepath=filepath)

    def clear_history_data(self):
        config_store.clear_history()
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

    def _get_format_string(self, format_choice):
        return core.get_format_string(format_choice)

    def _default_format_values(self):
        return list(core.DEFAULT_FORMAT_VALUES)

    def _apply_format_values(self, values):
        """Cập nhật danh sách lựa chọn của menu chất lượng, giữ lựa chọn hiện tại nếu vẫn còn."""
        current = self.format_var.get()
        self.format_menu.configure(values=values)
        if current not in values:
            self.format_var.set(values[0])

    def _update_format_menu(self, info):
        """Dựng lại danh sách chất lượng dựa trên độ phân giải thật sự có của video."""
        try:
            values = core.format_values_from_info(info)
            self._ui(lambda: self._apply_format_values(values))
        except Exception:
            pass

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.save_dir.get())
        if folder:
            self.save_dir.set(folder)
            self._remember_dir(folder)

    def _remember_dir(self, folder):
        """Cập nhật danh sách thư mục gần đây và làm mới dropdown."""
        self.recent_dirs = core.update_recent_folders(self.recent_dirs, folder)
        try:
            self.recent_menu.configure(values=(self.recent_dirs or ["(trống)"]))
        except Exception:
            pass

    def _on_recent_selected(self, choice):
        """Người dùng chọn 1 thư mục gần đây từ dropdown."""
        if choice and choice != "(trống)":
            self.save_dir.set(choice)
        self.recent_var.set("Gần đây ▾")

    def export_history_csv(self):
        """Xuất lịch sử tải ra file CSV do người dùng chọn."""
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
            initialfile="lich_su_tai.csv",
        )
        if not path:
            return
        if config_store.export_history_csv(path):
            self.status_label.configure(text="Đã xuất lịch sử ra CSV!", text_color="green")
        else:
            self.status_label.configure(text="Lỗi khi xuất CSV!", text_color="red")

    def open_save_dir(self):
        folder = self.save_dir.get()
        try:
            if not os.path.isdir(folder):
                os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
        except Exception:
            self.status_label.configure(text="Không thể mở thư mục tải!", text_color="red")

    def _check_clipboard_for_link(self):
        """Tự động dán link từ clipboard nếu là URL hợp lệ và ô nhập đang trống."""
        try:
            clip = self.clipboard_get().strip()
        except Exception:
            return  # Clipboard trống hoặc không phải text

        # Bỏ qua nếu không phải link, hoặc đã xử lý rồi, hoặc ô nhập đang có nội dung
        if not clip.startswith("http") or clip == self._last_clipboard:
            return
        if self.url_var.get().strip():
            return

        self._last_clipboard = clip
        self.url_var.set(clip)
        self._set_status("Đã tự dán link từ clipboard.", "gray")

    def on_format_change(self, *args):
        url = self.url_var.get().strip()
        if url and url.startswith("http"):
            text = self.video_duration_label.cget("text")
            base_text = text.split(" | ")[0] if " | " in text else text
            # Hiện thông báo đang tính bên cạnh thời lượng
            self.video_duration_label.configure(text=base_text + " | Đang tính dung lượng...")
            threading.Thread(target=self._thread_fetch_size_only, args=(url, self.format_var.get()), daemon=True).start()

    def on_playlist_toggle(self, *args):
        url = self.url_var.get().strip()
        if url and url.startswith("http"):
            self.fetch_video_info()

    def on_cookie_change(self, *args):
        url = self.url_var.get().strip()
        if url and url.startswith("http"):
            self.fetch_video_info()

    def _get_cookie_opts(self):
        return core.cookie_opts_from_choice(self.cookie_var.get())

    def _thread_fetch_size_only(self, url, format_choice):
        if self.playlist_var.get():
            return
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'format': self._get_format_string(format_choice)
            }
            cookie_opt = self._get_cookie_opts()
            if cookie_opt:
                ydl_opts['cookiesfrombrowser'] = cookie_opt
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            file_size_bytes = core.total_filesize_bytes(info)

            text = self.video_duration_label.cget("text").split(" | ")[0]
            new_text = f"{text} | {core.human_size_label(file_size_bytes)}"
            self._ui(lambda: self.video_duration_label.configure(text=new_text))
        except Exception:
            pass # Lặng lẽ bỏ qua nếu lỗi cập nhật ngầm

    def on_url_validate(self, *args):
        # Debounce: Xóa timer cũ nếu người dùng đang gõ liên tiếp
        if self.fetch_timer is not None:
            self.after_cancel(self.fetch_timer)
        # Hẹn 1.2 giây sau khi người dùng ngừng gõ mới lấy dữ liệu
        self.fetch_timer = self.after(1200, self.fetch_video_info)

    def fetch_video_info(self):
        url = self.url_var.get().strip()
        if not url or not url.startswith("http"):
            self.thumbnail_label.configure(image=None, text="Nhập link để hiển thị video")
            self.video_title_label.configure(text="")
            self.video_duration_label.configure(text="")
            return

        self.video_title_label.configure(text="Đang lấy thông tin video & tính dung lượng...")
        threading.Thread(target=self._thread_fetch_info, args=(url, self.format_var.get()), daemon=True).start()

    def _thread_fetch_info(self, url, format_choice):
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'noplaylist': not self.playlist_var.get(),
                'extract_flat': 'in_playlist' if self.playlist_var.get() else False,
                'format': self._get_format_string(format_choice)
            }
            cookie_opt = self._get_cookie_opts()
            if cookie_opt:
                ydl_opts['cookiesfrombrowser'] = cookie_opt
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if 'entries' in info:
                # Nếu là Playlist
                title = "Playlist: " + info.get('title', 'Tên Playlist không xác định')
                entries = list(info['entries'])
                video_count = len(entries)
                duration_str = f"Danh sách này có: {video_count} video"

                self.current_playlist_url = url
                self.current_playlist_entries = entries

                thumbnail_url = None
                if entries and len(entries) > 0 and isinstance(entries[0], dict):
                    thumbnail_url = entries[0].get('thumbnails', [{'url': None}])[-1].get('url') or entries[0].get('thumbnail')
                if not thumbnail_url:
                    thumbnail_url = info.get('thumbnails', [{'url': None}])[-1].get('url')

                self._ui(lambda: self.video_title_label.configure(text=title))
                self._ui(lambda: self.video_duration_label.configure(text=duration_str))
                # Playlist: menu chất lượng trả về mặc định (mỗi video có thể khác nhau)
                self._ui(lambda: self._apply_format_values(self._default_format_values()))
            else:
                # Nếu là 1 Video đơn
                title = info.get('title', 'Tên video không xác định')
                duration_str = core.format_duration(info.get('duration', 0))

                file_size_bytes = core.total_filesize_bytes(info)
                duration_str += f" | {core.human_size_label(file_size_bytes)}"

                thumbnail_url = info.get('thumbnail')
                self._ui(lambda: self.video_title_label.configure(text=title))
                self._ui(lambda: self.video_duration_label.configure(text=duration_str))

                # Cập nhật menu chất lượng theo độ phân giải THẬT của video
                self._update_format_menu(info)

            # Lấy hình ảnh trên mạng về và Render
            if thumbnail_url:
                try:
                    response = requests.get(thumbnail_url, timeout=15)
                    img_data = response.content
                    image = Image.open(io.BytesIO(img_data))
                    ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(384, 216))
                    self._ui(lambda: self.thumbnail_label.configure(image=ctk_image, text=""))
                except Exception:
                    self._ui(lambda: self.thumbnail_label.configure(image=None, text="Lỗi khi tải ảnh thu nhỏ"))
        except Exception:
            self._ui(lambda: self.video_title_label.configure(text="Không thể lấy thông tin video (Hoặc link bị lỗi)"))
            self._ui(lambda: self.video_duration_label.configure(text=""))
            self._ui(lambda: self.thumbnail_label.configure(image=None, text="Lỗi"))

    def cancel_download(self):
        self.is_cancelled = True
        self.download_queue.clear() # Xóa hết các video đang đợi xếp hàng luôn
        self.refresh_queue_ui() # Xóa trích xuất hiển thị hàng đợi
        self.status_label.configure(text="Đang dừng và hủy toàn bộ...", text_color="orange")
        self.cancel_btn.configure(state="disabled")

    def _make_progress_hook(self, state):
        """Tạo progress hook riêng cho 1 task (an toàn khi tải song song).

        state: dict giữ 'temp_files' và 'current_filename' riêng của task này.
        """
        def hook(d):
            if d.get('info_dict'):
                state['current_filename'] = d['info_dict'].get('_filename')

            if self.is_cancelled:
                raise Exception("CANCELLED_BY_USER")

            if d['status'] == 'downloading':
                tmp = d.get('tmpfilename')
                if tmp and tmp not in state['temp_files']:
                    state['temp_files'].append(tmp)

                # Khi tải song song, không cập nhật thanh % đơn lẻ (gây nhảy loạn)
                if self._concurrent_active > 1:
                    return

                p_str = d.get('_percent_str', '0%').replace('\x1b[0;94m', '').replace('\x1b[0m', '').strip()

                playlist_idx = d.get('info_dict', {}).get('playlist_index')
                playlist_count = d.get('info_dict', {}).get('playlist_count')
                prefix = f"[Video {playlist_idx}/{playlist_count}] " if playlist_idx and playlist_count else ""

                if playlist_idx and playlist_count:
                    self._set_playlist_progress(playlist_idx, playlist_count)

                try:
                    clean_str = p_str.replace('%', '')
                    percent_float = float(clean_str) / 100.0
                    self._set_progress(percent_float)

                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    self._set_status(f"{prefix}Đang tải... {p_str}  |  Tốc độ: {speed}  |  Còn lại: {eta}")
                except Exception:
                    pass

            elif d['status'] == 'finished':
                if self._concurrent_active > 1:
                    return
                playlist_idx = d.get('info_dict', {}).get('playlist_index')
                playlist_count = d.get('info_dict', {}).get('playlist_count')
                if playlist_idx and playlist_count:
                    self._set_playlist_progress(playlist_idx, playlist_count)
                if playlist_idx and playlist_count and playlist_idx < playlist_count:
                    self._set_status(f"[Video {playlist_idx}/{playlist_count}] Tải xong! Đang chuyển sang video tiếp theo...")
                else:
                    self._set_status("Tải xong! Đang xử lý file cuối cùng (nếu có)...")
                self._set_progress(1.0)
        return hook

    def _resolve_final_filepath(self, info, download_folder):
        """Suy ra đường dẫn file cuối cùng sau khi tải (xét cả chuyển sang .mp3)."""
        is_audio = self.format_var.get() == "Âm thanh (MP3)"
        return core.resolve_final_filepath(info, is_audio)

    def _render_history_item(self, title, download_folder, filepath=None):
        item_frame = ctk.CTkFrame(self.history_scroll, corner_radius=5)
        item_frame.pack(fill="x", pady=2)

        lbl = ctk.CTkLabel(item_frame, text="✅ " + (title[:26] + "..." if len(title) > 26 else title), font=ctk.CTkFont(size=11))
        lbl.pack(side="left", padx=5, pady=5)

        def open_folder():
            try:
                os.startfile(download_folder)
            except Exception:
                pass

        def open_file():
            try:
                os.startfile(filepath)
            except Exception:
                # Nếu mở file lỗi (đã xóa/di chuyển), mở thư mục thay thế
                open_folder()

        btn = ctk.CTkButton(item_frame, text="📂", width=32, height=22, font=ctk.CTkFont(size=11), fg_color="#2980b9", hover_color="#3498db", command=open_folder)
        btn.pack(side="right", padx=(2, 5), pady=5)

        # Chỉ hiện nút mở file nếu có đường dẫn file thật và file còn tồn tại
        if filepath and os.path.exists(filepath):
            btn_play = ctk.CTkButton(item_frame, text="▶ Mở file", width=64, height=22, font=ctk.CTkFont(size=11), fg_color="#27ae60", hover_color="#2ecc71", command=open_file)
            btn_play.pack(side="right", padx=2, pady=5)

    def add_history_item(self, title, download_folder, filepath=None):
        self.save_history_to_file(title, download_folder, filepath)

        for widget in self.history_scroll.winfo_children():
            widget.destroy()
        self.load_history_from_file()


    def _parse_time(self, t_str):
        """Chuyển chuỗi thời gian (HH:MM:SS / MM:SS / SS) thành giây.
        Trả về (seconds | None, error_message | None)."""
        return core.parse_time(t_str)

    def add_to_queue(self):
        url = self.url_var.get().strip()
        if not url or not url.startswith("http"):
            self.status_label.configure(text="Lỗi: Vui lòng dán một đường link hợp lệ!", text_color="red")
            return

        start_sec, start_err = self._parse_time(self.start_var.get())
        if start_err:
            self.status_label.configure(text=f"Lỗi thời gian cắt (Từ): {start_err}", text_color="red")
            return
        end_sec, end_err = self._parse_time(self.end_var.get())
        if end_err:
            self.status_label.configure(text=f"Lỗi thời gian cắt (Đến): {end_err}", text_color="red")
            return
        if start_sec is not None and end_sec is not None and end_sec <= start_sec:
            self.status_label.configure(text="Lỗi: Thời gian 'Đến' phải lớn hơn 'Từ'", text_color="red")
            return

        rate_limit, rate_err = core.parse_rate_limit(self.rate_var.get())
        if rate_err:
            self.status_label.configure(text=f"Lỗi giới hạn tốc độ: {rate_err}", text_color="red")
            return

        # Ghi nhớ thư mục tải hiện tại vào danh sách gần đây
        self._remember_dir(self.save_dir.get())

        task = {
            'url': url,
            'download_folder': self.save_dir.get(),
            'format_choice': self.format_var.get(),
            'is_playlist': self.playlist_var.get(),
            'cookie_opt': self._get_cookie_opts(),
            'subtitle_opt': self.subtitle_var.get(),
            'thumbnail_opt': self.thumbnail_var.get(),
            'container': self.container_var.get().lower(),
            'rate_limit': rate_limit,
            'start_sec': start_sec,
            'end_sec': end_sec,
            'smart_folder': self.smart_folder_var.get()
        }

        if task['is_playlist'] and getattr(self, 'current_playlist_url', '') == url and getattr(self, 'current_playlist_entries', None):
            self._show_playlist_selector(task)
        else:
            self._enqueue_task(task)

    def _show_playlist_selector(self, task):
        popup = ctk.CTkToplevel(self)
        popup.title("Lọc Video trong Playlist")
        popup.geometry("600x500")
        popup.grab_set()

        lbl = ctk.CTkLabel(popup, text="Hãy tick chọn những video bạn muốn tải:", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(pady=10)

        scroll = ctk.CTkScrollableFrame(popup)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)

        checkboxes = []
        entries = self.current_playlist_entries
        for i, entry in enumerate(entries):
            var = ctk.BooleanVar(value=True)
            title = entry.get('title') or entry.get('url', f"Video {i+1}")
            cb = ctk.CTkCheckBox(scroll, text=f"{i+1}. {title}", variable=var, font=ctk.CTkFont(size=12))
            cb.pack(fill="x", pady=5)
            checkboxes.append((i+1, var))

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)

        def toggle_all():
            any_unchecked = any(not var.get() for _, var in checkboxes)
            for _, var in checkboxes:
                var.set(any_unchecked)

        ctk.CTkButton(btn_frame, text="Chọn / Bỏ chọn Tất cả", width=120, command=toggle_all).pack(side="left", padx=10)

        def confirm():
            selected = [str(idx) for idx, var in checkboxes if var.get()]
            if not selected:
                return
            task['playlist_items'] = ",".join(selected)
            popup.destroy()
            self._enqueue_task(task)

        ctk.CTkButton(btn_frame, text="Xác Nhận Tải", width=120, fg_color="#27ae60", hover_color="#2ecc71", command=confirm).pack(side="right", padx=10)

    def _enqueue_task(self, task):
        self.download_queue.append(task)
        self.url_var.set("")

        self.status_label.configure(text=f"Đã đưa vào hàng đợi. (+{len(self.download_queue)} mục)", text_color="orange")
        self.refresh_queue_ui()

        if not self.is_downloading:
            threading.Thread(target=self._process_queue_thread, daemon=True).start()

    def _get_concurrency(self):
        """Đọc số luồng song song mong muốn (1-4), mặc định 1 nếu lỗi."""
        return queue_logic.clamp_concurrency(self.concurrency_var.get())

    def _process_queue_thread(self):
        self.is_downloading = True
        self.is_cancelled = False
        self._ui(lambda: self.cancel_btn.configure(state="normal"))

        has_errors = False
        concurrency = self._get_concurrency()

        if concurrency <= 1:
            # Chế độ tuần tự (như cũ)
            self._concurrent_active = 1
            while len(self.download_queue) > 0:
                task = self.download_queue.pop(0)
                self._ui(self.refresh_queue_ui)
                if self.is_cancelled:
                    break
                pending = len(self.download_queue)
                self._set_status(f"Đang tiến hành tải... (Còn {pending} mục đang đợi xếp hàng)", "gray")
                self._set_progress(0)
                if not self._execute_download(task):
                    has_errors = True
                if self.is_cancelled:
                    break
        else:
            # Chế độ song song: tải nhiều task cùng lúc bằng thread pool
            from concurrent.futures import ThreadPoolExecutor
            self._set_progress(0)
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                while self.download_queue and not self.is_cancelled:
                    batch = []
                    while self.download_queue and len(batch) < concurrency:
                        batch.append(self.download_queue.pop(0))
                    self._ui(self.refresh_queue_ui)
                    self._concurrent_active = len(batch)
                    remaining = len(self.download_queue)
                    self._set_status(
                        f"Đang tải song song {len(batch)} video... (Còn {remaining} mục chờ)", "gray")
                    results = list(executor.map(self._execute_download, batch))
                    if not all(results):
                        has_errors = True
            self._concurrent_active = 1
        self.is_downloading = False
        self._ui(lambda: self.cancel_btn.configure(state="disabled"))
        self._show_playlist_progress(False)  # Ẩn thanh tổng playlist khi xong hàng đợi

        if self.is_cancelled:
            pass # Keep the cancel message
        elif has_errors:
            # Leave the error message on screen
            self._notify("Tải hoàn tất (có lỗi)", "Một số mục tải lỗi. Xem mục 'Tải lỗi' để thử lại.")
        else:
            self._set_status("Tuyệt vời! Toàn bộ Hàng Đợi đã được tải xong.", "green")
            self._set_progress(1.0)
            self._notify("Tải hoàn tất", "Toàn bộ hàng đợi đã được tải xong!")

        # Check if queue has items added while cancelling
        if len(self.download_queue) > 0 and not self.is_cancelled:
            threading.Thread(target=self._process_queue_thread, daemon=True).start()

    def _execute_download(self, task):
        url = task['url']
        download_folder = task['download_folder']
        is_playlist = task['is_playlist']

        # Hiện thanh tiến trình tổng nếu là playlist, ẩn nếu video đơn
        if is_playlist:
            self._set_playlist_progress(0, 1)
            self._show_playlist_progress(True)
        else:
            self._show_playlist_progress(False)

        if task.get('smart_folder', False):
            sub_fs = core.classify_folder(url)
            download_folder = os.path.join(download_folder, sub_fs)
            if not os.path.exists(download_folder):
                try:
                    os.makedirs(download_folder)
                except Exception:
                    pass

        out_template = downloader.build_out_template(download_folder, is_playlist)

        retry_without_subtitles = False
        # State riêng cho task này (an toàn khi tải song song)
        state = {'temp_files': [], 'current_filename': None}

        while True:
            ffmpeg_dir = get_ffmpeg_path()

            s_val = task['start_sec']
            e_val = task['end_sec']
            download_ranges = downloader.build_download_ranges(s_val, e_val)

            ydl_opts = downloader.build_ydl_opts(
                task, out_template,
                ffmpeg_dir=ffmpeg_dir,
                progress_hook=self._make_progress_hook(state),
                download_ranges=download_ranges,
            )

            state['temp_files'] = []

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if is_playlist:
                        downloaded_title = "Playlist/Kênh: " + info.get('title', 'Nhiều video')
                        history_folder = os.path.join(download_folder, info.get('title', ''))
                        final_filepath = None  # Playlist nhiều file, không mở 1 file cụ thể
                    else:
                        downloaded_title = info.get('title', 'Video Mới Tải')
                        history_folder = download_folder
                        # Lấy đường dẫn file cuối cùng để có thể mở trực tiếp
                        final_filepath = self._resolve_final_filepath(info, download_folder)

                if not self.is_cancelled:
                    if retry_without_subtitles:
                        downloaded_title = downloaded_title + " (Không Phụ Đề)"

                    self.after(0, self.add_history_item, downloaded_title, history_folder, final_filepath)
                    return True

            except Exception as e:
                err_str = str(e)
                if queue_logic.is_cancel_error(err_str):
                    cleaned = False
                    for f in state['temp_files']:
                        try:
                            if os.path.exists(f):
                                os.remove(f)
                                cleaned = True
                        except Exception:
                            pass

                    if not is_playlist:
                        try:
                            # 1. Clean expected final files from output template
                            for ext in ['.mp4', '.m4a', '.webm', '.mp3']:
                                expected_final = out_template.replace('.%(ext)s', ext)
                                dir_path = os.path.dirname(expected_final)
                                if os.path.exists(dir_path):
                                    for f in os.listdir(dir_path):
                                        if f.endswith('.ytdl') or f.endswith('.part'):
                                            os.remove(os.path.join(dir_path, f))
                                            cleaned = True

                            # 2. Clean thumbnails and media starting with exact base_name from yt-dlp info_dict
                            if state.get('current_filename'):
                                base_name = os.path.splitext(state['current_filename'])[0]
                                possible_exts = ['.webp', '.jpg', '.png', '.mp4', '.m4a', '.webm', '.mp3', '.part', '.ytdl']
                                for ext in possible_exts:
                                    target = base_name + ext
                                    if os.path.exists(target):
                                        os.remove(target)
                                        cleaned = True
                        except Exception:
                            pass

                    if cleaned:
                        self._set_status("Đã hủy & tự động dọn rác!", "orange")
                    else:
                        self._set_status("Đã hủy tải.", "orange")
                    return False

                elif queue_logic.should_retry_without_subtitles(task, err_str):
                    # Tự động Retry nhưng tắt phụ đề
                    task['subtitle_opt'] = False
                    retry_without_subtitles = True
                    self._set_status("Mạng hạn chế tải Phụ Đề (Lỗi 429). Đang tải lại video KHÔNG Phụ Đề...", "orange")
                    continue # Quay lại vòng lặp while True để tải lại

                else:
                    import re
                    clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', err_str)
                    self._set_status(f"Lỗi tải link {url[:15]}...: {clean_msg[:100]}", "red")
                    # Ghi nhận task lỗi để người dùng có thể bấm "Thử lại"
                    self._add_failed_task(task, clean_msg[:100])
                    return False
            return False

if __name__ == "__main__":
    app = UniversalVideoDownloaderApp()
    app.mainloop()
