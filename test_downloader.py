"""Test pytest cho downloader.py (dựng tùy chọn yt-dlp) và config_store.py (I/O).

Chạy: pytest -v
"""

import os

import config_store
import downloader

# ---------------------- build_out_template ----------------------

class TestBuildOutTemplate:
    def test_single_video(self):
        tpl = downloader.build_out_template("/downloads", False)
        assert tpl == os.path.join("/downloads", '%(title)s.%(ext)s')

    def test_playlist(self):
        tpl = downloader.build_out_template("/downloads", True)
        assert '%(playlist_index)s' in tpl
        assert '%(playlist_title)s' in tpl


# ---------------------- build_ydl_opts ----------------------

def _base_task(**over):
    task = {
        'format_choice': "Video - Tốt nhất",
        'is_playlist': False,
        'cookie_opt': None,
        'subtitle_opt': False,
        'thumbnail_opt': False,
    }
    task.update(over)
    return task


class TestBuildYdlOpts:
    def test_basic_defaults(self):
        opts = downloader.build_ydl_opts(_base_task(), "out.%(ext)s")
        assert opts['outtmpl'] == "out.%(ext)s"
        assert opts['noplaylist'] is True
        assert opts['quiet'] is True
        assert opts['merge_output_format'] == 'mp4'
        assert 'progress_hooks' not in opts  # không truyền hook

    def test_playlist_sets_noplaylist_false(self):
        opts = downloader.build_ydl_opts(_base_task(is_playlist=True), "o")
        assert opts['noplaylist'] is False

    def test_progress_hook_attached(self):
        hook = lambda d: None
        opts = downloader.build_ydl_opts(_base_task(), "o", progress_hook=hook)
        assert opts['progress_hooks'] == [hook]

    def test_ffmpeg_location_set_when_given(self):
        opts = downloader.build_ydl_opts(_base_task(), "o", ffmpeg_dir="/path/ff")
        assert opts['ffmpeg_location'] == "/path/ff"

    def test_ffmpeg_location_absent_when_none(self):
        opts = downloader.build_ydl_opts(_base_task(), "o", ffmpeg_dir=None)
        assert 'ffmpeg_location' not in opts

    def test_mp3_adds_extract_audio_postprocessor(self):
        opts = downloader.build_ydl_opts(_base_task(format_choice="Âm thanh (MP3)"), "o")
        keys = [p['key'] for p in opts.get('postprocessors', [])]
        assert 'FFmpegExtractAudio' in keys
        assert 'merge_output_format' not in opts

    def test_thumbnail_adds_embed_postprocessor(self):
        opts = downloader.build_ydl_opts(_base_task(thumbnail_opt=True), "o")
        keys = [p['key'] for p in opts.get('postprocessors', [])]
        assert 'EmbedThumbnail' in keys
        assert opts['writethumbnail'] is True

    def test_mp3_and_thumbnail_combined(self):
        opts = downloader.build_ydl_opts(
            _base_task(format_choice="Âm thanh (MP3)", thumbnail_opt=True), "o")
        keys = [p['key'] for p in opts.get('postprocessors', [])]
        assert 'FFmpegExtractAudio' in keys
        assert 'EmbedThumbnail' in keys

    def test_subtitle_opts(self):
        opts = downloader.build_ydl_opts(_base_task(subtitle_opt=True), "o")
        assert opts['writesubtitles'] is True
        assert opts['writeautomaticsub'] is True
        assert 'vi' in opts['subtitleslangs']

    def test_cookie_opt(self):
        opts = downloader.build_ydl_opts(_base_task(cookie_opt=('chrome',)), "o")
        assert opts['cookiesfrombrowser'] == ('chrome',)

    def test_playlist_items(self):
        opts = downloader.build_ydl_opts(_base_task(playlist_items="1,3,5"), "o")
        assert opts['playlist_items'] == "1,3,5"

    def test_download_ranges(self):
        rng = lambda info, ydl: [(0, 10)]
        opts = downloader.build_ydl_opts(_base_task(), "o", download_ranges=rng)
        assert opts['download_ranges'] is rng
        assert opts['force_keyframes_at_cuts'] is True


# ---------------------- config_store ----------------------

class TestConfigStore:
    def test_load_missing_returns_empty(self, tmp_path):
        p = str(tmp_path / "nope.json")
        assert config_store.load_config(p) == {}

    def test_save_then_load_roundtrip(self, tmp_path):
        p = str(tmp_path / "cfg.json")
        data = {'save_dir': 'D:/x', 'format_choice': 'Video - 720p', 'smart_folder': True}
        assert config_store.save_config(data, p) is True
        assert config_store.load_config(p) == data

    def test_load_corrupt_returns_empty(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json", encoding='utf-8')
        assert config_store.load_config(str(p)) == {}

    def test_history_missing_returns_empty_list(self, tmp_path):
        p = str(tmp_path / "h.json")
        assert config_store.load_history(p) == []

    def test_add_history_inserts_at_front(self, tmp_path):
        p = str(tmp_path / "h.json")
        config_store.add_history("First", "/a", path=p)
        config_store.add_history("Second", "/b", path=p)
        data = config_store.load_history(p)
        assert data[0]['title'] == "Second"
        assert data[1]['title'] == "First"

    def test_add_history_respects_max(self, tmp_path):
        p = str(tmp_path / "h.json")
        for i in range(10):
            config_store.add_history(f"T{i}", "/x", path=p, max_items=5)
        data = config_store.load_history(p)
        assert len(data) == 5
        assert data[0]['title'] == "T9"

    def test_add_history_with_filepath(self, tmp_path):
        p = str(tmp_path / "h.json")
        config_store.add_history("Vid", "/folder", filepath="/folder/vid.mp4", path=p)
        data = config_store.load_history(p)
        assert data[0]['filepath'] == "/folder/vid.mp4"

    def test_clear_history(self, tmp_path):
        p = str(tmp_path / "h.json")
        config_store.add_history("X", "/x", path=p)
        assert config_store.clear_history(p) is True
        assert config_store.load_history(p) == []


# ---------------------- build_download_ranges ----------------------

class TestBuildDownloadRanges:
    def test_both_none_returns_none(self):
        assert downloader.build_download_ranges(None, None) is None

    def test_start_only_opens_end(self):
        fn = downloader.build_download_ranges(10, None)
        ranges = fn({}, None)
        assert ranges[0][0] == 10
        assert ranges[0][1] == float('inf')

    def test_end_only_starts_at_zero(self):
        fn = downloader.build_download_ranges(None, 30)
        ranges = fn({}, None)
        assert ranges[0] == (0, 30)

    def test_both_set(self):
        fn = downloader.build_download_ranges(5, 25)
        assert fn({}, None) == [(5, 25)]

    def test_integrates_with_build_ydl_opts(self):
        fn = downloader.build_download_ranges(0, 10)
        opts = downloader.build_ydl_opts(_base_task(), "o", download_ranges=fn)
        assert opts['download_ranges'] is fn
        assert opts['force_keyframes_at_cuts'] is True
