"""Test pytest cho queue_logic.py (logic hàng đợi & retry).

Chạy: pytest -v
"""

import queue_logic

# ---------------------- clamp_concurrency ----------------------

class TestClampConcurrency:
    def test_within_range(self):
        assert queue_logic.clamp_concurrency(2) == 2
        assert queue_logic.clamp_concurrency("3") == 3

    def test_below_min(self):
        assert queue_logic.clamp_concurrency(0) == 1
        assert queue_logic.clamp_concurrency(-5) == 1

    def test_above_max(self):
        assert queue_logic.clamp_concurrency(10) == 4
        assert queue_logic.clamp_concurrency(5) == 4

    def test_invalid_returns_min(self):
        assert queue_logic.clamp_concurrency("abc") == 1
        assert queue_logic.clamp_concurrency(None) == 1

    def test_custom_bounds(self):
        assert queue_logic.clamp_concurrency(8, lo=2, hi=6) == 6
        assert queue_logic.clamp_concurrency(1, lo=2, hi=6) == 2


# ---------------------- make_batches ----------------------

class TestMakeBatches:
    def test_even_split(self):
        assert queue_logic.make_batches([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_uneven_split(self):
        assert queue_logic.make_batches([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_size_larger_than_list(self):
        assert queue_logic.make_batches([1, 2], 5) == [[1, 2]]

    def test_empty(self):
        assert queue_logic.make_batches([], 3) == []

    def test_size_one_is_sequential(self):
        assert queue_logic.make_batches([1, 2, 3], 1) == [[1], [2], [3]]

    def test_size_zero_treated_as_one(self):
        assert queue_logic.make_batches([1, 2], 0) == [[1], [2]]


# ---------------------- should_retry_without_subtitles ----------------------

class TestShouldRetry:
    def test_retry_on_subtitle_error(self):
        task = {'subtitle_opt': True}
        assert queue_logic.should_retry_without_subtitles(task, "Unable to download subtitles") is True

    def test_retry_on_429(self):
        task = {'subtitle_opt': True}
        assert queue_logic.should_retry_without_subtitles(task, "HTTP Error 429: Too Many Requests") is True

    def test_no_retry_when_subtitles_off(self):
        task = {'subtitle_opt': False}
        assert queue_logic.should_retry_without_subtitles(task, "subtitles 429") is False

    def test_no_retry_on_unrelated_error(self):
        task = {'subtitle_opt': True}
        assert queue_logic.should_retry_without_subtitles(task, "Video unavailable") is False

    def test_handles_empty_message(self):
        task = {'subtitle_opt': True}
        assert queue_logic.should_retry_without_subtitles(task, "") is False
        assert queue_logic.should_retry_without_subtitles(task, None) is False


# ---------------------- is_cancel_error ----------------------

class TestIsCancelError:
    def test_cancel(self):
        assert queue_logic.is_cancel_error("Something CANCELLED_BY_USER happened") is True

    def test_not_cancel(self):
        assert queue_logic.is_cancel_error("Network error") is False

    def test_none(self):
        assert queue_logic.is_cancel_error(None) is False


# ---------------------- summarize_queue_result ----------------------

class TestSummarize:
    def test_cancelled(self):
        assert "hủy" in queue_logic.summarize_queue_result(5, 2, cancelled=True).lower()

    def test_all_success(self):
        msg = queue_logic.summarize_queue_result(3, 0, cancelled=False)
        assert "Tuyệt vời" in msg

    def test_all_failed(self):
        msg = queue_logic.summarize_queue_result(3, 3, cancelled=False)
        assert "Tất cả" in msg

    def test_partial_failure(self):
        msg = queue_logic.summarize_queue_result(5, 2, cancelled=False)
        assert "2/5" in msg
