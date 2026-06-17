"""Dựng tùy chọn tải cho yt-dlp (logic thuần, không phụ thuộc GUI).

Tách riêng để dễ kiểm thử: hàm build_ydl_opts chỉ nhận dữ liệu vào và
trả về dict tùy chọn, không gọi mạng hay đụng tới Tkinter.
"""

import os

from core import get_format_string


def build_out_template(download_folder, is_playlist):
    """Tạo mẫu đường dẫn xuất file cho yt-dlp."""
    if is_playlist:
        return os.path.join(
            download_folder, '%(playlist_title)s',
            '%(playlist_index)s - %(title)s.%(ext)s'
        )
    return os.path.join(download_folder, '%(title)s.%(ext)s')


def build_ydl_opts(task, out_template, ffmpeg_dir=None,
                   progress_hook=None, download_ranges=None):
    """Dựng dict tùy chọn cho yt-dlp dựa trên task của người dùng.

    task: dict gồm format_choice, is_playlist, cookie_opt, subtitle_opt,
          thumbnail_opt, và (tùy chọn) playlist_items.
    Trả về dict ydl_opts.
    """
    is_playlist = task.get('is_playlist', False)
    format_choice = task.get('format_choice', "Video - Tốt nhất")

    ydl_opts = {
        'outtmpl': out_template,
        'noplaylist': not is_playlist,
        'quiet': True,
        'no_warnings': True,
        'format': get_format_string(format_choice),
    }

    if progress_hook is not None:
        ydl_opts['progress_hooks'] = [progress_hook]

    # Chỉ set khi tìm thấy ffmpeg; nếu None để yt-dlp tự dò trong PATH
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir

    if task.get('playlist_items'):
        ydl_opts['playlist_items'] = task['playlist_items']

    if task.get('cookie_opt'):
        ydl_opts['cookiesfrombrowser'] = task['cookie_opt']

    if task.get('subtitle_opt'):
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

    if task.get('thumbnail_opt'):
        ydl_opts['writethumbnail'] = True
        ydl_opts.setdefault('postprocessors', [])
        ydl_opts['postprocessors'].append({
            'key': 'EmbedThumbnail',
            'already_have_thumbnail': False,
        })

    if download_ranges is not None:
        ydl_opts['download_ranges'] = download_ranges
        ydl_opts['force_keyframes_at_cuts'] = True

    return ydl_opts
