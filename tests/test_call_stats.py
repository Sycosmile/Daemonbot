"""
tests/test_call_stats.py — Pure math for /stats (median resists outlier skew).
"""

import pytest
from services.research import compute_call_stats


class TestComputeCallStats:
    def test_empty_returns_zeroed_result(self):
        result = compute_call_stats([])
        assert result == {"median": 0.0, "average": 0.0, "hit_rate": 0.0, "n": 0}

    def test_single_value(self):
        result = compute_call_stats([50.0])
        assert result["median"] == 50.0
        assert result["average"] == 50.0
        assert result["n"] == 1

    def test_median_with_odd_count(self):
        result = compute_call_stats([-50.0, 10.0, 200.0])
        assert result["median"] == 10.0

    def test_median_with_even_count(self):
        result = compute_call_stats([10.0, 20.0, 30.0, 40.0])
        assert result["median"] == 25.0

    def test_one_outlier_does_not_dominate_median(self):
        # 1 huge winner among 9 losers — average looks decent, median should not
        returns = [5000.0] + [-50.0] * 9
        result = compute_call_stats(returns)
        assert result["median"] == -50.0
        assert result["average"] > result["median"]  # average gets dragged up by the outlier

    def test_hit_rate_counts_only_at_or_above_threshold(self):
        # default threshold is 100.0 (i.e. a 2x)
        returns = [99.0, 100.0, 150.0, -20.0]
        result = compute_call_stats(returns)
        assert result["hit_rate"] == 50.0  # 2 of 4 hit

    def test_custom_hit_threshold(self):
        returns = [40.0, 60.0, 80.0]
        result = compute_call_stats(returns, hit_threshold=50.0)
        assert result["hit_rate"] == pytest.approx(200 / 3)  # 2 of 3 hit
