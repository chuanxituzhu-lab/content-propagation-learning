from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cli.proof01 import run_fixture


class IntegrationProofTests(unittest.TestCase):
    def test_fixture_proof_reaches_pattern_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            report = run_fixture(Path(temp))
            self.assertEqual(report["proof"], "Integration Proof 01")
            self.assertEqual(report["pattern_candidate"]["lifecycle"], "candidate")
            for gate in (
                "raw_to_canonical_traceable",
                "creator_baseline_computed",
                "outlier_and_controls_found",
                "local_extractor_registered",
                "support_and_counterevidence_present",
                "pattern_candidate_traceable",
            ):
                self.assertTrue(report["acceptance"][gate])
            self.assertTrue((Path(temp) / "data" / "db" / "core.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
