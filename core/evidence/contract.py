"""Evidence chain helpers. Knowledge cannot exist without traceable evidence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from core.contracts.models import (
    Claim,
    EvidenceRecord,
    EvidenceStatus,
    PatternCandidate,
    PatternLifecycle,
    PatternMetrics,
    Provenance,
    Scope,
    utc_now,
)


class EvidenceIntegrityError(ValueError):
    pass


def validate_evidence_chain(
    claim: Claim,
    evidence: EvidenceRecord,
    pattern: PatternCandidate | None = None,
) -> None:
    if evidence.claim_id != claim.claim_id:
        raise EvidenceIntegrityError("evidence does not reference the supplied claim")
    subject_ids = set(claim.subject_sample_ids)
    observed_ids = set(evidence.evidence_for) | set(evidence.evidence_against) | set(evidence.controls)
    if subject_ids and not observed_ids.issubset(subject_ids):
        raise EvidenceIntegrityError("evidence references samples outside the claim subject set")
    if evidence.comparison.sample_count < len(observed_ids):
        raise EvidenceIntegrityError("comparison count is smaller than referenced evidence")
    if pattern is not None and evidence.evidence_id not in pattern.evidence_ids:
        raise EvidenceIntegrityError("pattern does not reference the supplied evidence")


def create_candidate(
    claim: Claim,
    evidence_records: list[EvidenceRecord],
    *,
    provenance: Provenance,
    version: int = 1,
    now: datetime | None = None,
) -> PatternCandidate:
    if not evidence_records:
        raise EvidenceIntegrityError("a Pattern Candidate requires at least one EvidenceRecord")
    if any(record.claim_id != claim.claim_id for record in evidence_records):
        raise EvidenceIntegrityError("all evidence records must reference the same claim")
    for record in evidence_records:
        validate_evidence_chain(claim, record)
    if not any(record.evidence_for for record in evidence_records):
        raise EvidenceIntegrityError("a Pattern Candidate needs supporting evidence")
    support_ids = {sample_id for record in evidence_records for sample_id in record.evidence_for}
    counter_ids = {sample_id for record in evidence_records for sample_id in record.evidence_against}
    control_ids = {sample_id for record in evidence_records for sample_id in record.controls}
    weights = [record.confidence for record in evidence_records]
    effect_sizes = [record.comparison.effect_size for record in evidence_records if record.comparison.effect_size is not None]
    now = now or utc_now()
    return PatternCandidate(
        statement=claim.statement,
        scope=claim.scope,
        evidence_ids=[record.evidence_id for record in evidence_records],
        lifecycle=PatternLifecycle.CANDIDATE,
        metrics=PatternMetrics(
            support_count=len(support_ids),
            counterexample_count=len(counter_ids),
            control_count=len(control_ids),
            confidence=sum(weights) / len(weights),
            effect_size=sum(effect_sizes) / len(effect_sizes) if effect_sizes else None,
        ),
        first_observed_at=min(record.created_at for record in evidence_records),
        last_verified_at=now,
        version=version,
        provenance=provenance,
    )

