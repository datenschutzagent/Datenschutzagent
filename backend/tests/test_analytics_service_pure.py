"""Reine Unit-Tests fuer Helfer in app.services.analytics_service.

Brauchen keine DB, sind also auch in CI ohne Postgres lauffaehig.
"""

from app.services.maturity_service import MATURITY_WEIGHTS
from app.services.pipeline_service import _avv_bucket
from app.services.velocity_service import (
    _histogram_days,
    _histogram_hours,
    _percentile,
    _summarize_funnel,
)


def test_maturity_weights_sum_to_one():
    assert abs(sum(MATURITY_WEIGHTS.values()) - 1.0) < 1e-6


def test_avv_bucket_overdue_for_expired_status():
    assert _avv_bucket(None, "expired") == "overdue"
    assert _avv_bucket(120, "expired") == "overdue"


def test_avv_bucket_overdue_for_negative_days():
    assert _avv_bucket(-1, "signed") == "overdue"
    assert _avv_bucket(-365, "signed") == "overdue"


def test_avv_bucket_undated_for_no_expiry():
    assert _avv_bucket(None, "signed") == "undated"
    assert _avv_bucket(None, "pending") == "undated"


def test_avv_bucket_classifies_by_days():
    assert _avv_bucket(0, "signed") == "0_30"
    assert _avv_bucket(30, "signed") == "0_30"
    assert _avv_bucket(31, "signed") == "31_90"
    assert _avv_bucket(90, "signed") == "31_90"
    assert _avv_bucket(91, "signed") == "91_180"
    assert _avv_bucket(180, "signed") == "91_180"
    assert _avv_bucket(181, "signed") == "180_plus"


def test_percentile_empty_returns_none():
    assert _percentile([], 50) is None


def test_percentile_single_value():
    assert _percentile([42.0], 50) == 42.0
    assert _percentile([42.0], 90) == 42.0


def test_percentile_median():
    assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0


def test_percentile_p90_is_high_value():
    vals = [float(i) for i in range(1, 11)]  # 1..10
    p90 = _percentile(vals, 90)
    assert p90 is not None and p90 >= 9.0


def test_histogram_days_buckets_correctly():
    h = _histogram_days([1.0, 5.0, 10.0, 20.0, 45.0, 100.0])
    counts = {b["bucket"]: b["count"] for b in h}
    assert counts["0-7"] == 2
    assert counts["8-14"] == 1
    assert counts["15-30"] == 1
    assert counts["31-60"] == 1
    assert counts["61+"] == 1


def test_histogram_days_empty():
    h = _histogram_days([])
    assert all(b["count"] == 0 for b in h)
    assert {b["bucket"] for b in h} == {"0-7", "8-14", "15-30", "31-60", "61+"}


def test_histogram_hours_72h_threshold():
    """72h ist die DSGVO-Grenze fuer Behoerden-Meldung."""
    h = _histogram_hours([10.0, 30.0, 50.0, 100.0, 200.0])
    counts = {b["bucket"]: b["count"] for b in h}
    assert counts["0-24h"] == 1
    assert counts["24-48h"] == 1
    assert counts["48-72h"] == 1
    assert counts["72-168h"] == 1
    assert counts[">168h"] == 1


def test_summarize_funnel_skips_negative_durations():
    rows = [
        ("created", "updated", 5.0),
        ("updated", "closed", -2.0),  # invalid, should be skipped
        ("created", "updated", 10.0),
        ("created", "updated", None),  # invalid, should be skipped
    ]
    result = _summarize_funnel("Test", rows)
    assert result["entity"] == "Test"
    assert len(result["steps"]) == 1
    step = result["steps"][0]
    assert step["transition"] == "created → updated"
    assert step["sample_size"] == 2
    assert step["median_hours"] == 7.5 or step["avg_hours"] == 7.5


def test_summarize_funnel_handles_empty_input():
    result = _summarize_funnel("Empty", [])
    assert result["entity"] == "Empty"
    assert result["steps"] == []
