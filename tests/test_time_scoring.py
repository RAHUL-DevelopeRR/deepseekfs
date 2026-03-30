"""
Unit tests for core/time/scoring.py
Covers: calculate_time_score, get_time_multiplier,
        extract_time_target, calculate_target_time_score
"""
import os
import sys
import math
import time
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.time.scoring import (
    calculate_time_score,
    get_time_multiplier,
    extract_time_target,
    calculate_target_time_score,
)


class TestCalculateTimeScore:
    """Tests for calculate_time_score()"""

    def test_very_recent_file_scores_near_one(self):
        now = time.time()
        score = calculate_time_score(now - 60)  # 1 minute ago
        assert score > 0.99

    def test_brand_new_file_scores_one(self):
        now = time.time()
        score = calculate_time_score(now)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_score_decreases_with_age(self):
        now = time.time()
        recent = calculate_time_score(now - 86400)       # 1 day ago
        older = calculate_time_score(now - 86400 * 30)   # 30 days ago
        oldest = calculate_time_score(now - 86400 * 90)  # 90 days ago
        assert recent > older > oldest

    def test_score_within_zero_one(self):
        now = time.time()
        for delta_days in [0, 1, 7, 30, 90, 365]:
            score = calculate_time_score(now - delta_days * 86400)
            assert 0.0 <= score <= 1.0, f"Score out of range for {delta_days} days ago"

    def test_future_file_returns_one(self):
        future = time.time() + 86400
        score = calculate_time_score(future)
        assert score == 1.0

    def test_custom_reference_time(self):
        reference = 1_700_000_000.0  # fixed reference
        file_ts = reference - 86400  # 1 day before reference
        score = calculate_time_score(file_ts, reference_time=reference)
        assert 0.0 < score < 1.0

    def test_custom_decay_days_faster_decay(self):
        now = time.time()
        file_ts = now - 86400 * 5  # 5 days ago
        score_fast = calculate_time_score(file_ts, decay_days=3)
        score_slow = calculate_time_score(file_ts, decay_days=30)
        assert score_fast < score_slow

    def test_returns_float(self):
        score = calculate_time_score(time.time() - 1000)
        assert isinstance(score, float)

    def test_exponential_decay_at_decay_days(self):
        """At exactly decay_days, score should be exp(-1) ≈ 0.368"""
        now = time.time()
        decay_days = 30
        file_ts = now - decay_days * 86400
        score = calculate_time_score(file_ts, reference_time=now, decay_days=decay_days)
        assert score == pytest.approx(math.exp(-1), abs=0.01)

    def test_zero_timestamp(self):
        """Very old file (epoch 0) should score near zero"""
        score = calculate_time_score(0.0)
        assert score < 0.01


class TestGetTimeMultiplier:
    """Tests for get_time_multiplier()"""

    def test_no_keywords_returns_one(self):
        assert get_time_multiplier("machine learning report") == 1.0
        assert get_time_multiplier("python code files") == 1.0

    def test_recent_keyword(self):
        assert get_time_multiplier("recent documents") == 1.5

    def test_latest_keyword(self):
        assert get_time_multiplier("latest files") == 1.5

    def test_today_keyword(self):
        assert get_time_multiplier("files from today") == 2.0

    def test_yesterday_keyword(self):
        assert get_time_multiplier("modified yesterday") == 1.8

    def test_this_week_keyword(self):
        assert get_time_multiplier("this week reports") == 1.4

    def test_last_week_keyword(self):
        assert get_time_multiplier("last week") == 1.2

    def test_this_month_keyword(self):
        assert get_time_multiplier("this month invoices") == 1.1

    def test_old_keyword_no_boost(self):
        # "old" maps to 0.5 but max(1.0, 0.5)=1.0 — function never drops below 1.0
        assert get_time_multiplier("old files") == 1.0

    def test_archive_keyword_no_boost(self):
        # "archive" maps to 0.3 but max(1.0, 0.3)=1.0 — same reason
        assert get_time_multiplier("archive backup files") == 1.0

    def test_multiple_keywords_max_wins(self):
        # "today" (2.0) and "recent" (1.5) → max = 2.0
        assert get_time_multiplier("recent files from today") == 2.0

    def test_case_insensitive(self):
        assert get_time_multiplier("Recent Documents") == 1.5
        assert get_time_multiplier("TODAY files") == 2.0

    def test_empty_query(self):
        assert get_time_multiplier("") == 1.0

    def test_returns_float(self):
        result = get_time_multiplier("show me recent pdfs")
        assert isinstance(result, float)


class TestExtractTimeTarget:
    """Tests for extract_time_target()"""

    def test_no_date_returns_none_and_original(self):
        ts, cleaned = extract_time_target("machine learning files")
        assert ts is None
        assert cleaned == "machine learning files"

    def test_returns_tuple(self):
        result = extract_time_target("any query")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_cleaned_query_is_string(self):
        _, cleaned = extract_time_target("some query")
        assert isinstance(cleaned, str)

    def test_no_date_preserves_full_query(self):
        query = "python scripts in downloads"
        ts, cleaned = extract_time_target(query)
        assert ts is None
        assert cleaned == query

    def test_exception_safety(self):
        # Should never raise even with weird input
        try:
            ts, cleaned = extract_time_target("")
            assert ts is None
        except Exception:
            pytest.fail("extract_time_target raised an exception on empty input")

    def test_exception_safety_unicode(self):
        try:
            ts, cleaned = extract_time_target("文件从今天")
        except Exception:
            pytest.fail("extract_time_target raised an exception on unicode input")


class TestCalculateTargetTimeScore:
    """Tests for calculate_target_time_score()"""

    def test_exact_match_returns_one(self):
        target = 1_700_000_000.0
        score = calculate_target_time_score(target, target)
        assert score == 1.0

    def test_within_one_day_returns_one(self):
        target = 1_700_000_000.0
        file_ts = target + 3600  # 1 hour difference
        score = calculate_target_time_score(file_ts, target)
        assert score == 1.0

    def test_score_decreases_farther_from_target(self):
        target = 1_700_000_000.0
        close = calculate_target_time_score(target + 86400, target)      # ~1 day
        far = calculate_target_time_score(target + 86400 * 10, target)   # 10 days
        further = calculate_target_time_score(target + 86400 * 30, target)  # 30 days
        assert close >= far >= further

    def test_score_within_zero_one(self):
        target = 1_700_000_000.0
        for delta_days in [0, 1, 5, 10, 30, 90]:
            score = calculate_target_time_score(target + delta_days * 86400, target)
            assert 0.0 <= score <= 1.0

    def test_symmetric_before_and_after(self):
        target = 1_700_000_000.0
        offset = 86400 * 5  # 5 days
        before = calculate_target_time_score(target - offset, target)
        after = calculate_target_time_score(target + offset, target)
        assert before == pytest.approx(after, abs=0.001)

    def test_returns_float(self):
        result = calculate_target_time_score(1_700_000_000.0, 1_700_000_000.0)
        assert isinstance(result, float)

    def test_very_far_away_scores_near_zero(self):
        target = 1_700_000_000.0
        file_ts = target + 86400 * 365  # 1 year off
        score = calculate_target_time_score(file_ts, target)
        assert score < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
