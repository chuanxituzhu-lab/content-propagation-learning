from __future__ import annotations

import unittest
from datetime import timedelta
from uuid import uuid4

from core.contracts.models import ContentSample, MetricSnapshot, PlatformContentRef, utc_now
from core.scoring.scorer import CreatorHistoryItem, score_sample


def make_sample(age_days: float = 2) -> ContentSample:
    ref = PlatformContentRef(
        platform="test",
        platform_content_id=str(uuid4()),
        canonical_url="https://example.invalid/test",
        discovery_source="test",
        collector_plugin="test",
        collector_version="0.1",
    )
    return ContentSample(ref_id=ref.ref_id, published_at=utc_now() - timedelta(days=age_days))


def make_snapshot(sample_id, views, captured_at=None, **kwargs):
    return MetricSnapshot(
        sample_id=sample_id,
        views=views,
        captured_at=captured_at or utc_now(),
        source={"plugin_id": "test", "plugin_version": "0.1"},
        raw_snapshot_ref="raw://test",
        **kwargs,
    )


class ScoringTests(unittest.TestCase):
    def setUp(self):
        now = utc_now()
        self.history = [
            CreatorHistoryItem(sample_id=str(index), views=10_000, captured_at=now - timedelta(days=index + 1))
            for index in range(8)
        ]

    def test_baseline_and_outlier(self):
        sample = make_sample()
        snapshot = make_snapshot(sample.sample_id, 50_000, likes=5_000, comments=100)
        result = score_sample(sample, snapshot, creator_history=self.history)
        self.assertEqual(result.creator_baseline_views, 10_000)
        self.assertEqual(result.relative_score, 5)
        self.assertEqual(result.primary_class.value, "outlier")
        self.assertIn("strong_outlier", result.signals)
        self.assertEqual(result.like_rate, 0.1)

    def test_underperform_waits_for_maturity(self):
        sample = make_sample(age_days=2)
        result = score_sample(sample, make_snapshot(sample.sample_id, 4_000), creator_history=self.history)
        self.assertEqual(result.primary_class.value, "underperform")

    def test_unknown_when_baseline_is_insufficient(self):
        sample = make_sample()
        history = self.history[:7]
        result = score_sample(sample, make_snapshot(sample.sample_id, 100_000), creator_history=history)
        self.assertEqual(result.primary_class.value, "unknown")
        self.assertIsNone(result.relative_score)

    def test_rising_is_a_signal_and_outlier_keeps_priority(self):
        sample = make_sample(age_days=1)
        earlier = make_snapshot(sample.sample_id, 10_000, captured_at=utc_now() - timedelta(hours=2))
        current = make_snapshot(sample.sample_id, 30_000, captured_at=utc_now())
        result = score_sample(
            sample,
            current,
            sample_snapshots=[earlier],
            creator_history=self.history,
            baseline_velocity=4_000,
        )
        self.assertIn("rising", result.signals)
        self.assertEqual(result.primary_class.value, "outlier")


if __name__ == "__main__":
    unittest.main()
