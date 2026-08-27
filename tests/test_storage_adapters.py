from __future__ import annotations

import tempfile
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.contracts.models import MetricSnapshot, utc_now
from plugins.platforms.bilibili.adapter import BilibiliCollectorAdapter
from plugins.platforms.youtube.adapter import YouTubeCollectorAdapter
from plugins.storage.sqlite_store.store import SQLiteCoreStore


@unittest.skipUnless(importlib.util.find_spec("duckdb"), "duckdb optional dependency is not installed")
class DuckDBStorageTests(unittest.TestCase):
    def test_duckdb_accepts_derived_metrics(self):
        from core.scoring.scorer import SampleDerivedMetrics
        from plugins.storage.duckdb_analysis.store import DuckDBAnalysisStore

        with tempfile.TemporaryDirectory() as temp:
            store = DuckDBAnalysisStore(Path(temp) / "analysis.duckdb")
            self.assertEqual(store.insert_derived([SampleDerivedMetrics(sample_id=str(uuid4()))]), 1)
            self.assertEqual(len(store.query("SELECT * FROM derived_metrics")), 1)
            store.close()


class StorageAdapterTests(unittest.TestCase):
    def test_sqlite_is_append_only_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "core.sqlite3"
            with SQLiteCoreStore(path) as store:
                snapshot = MetricSnapshot(
                    sample_id=uuid4(),
                    views=123,
                    source={"plugin_id": "test", "plugin_version": "0.1"},
                    raw_snapshot_ref="raw://1",
                )
                store.save(snapshot)
                self.assertEqual(store.get("MetricSnapshot", snapshot.snapshot_id).views, 123)
                with self.assertRaises(ValueError):
                    store.save(snapshot)
                raw_id = store.append_raw_snapshot(platform="test", payload={"views": 123})
                self.assertEqual(len(store.raw_snapshots()), 1)
                self.assertTrue(raw_id)

    @patch("plugins.platforms.youtube.adapter._extract")
    def test_youtube_mapping_is_canonical(self, extract):
        extract.return_value = {
            "id": "abc",
            "webpage_url": "https://youtube.invalid/watch?v=abc",
            "title": "Title",
            "view_count": 0,
            "like_count": 7,
            "comment_count": 2,
            "channel_id": "creator",
        }
        with tempfile.TemporaryDirectory() as temp:
            result = YouTubeCollectorAdapter(temp).collect("https://youtube.invalid/watch?v=abc")
            self.assertEqual(result.platform, "youtube")
            self.assertEqual(result.platform_content_id, "abc")
            self.assertEqual(result.metrics.views, 0)
            self.assertIsNone(result.metrics.favorites)

    @patch("plugins.platforms.bilibili.adapter._extract")
    def test_bilibili_mapping_does_not_leak_platform_fields(self, extract):
        extract.return_value = {
            "id": "BV1abcdefgh",
            "webpage_url": "https://bilibili.invalid/video/BV1abcdefgh",
            "title": "中文标题",
            "play_count": 10,
            "favorite_count": 3,
        }
        with tempfile.TemporaryDirectory() as temp:
            result = BilibiliCollectorAdapter(temp).collect("https://bilibili.invalid/video/BV1abcdefgh")
            self.assertEqual(result.platform_content_id, "BV1abcdefgh")
            self.assertEqual(result.metrics.views, 10)
            self.assertEqual(result.metrics.favorites, 3)
            self.assertFalse(hasattr(result, "aid"))


if __name__ == "__main__":
    unittest.main()
