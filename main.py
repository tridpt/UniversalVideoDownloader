import customtkinter as ctk
import yt_dlp
import threading
import os
import requests
from PIL import Image
import io
import tkinter.filedialog as filedialog
import subprocess
import sys

def get_ffmpeg_path():
    # Khi đã đóng gói (PyInstaller): dùng ffmpeg nhúng kèm
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'ffmpeg_bin')

    # 1. Thử lấy ffmpeg từ package static_ffmpeg (khả chuyển, không phụ thuộc máy)
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

    # 2. Nếu không có, để None -> yt-dlp tự tìm ffmpeg trong PATH của hệ thống
    return None

# Thiết lập giao diện hiện đại
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class YouTubeDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

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
        
        self.save_dir = ctk.StringVar(value=os.path.join(os.path.expanduser('~'), 'Downloads'))
        
        self.dir_entry = ctk.CTkEntry(self.folder_frame, textvariable=self.save_dir, width=300, height=35, state="disabled")
        self.dir_entry.pack(side="left", padx=(0, 10))
        
        self.btn_browse = ctk.CTkButton(self.folder_frame, text="Chọn Thư Mục", width=110, height=35, command=self.browse_folder, fg_color="gray30", hover_color="gray40")
        self.btn_browse.pack(side="left", padx=(0, 15))

        self.smart_folder_var = ctk.BooleanVar(value=True)
        self.smart_folder_cb = ctk.CTkCheckBox(self.folder_frame, text="Phân loại nền tảng ngầm (VD: /Youtube)", variable=self.smart_folder_var, font=ctk.CTkFont(size=12, weight="bold"))
        self.smart_folder_cb.pack(side="left")

        # --- Lựa chọn tùy chọn tải ---
        self.options_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.options_frame.pack(padx=20, pady=10)

        self.format_var = ctk.StringVar(value="Video - Tốt nhất")
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
        
        self.cookie_var = ctk.StringVar(value="Không Dùng Cookie")
        self.cookie_menu = ctk.CTkOptionMenu(
            self.options_frame,
            values=["Không Dùng Cookie", "Tài khoản Chrome", "Tài khoản Edge", "Tài khoản Firefox", "Tài khoản Brave"],
            variable=self.cookie_var,
            width=165, height=35,
            font=ctk.CTkFont(size=12)
        )
        self.cookie_menu.pack(side="left", padx=10)
        
        # Thiết lập sự kiện thay đổi
        self.playlist_var.trace_add("write", self.on_playlist_toggle)
        self.cookie_var.trace_add("write", self.on_cookie_change)
        
        # --- Các tuỳ chọn nâng cao khác ---
        self.adv_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.adv_frame.pack(padx=20, pady=(0, 10))

        self.subtitle_var = ctk.BooleanVar(value=False)
        self.subtitle_checkbox = ctk.CTkCheckBox(
            self.adv_frame, text="Tải kèm Phụ đề (Nếu có)", variable=self.subtitle_var, font=ctk.CTkFont(size=12)
        )
        self.subtitle_checkbox.pack(side="left", padx=10)

        self.thumbnail_var = ctk.BooleanVar(value=True)
        self.thumbnail_checkbox = ctk.CTkCheckBox(
            self.adv_frame, text="Gắn Ảnh Bìa (vào MP3/MP4)", variable=self.thumbnail_var, font=ctk.CTkFont(size=12)
        )
        self.thumbnail_checkbox.pack(side="left", padx=10)
        
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
        self.temp_files = [] # Lấy danh sách file rác tải dở
        
        # --- Nhãn trạng thái ---
        self.status_label = ctk.CTkLabel(self.main_frame, text="", font=ctk.CTkFont(size=13), text_color="gray")
        self.status_label.pack(padx=20, pady=(5, 0))
        
        # --- Thanh tiến trình (Progress Bar) ---
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=550, height=12)
        self.progress_bar.set(0) # Mặc định là 0
        self.progress_bar.pack(padx=20, pady=10)
        
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
        self.appearance_mode_switch.select()

        self.queue_title = ctk.CTkLabel(self.history_frame, text="⏳ HÀNG ĐỢI TẢI (ĐANG CHỜ)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f39c12")
        self.queue_title.pack(pady=(5, 5))

        self.queue_scroll = ctk.CTkScrollableFrame(self.history_frame, fg_color=("gray85", "gray25"), height=110)
        self.queue_scroll.pack(fill="x", padx=10, pady=(0, 10))

        self.history_header_frame = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        self.history_header_frame.pack(fill="x", padx=10, pady=(5, 5))
        
        self.history_title = ctk.CTkLabel(self.history_header_frame, text="📁 LỊCH SỬ TẢI (HOÀN TẤT)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#2ecc71")
        self.history_title.pack(side="left")
        
        self.clear_history_btn = ctk.CTkButton(self.history_header_frame, text="🗑️ Xóa", width=40, height=22, fg_color="#c0392b", hover_color="#e74c3c", font=ctk.CTkFont(size=11), command=self.clear_history_data)
        self.clear_history_btn.pack(side="right")

        self.history_scroll = ctk.CTkScrollableFrame(self.history_frame, fg_color="transparent")
        self.history_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.history_file = os.path.join(os.path.expanduser('~'), '.univideo_history.json')
        self.load_history_from_file()

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

    def load_history_from_file(self):
        import json
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        self._render_history_item(item.get('title', ''), item.get('path', ''))
            except Exception:
                pass

    def save_history_to_file(self, title, path):
        import json
        data = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
        
        data.insert(0, {'title': title, 'path': path}) 
        if len(data) > 100:
            data = data[:100]
            
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def clear_history_data(self):
        if os.path.exists(self.history_file):
            try:
                os.remove(self.history_file)
            except Exception:
                pass
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

    def _get_format_string(self, format_choice):
        # Trả về mã format chuẩn của yt-dlp tương ứng với lựa chọn
        if format_choice == "Âm thanh (MP3)":
            return 'bestaudio/best'
        elif format_choice == "Video - 1080p":
            return 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best'
        elif format_choice == "Video - 720p":
            return 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
        elif format_choice == "Video - 480p":
            return 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
        else: # Video - Tốt nhất
            return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.save_dir.get())
        if folder:
            self.save_dir.set(folder)

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
        choice = self.cookie_var.get()
        if choice != "Không Dùng Cookie":
            browser = choice.replace("Tài khoản ", "").lower()
            return (browser,) # Trả về tuple ('chrome', ...)
        return None

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
            
            file_size_bytes = 0
            if 'requested_formats' in info:
                for f in info['requested_formats']:
                    file_size_bytes += f.get('filesize') or f.get('filesize_approx') or 0
            else:
                file_size_bytes = info.get('filesize') or info.get('filesize_approx') or 0
                
            text = self.video_duration_label.cget("text").split(" | ")[0]
            if file_size_bytes > 0:
                mb_size = file_size_bytes / (1024 * 1024)
                new_text = f"{text} | Dung lượng cỡ: ~{mb_size:.1f} MB"
            else:
                new_text = f"{text} | Dung lượng: [Chưa rõ]"
            self._ui(lambda: self.video_duration_label.configure(text=new_text))
        except Exception as e:
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
            self.thumbnail_label.configure(image="", text="Nhập link để hiển thị video")
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
            else:
                # Nếu là 1 Video đơn
                title = info.get('title', 'Tên video không xác định')
                duration = info.get('duration', 0)
                mins, secs = divmod(duration, 60)
                duration_str = f"Thời lượng: {int(mins)} phút {int(secs)} giây"
                
                file_size_bytes = 0
                if 'requested_formats' in info:
                    for f in info['requested_formats']:
                        file_size_bytes += f.get('filesize') or f.get('filesize_approx') or 0
                else:
                    file_size_bytes = info.get('filesize') or info.get('filesize_approx') or 0
                    
                if file_size_bytes > 0:
                    mb_size = file_size_bytes / (1024 * 1024)
                    duration_str += f" | Dung lượng cỡ: ~{mb_size:.1f} MB"
                else:
                    duration_str += f" | Dung lượng: [Chưa rõ]"

                thumbnail_url = info.get('thumbnail')
                self._ui(lambda: self.video_title_label.configure(text=title))
                self._ui(lambda: self.video_duration_label.configure(text=duration_str))

            # Lấy hình ảnh trên mạng về và Render
            if thumbnail_url:
                try:
                    response = requests.get(thumbnail_url, timeout=15)
                    img_data = response.content
                    image = Image.open(io.BytesIO(img_data))
                    ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(384, 216))
                    self._ui(lambda: self.thumbnail_label.configure(image=ctk_image, text=""))
                except Exception as img_e:
                    self._ui(lambda: self.thumbnail_label.configure(image="", text="Lỗi khi tải ảnh thu nhỏ"))
        except Exception as e:
            self._ui(lambda: self.video_title_label.configure(text="Không thể lấy thông tin video (Hoặc link bị lỗi)"))
            self._ui(lambda: self.video_duration_label.configure(text=""))
            self._ui(lambda: self.thumbnail_label.configure(image="", text="Lỗi"))

    def cancel_download(self):
        self.is_cancelled = True
        self.download_queue.clear() # Xóa hết các video đang đợi xếp hàng luôn
        self.refresh_queue_ui() # Xóa trích xuất hiển thị hàng đợi
        self.status_label.configure(text="Đang dừng và hủy toàn bộ...", text_color="orange")
        self.cancel_btn.configure(state="disabled")

    def my_hook(self, d):
        if d.get('info_dict'):
            self.current_filename = d['info_dict'].get('_filename')
            
        if self.is_cancelled:
            raise Exception("CANCELLED_BY_USER")
            
        if d['status'] == 'downloading':
            tmp = d.get('tmpfilename')
            if tmp and tmp not in self.temp_files:
                self.temp_files.append(tmp)

            p_str = d.get('_percent_str', '0%').replace('\x1b[0;94m', '').replace('\x1b[0m', '').strip()
            
            playlist_idx = d.get('info_dict', {}).get('playlist_index')
            playlist_count = d.get('info_dict', {}).get('playlist_count')
            prefix = f"[Video {playlist_idx}/{playlist_count}] " if playlist_idx and playlist_count else ""

            try:
                clean_str = p_str.replace('%', '')
                percent_float = float(clean_str) / 100.0
                self._set_progress(percent_float)
                
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                self._set_status(f"{prefix}Đang tải... {p_str}  |  Tốc độ: {speed}  |  Còn lại: {eta}")
            except Exception as e:
                pass
                
        elif d['status'] == 'finished':
            playlist_idx = d.get('info_dict', {}).get('playlist_index')
            playlist_count = d.get('info_dict', {}).get('playlist_count')
            if playlist_idx and playlist_count and playlist_idx < playlist_count:
                self._set_status(f"[Video {playlist_idx}/{playlist_count}] Tải xong! Đang chuyển sang video tiếp theo...")
            else:
                self._set_status("Tải xong! Đang xử lý file cuối cùng (nếu có)...")
            self._set_progress(1.0)

    def _render_history_item(self, title, download_folder):
        import os
        item_frame = ctk.CTkFrame(self.history_scroll, corner_radius=5)
        item_frame.pack(fill="x", pady=2)
        
        lbl = ctk.CTkLabel(item_frame, text="✅ " + (title[:30] + "..." if len(title) > 30 else title), font=ctk.CTkFont(size=11))
        lbl.pack(side="left", padx=5, pady=5)
        
        def open_folder():
            try:
                os.startfile(download_folder)
            except Exception:
                pass
                
        btn = ctk.CTkButton(item_frame, text="📂 Mở", width=40, height=22, font=ctk.CTkFont(size=11), fg_color="#2980b9", hover_color="#3498db", command=open_folder)
        btn.pack(side="right", padx=5, pady=5)

    def add_history_item(self, title, download_folder):
        self.save_history_to_file(title, download_folder)
        
        for widget in self.history_scroll.winfo_children():
            widget.destroy()
        self.load_history_from_file()


    def add_to_queue(self):
        url = self.url_var.get().strip()
        if not url or not url.startswith("http"):
            self.status_label.configure(text="Lỗi: Vui lòng dán một đường link hợp lệ!")
            self.status_label.configure(text_color="red")
            return

        def time_to_sec(t_str):
            if not t_str: return None
            parts = reversed(t_str.strip().split(':'))
            sec = 0
            for i, part in enumerate(parts):
                try:
                    sec += float(part) * (60 ** i)
                except ValueError:
                    pass
            return sec

        task = {
            'url': url,
            'download_folder': self.save_dir.get(),
            'format_choice': self.format_var.get(),
            'is_playlist': self.playlist_var.get(),
            'cookie_opt': self._get_cookie_opts(),
            'subtitle_opt': self.subtitle_var.get(),
            'thumbnail_opt': self.thumbnail_var.get(),
            'start_sec': time_to_sec(self.start_var.get()),
            'end_sec': time_to_sec(self.end_var.get()),
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

    def _process_queue_thread(self):
        self.is_downloading = True
        self.is_cancelled = False
        self._ui(lambda: self.cancel_btn.configure(state="normal"))
        
        has_errors = False
        
        while len(self.download_queue) > 0:
            task = self.download_queue.pop(0)
            
            self._ui(self.refresh_queue_ui)
            
            if self.is_cancelled:
                break
                
            pending = len(self.download_queue)
            
            self._set_status(f"Đang tiến hành tải... (Còn {pending} mục đang đợi xếp hàng)", "gray")
            self._set_progress(0)
            
            success = self._execute_download(task)
            if not success:
                has_errors = True
            
            if self.is_cancelled:
                break
                
        self.is_downloading = False
        self._ui(lambda: self.cancel_btn.configure(state="disabled"))
        
        if self.is_cancelled:
            pass # Keep the cancel message
        elif has_errors:
            # Leave the error message on screen
            pass
        else:
            self._set_status("Tuyệt vời! Toàn bộ Hàng Đợi đã được tải xong.", "green")
            self._set_progress(1.0)
            
        # Check if queue has items added while cancelling
        if len(self.download_queue) > 0 and not self.is_cancelled:
            threading.Thread(target=self._process_queue_thread, daemon=True).start()
    
    def _execute_download(self, task):
        url = task['url']
        download_folder = task['download_folder']
        is_playlist = task['is_playlist']
        
        if task.get('smart_folder', False):
            domain_map = {
                'youtube.com': 'YouTube', 'youtu.be': 'YouTube',
                'tiktok.com': 'TikTok',
                'facebook.com': 'Facebook', 'fb.watch': 'Facebook',
                'instagram.com': 'Instagram',
                'twitter.com': 'Twitter_X', 'x.com': 'Twitter_X',
                'soundcloud.com': 'SoundCloud'
            }
            sub_fs = 'Others'
            for dom, name in domain_map.items():
                if dom in url.lower():
                    sub_fs = name
                    break
            download_folder = os.path.join(download_folder, sub_fs)
            if not os.path.exists(download_folder):
                try:
                    os.makedirs(download_folder)
                except Exception:
                    pass

        if is_playlist:
            out_template = os.path.join(download_folder, '%(playlist_title)s', '%(playlist_index)s - %(title)s.%(ext)s')
        else:
            out_template = os.path.join(download_folder, '%(title)s.%(ext)s')
            
        retry_without_subtitles = False
        
        while True:
            format_choice = task['format_choice']
            ffmpeg_dir = get_ffmpeg_path()
            
            ydl_opts = {
                'outtmpl': out_template,
                'progress_hooks': [self.my_hook],
                'noplaylist': not is_playlist, 
                'quiet': True,
                'no_warnings': True,
                'format': self._get_format_string(format_choice)
            }
            # Chỉ set khi tìm thấy ffmpeg; nếu None để yt-dlp tự dò trong PATH
            if ffmpeg_dir:
                ydl_opts['ffmpeg_location'] = ffmpeg_dir
            
            if 'playlist_items' in task:
                ydl_opts['playlist_items'] = task['playlist_items']
            
            if task['cookie_opt']:
                ydl_opts['cookiesfrombrowser'] = task['cookie_opt']
                
            if task['subtitle_opt']:
                ydl_opts['writesubtitles'] = True
                ydl_opts['writeautomaticsub'] = True
                ydl_opts['subtitleslangs'] = ['vi', 'en'] 
    
            if format_choice == "Âm thanh (MP3)":
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                ydl_opts['merge_output_format'] = 'mp4'
                
            if task['thumbnail_opt']:
                ydl_opts['writethumbnail'] = True
                if 'postprocessors' not in ydl_opts:
                    ydl_opts['postprocessors'] = []
                ydl_opts['postprocessors'].append({
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                })
    
            s_val = task['start_sec']
            e_val = task['end_sec']
            if s_val is not None or e_val is not None:
                def my_download_range_func(info_dict, ydl):
                    start = s_val if s_val is not None else 0
                    end = e_val if e_val is not None else float('inf')
                    return [(start, end)]
                ydl_opts['download_ranges'] = my_download_range_func
                ydl_opts['force_keyframes_at_cuts'] = True
    
            self.temp_files = [] 
    
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True) 
                    if is_playlist:
                        downloaded_title = "Playlist/Kênh: " + info.get('title', 'Nhiều video')
                        history_folder = os.path.join(download_folder, info.get('title', ''))
                    else:
                        downloaded_title = info.get('title', 'Video Mới Tải')
                        history_folder = download_folder
                    
                if not self.is_cancelled:
                    if retry_without_subtitles:
                        downloaded_title = downloaded_title + " (Không Phụ Đề)"
                        
                    self.after(0, self.add_history_item, downloaded_title, history_folder)
                    return True
    
            except Exception as e:
                err_str = str(e)
                if "CANCELLED_BY_USER" in err_str:
                    cleaned = False
                    for f in self.temp_files:
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
                            if hasattr(self, 'current_filename') and self.current_filename:
                                base_name = os.path.splitext(self.current_filename)[0]
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
                    
                elif task['subtitle_opt'] and ("subtitles" in err_str.lower() or "429" in err_str):
                    # Tự động Retry nhưng tắt phụ đề
                    task['subtitle_opt'] = False
                    retry_without_subtitles = True
                    self._set_status("Mạng hạn chế tải Phụ Đề (Lỗi 429). Đang tải lại video KHÔNG Phụ Đề...", "orange")
                    continue # Quay lại vòng lặp while True để tải lại
                    
                else:
                    import re
                    clean_msg = re.sub(r'\x1b\[[0-9;]*m', '', err_str)
                    self._set_status(f"Lỗi tải link {url[:15]}...: {clean_msg[:100]}", "red")
                    return False
            return False

if __name__ == "__main__":
    app = YouTubeDownloaderApp()
    app.mainloop()
