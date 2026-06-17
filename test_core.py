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
