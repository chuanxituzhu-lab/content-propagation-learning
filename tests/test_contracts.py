from __future__ import annotations

import unittest
from datetime import timedelta
from uuid import uuid4

from pydantic import ValidationError

from core.contracts.models import (
    Claim,
    Comparison,
    EvidenceRecord,
    MetricSnapshot,
    PatternLifecycle,
    Provenance,
    Scope,
    utc_now,
)
from core.evidence.contract import EvidenceIntegrityError, create_candidate


class ContractTests(unittest.TestCase):
    def test_raw_metric_snapshot_is_immutable(self):
        snapshot = MetricSnapshot(
            sample_id=uuid4(),
            views=10,
            source=Provenance(plugin_id="test", plugin_version="0.1"),
            raw_snapshot_ref="raw://1",
        )
        with self.assertRaises((ValidationError, TypeError)):
            snapshot.views = 20

    def test_candidate_requires_support_and_is_stopped_at_candidate(self):
        support, counter, control = uuid4(), uuid4(), uuid4()
        claim = Claim(
            statement="controlled difference",
            scope=Scope(platforms=["test"]),
            subject_sample_ids=[support, counter, control],
            provenance=Provenance(plugin_id="test", plugin_version="0.1"),
        )
        evidence = EvidenceRecord(
            claim_id=claim.claim_id,
            evidence_for=[support],
            evidence_against=[counter],
            controls=[control],
            comparison=Comparison(method="paired", sample_count=3),
            confidence=0.6,
            generated_by=Provenance(plugin_id="test", plugin_version="0.1"),
        )
        candidate = create_candidate(
            claim,
            [evidence],
            provenance=Provenance(plugin_id="test", plugin_version="0.1"),
        )
        self.assertEqual(candidate.lifecycle, PatternLifecycle.CANDIDATE)
        self.assertEqual(candidate.metrics.counterexample_count, 1)
        self.assertEqual(candidate.metrics.control_count, 1)

    def test_evidence_cannot_reference_outside_claim_scope(self):
        claim_sample = uuid4()
        claim = Claim(
            statement="bad chain",
            subject_sample_ids=[claim_sample],
            provenance=Provenance(plugin_id="test", plugin_version="0.1"),
        )
        evidence = EvidenceRecord(
            claim_id=claim.claim_id,
            evidence_for=[uuid4()],
            comparison=Comparison(method="paired", sample_count=1),
            confidence=0.5,
            generated_by=Provenance(plugin_id="test", plugin_version="0.1"),
        )
        with self.assertRaises(EvidenceIntegrityError):
            create_candidate(claim, [evidence], provenance=Provenance(plugin_id="test", plugin_version="0.1"))


if __name__ == "__main__":
    unittest.main()

