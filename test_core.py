"""Test pytest cho các hàm logic thuần trong core.py.

Chạy: pytest -v
"""

import pytest

import core

# ---------------------- parse_time ----------------------

class TestParseTime:
    def test_empty_is_valid_no_cut(self):
        assert core.parse_time("") == (None, None)
        assert core.parse_time(None) == (None, None)
        assert core.parse_time("   ") == (None, None)

    def test_seconds_only(self):
        sec, err = core.parse_time("45")
        assert err is None
        assert sec == 45.0

    def test_minutes_seconds(self):
        sec, err = core.parse_time("05:30")
        assert err is None
        assert sec == 330.0

    def test_hours_minutes_seconds(self):
        sec, err = core.parse_time("01:02:03")
        assert err is None
        assert sec == 3723.0

    def test_decimal_seconds(self):
        sec, err = core.parse_time("1.5")
        assert err is None
        assert sec == 1.5

    def test_whitespace_trimmed(self):
        sec, err = core.parse_time("  10:00  ")
        assert err is None
        assert sec == 600.0

    def test_too_many_parts(self):
        sec, err = core.parse_time("1:2:3:4")
        assert sec is None
        assert err is not None

    def test_empty_segment(self):
        sec, err = core.parse_time("05:")
        assert sec is None
        assert err is not None

    def test_non_numeric(self):
        sec, err = core.parse_time("ab:cd")
        assert sec is None
        assert err is not None

    def test_negative_value(self):
        sec, err = core.parse_time("-5")
        assert sec is None
        assert err is not None


# ---------------------- get_format_string ----------------------

class TestGetFormatString:
    def test_audio_mp3(self):
        assert core.get_format_string("Âm thanh (MP3)") == 'bestaudio/best'

    def test_best_video(self):
        result = core.get_format_string("Video - Tốt nhất")
        assert result == 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    @pytest.mark.parametrize("label,height", [
        ("Video - 1080p", "1080"),
        ("Video - 720p", "720"),
        ("Video - 480p", "480"),
        ("Video - 1440p", "1440"),
        ("Video - 2160p", "2160"),
    ])
    def test_resolution_labels(self, label, height):
        result = core.get_format_string(label)
        assert f'height<={height}' in result
        assert result.startswith('bestvideo')

    def test_unknown_falls_back_to_best(self):
        result = core.get_format_string("ngẫu nhiên không rõ")
        assert result == 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    def test_none_input(self):
        # Không được ném lỗi với None
        result = core.get_format_string(None)
        assert result.startswith('bestvideo')


# ---------------------- heights_from_info / format_values_from_info ----------------------

class TestHeightsFromInfo:
    def test_extracts_video_heights(self):
        info = {'formats': [
            {'vcodec': 'avc1', 'height': 1080},
            {'vcodec': 'vp9', 'height': 720},
            {'vcodec': 'none', 'height': None},   # audio-only, bỏ qua
            {'acodec': 'mp4a', 'vcodec': 'none'},  # audio-only
        ]}
        assert core.heights_from_info(info) == {1080, 720}

    def test_empty_info(self):
        assert core.heights_from_info({}) == set()
        assert core.heights_from_info(None) == set()

    def test_ignores_formats_without_height(self):
        info = {'formats': [{'vcodec': 'avc1'}, {'vcodec': 'avc1', 'height': 360}]}
        assert core.heights_from_info(info) == {360}


class TestFormatValuesFromInfo:
    def test_builds_sorted_descending(self):
        info = {'formats': [
            {'vcodec': 'avc1', 'height': 480},
            {'vcodec': 'avc1', 'height': 1080},
            {'vcodec': 'avc1', 'height': 720},
        ]}
        values = core.format_values_from_info(info)
        assert values == [
            "Video - Tốt nhất",
            "Video - 1080p",
            "Video - 720p",
            "Video - 480p",
            "Âm thanh (MP3)",
        ]

    def test_no_heights_returns_default(self):
        assert core.format_values_from_info({}) == core.DEFAULT_FORMAT_VALUES
        assert core.format_values_from_info({'formats': []}) == core.DEFAULT_FORMAT_VALUES

    def test_first_is_best_last_is_audio(self):
        info = {'formats': [{'vcodec': 'avc1', 'height': 144}]}
        values = core.format_values_from_info(info)
        assert values[0] == "Video - Tốt nhất"
        assert values[-1] == "Âm thanh (MP3)"
        assert "Video - 144p" in values


# ---------------------- classify_folder ----------------------

class TestClassifyFolder:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=abc", "YouTube"),
        ("https://youtu.be/abc", "YouTube"),
        ("https://www.tiktok.com/@u/video/1", "TikTok"),
        ("https://www.facebook.com/x/videos/1", "Facebook"),
        ("https://fb.watch/abc", "Facebook"),
        ("https://www.instagram.com/reel/abc", "Instagram"),
        ("https://twitter.com/u/status/1", "Twitter_X"),
        ("https://x.com/u/status/1", "Twitter_X"),
        ("https://soundcloud.com/u/track", "SoundCloud"),
    ])
    def test_known_domains(self, url, expected):
        assert core.classify_folder(url) == expected

    def test_unknown_domain(self):
        assert core.classify_folder("https://vimeo.com/123") == "Others"

    def test_empty_url(self):
        assert core.classify_folder("") == "Others"
        assert core.classify_folder(None) == "Others"

    def test_case_insensitive(self):
        assert core.classify_folder("https://WWW.YOUTUBE.COM/watch") == "YouTube"


# ---------------------- get_ffmpeg_path ----------------------

