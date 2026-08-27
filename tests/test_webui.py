from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from webui.server import WebApplication


class WebUITests(unittest.TestCase):
    def test_health_exposes_registry_without_platform_logic_in_ui(self):
        with tempfile.TemporaryDirectory() as temp:
            app = WebApplication(Path(temp))
            status, payload = app.get("/api/health")
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "ok")
            ids = {item["manifest"]["plugin_id"] for item in payload["plugins"]}
            self.assertIn("world.youtube.discovery", ids)
            self.assertIn("world.local-video.extractor", ids)

    def test_fixture_endpoint_returns_candidate_and_acceptance_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            app = WebApplication(Path(temp))
            status, payload = app.post("/api/proof/fixture", {})
            self.assertEqual(status, 200)
            self.assertEqual(payload["pattern_candidate"]["lifecycle"], "candidate")
            self.assertTrue(payload["acceptance"]["support_and_counterevidence_present"])


if __name__ == "__main__":
    unittest.main()