class TestGetFfmpegPath:
    def test_returns_path_or_none(self):
        # Không ném lỗi; trả về str (thư mục tồn tại) hoặc None
        result = core.get_ffmpeg_path()
        assert result is None or isinstance(result, str)

    def test_path_contains_ffmpeg_when_found(self):
        result = core.get_ffmpeg_path()
        if result is not None:
            import os
            exe = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
            assert os.path.exists(os.path.join(result, exe))


# ---------------------- cookie_opts_from_choice ----------------------

class TestCookieOptsFromChoice:
    def test_no_cookie_returns_none(self):
        assert core.cookie_opts_from_choice("Không Dùng Cookie") is None

    def test_empty_or_none_returns_none(self):
        assert core.cookie_opts_from_choice("") is None
        assert core.cookie_opts_from_choice(None) is None
        assert core.cookie_opts_from_choice("   ") is None

    @pytest.mark.parametrize("choice,expected", [
        ("Tài khoản Chrome", ("chrome",)),
        ("Tài khoản Edge", ("edge",)),
        ("Tài khoản Firefox", ("firefox",)),
        ("Tài khoản Brave", ("brave",)),
    ])
    def test_browser_choices(self, choice, expected):
        assert core.cookie_opts_from_choice(choice) == expected

    def test_whitespace_trimmed(self):
        assert core.cookie_opts_from_choice("  Tài khoản Chrome  ") == ("chrome",)


# ---------------------- total_filesize_bytes ----------------------

class TestTotalFilesizeBytes:
    def test_requested_formats_summed(self):
        info = {'requested_formats': [
            {'filesize': 1000},
            {'filesize_approx': 500},
        ]}
        assert core.total_filesize_bytes(info) == 1500

    def test_single_filesize(self):
        assert core.total_filesize_bytes({'filesize': 2048}) == 2048

    def test_filesize_approx_fallback(self):
        assert core.total_filesize_bytes({'filesize_approx': 999}) == 999

    def test_unknown_returns_zero(self):
        assert core.total_filesize_bytes({}) == 0
        assert core.total_filesize_bytes(None) == 0

    def test_requested_formats_with_missing_sizes(self):
        info = {'requested_formats': [{'filesize': 100}, {}]}
        assert core.total_filesize_bytes(info) == 100


# ---------------------- human_size_label ----------------------

class TestHumanSizeLabel:
    def test_positive_size_in_mb(self):
        label = core.human_size_label(1024 * 1024 * 5)  # 5 MB
        assert "5.0 MB" in label
        assert label.startswith("Dung lượng cỡ:")

    def test_zero_unknown(self):
        assert core.human_size_label(0) == "Dung lượng: [Chưa rõ]"

    def test_none_unknown(self):
        assert core.human_size_label(None) == "Dung lượng: [Chưa rõ]"


# ---------------------- format_duration ----------------------

class TestFormatDuration:
    def test_minutes_and_seconds(self):
        assert core.format_duration(330) == "Thời lượng: 5 phút 30 giây"

    def test_seconds_only(self):
        assert core.format_duration(45) == "Thời lượng: 0 phút 45 giây"

    def test_zero_and_none(self):
        assert core.format_duration(0) == "Thời lượng: 0 phút 0 giây"
        assert core.format_duration(None) == "Thời lượng: 0 phút 0 giây"

    def test_float_truncated(self):
        assert core.format_duration(90.9) == "Thời lượng: 1 phút 30 giây"


# ---------------------- resolve_final_filepath ----------------------

class TestResolveFinalFilepath:
    def test_requested_downloads_filepath(self):
        info = {'requested_downloads': [{'filepath': '/d/video.mp4'}]}
        # exists luôn True -> trả về chính candidate
        result = core.resolve_final_filepath(info, is_audio=False, exists=lambda p: True)
        assert result == '/d/video.mp4'

    def test_falls_back_to_underscore_filename(self):
        info = {'_filename': '/d/clip.mp4'}
        result = core.resolve_final_filepath(info, is_audio=False, exists=lambda p: True)
        assert result == '/d/clip.mp4'

    def test_no_candidate_returns_none(self):
        assert core.resolve_final_filepath({}, is_audio=False, exists=lambda p: True) is None
        assert core.resolve_final_filepath(None, is_audio=False, exists=lambda p: True) is None

    def test_audio_prefers_mp3(self):
        info = {'_filename': '/d/song.webm'}
        # Chỉ file .mp3 tồn tại
        result = core.resolve_final_filepath(
            info, is_audio=True, exists=lambda p: p == '/d/song.mp3')
        assert result == '/d/song.mp3'

    def test_audio_without_mp3_falls_through(self):
        info = {'_filename': '/d/song.webm'}
        # Không có mp3, nhưng file gốc tồn tại
        result = core.resolve_final_filepath(
            info, is_audio=True, exists=lambda p: p == '/d/song.webm')
        assert result == '/d/song.webm'

    def test_probes_alternate_extensions(self):
        info = {'_filename': '/d/movie.webm'}
        # File gốc .webm không còn, nhưng đã merge sang .mkv
        result = core.resolve_final_filepath(
            info, is_audio=False, exists=lambda p: p == '/d/movie.mkv')
        assert result == '/d/movie.mkv'

    def test_returns_candidate_when_nothing_exists(self):
        info = {'_filename': '/d/ghost.mp4'}
        # Không file nào tồn tại -> vẫn trả candidate gốc
        result = core.resolve_final_filepath(info, is_audio=False, exists=lambda p: False)
        assert result == '/d/ghost.mp4'

    def test_requested_downloads_underscore_filename(self):
        info = {'requested_downloads': [{'_filename': '/d/a.mp4'}]}
        result = core.resolve_final_filepath(info, is_audio=False, exists=lambda p: True)
        assert result == '/d/a.mp4'
