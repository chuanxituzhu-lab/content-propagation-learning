"""Frozen v0.1 domain contracts.

Raw objects are immutable at the model boundary. Derived and knowledge objects
are versioned and must be replaced with a new record rather than mutating raw
facts in place.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CONTRACT_VERSION = "world-loop/v0.1"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=False)


class FrozenContractModel(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=False)


class SampleClass(StrEnum):
    MEGA_VIRAL = "mega_viral"
    OUTLIER = "outlier"
    RISING = "rising"
    EVERGREEN = "evergreen"
    NORMAL = "normal"
    UNDERPERFORM = "underperform"
    UNKNOWN = "unknown"


class PatternLifecycle(StrEnum):
    HYPOTHESIS = "hypothesis"
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    TESTED = "tested"
    VALIDATED = "validated"
    CANARY = "canary"
    PROMOTED = "promoted"
    DEPRECATED = "deprecated"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class EvidenceStatus(StrEnum):
    HYPOTHESIS = "hypothesis"
    OBSERVED = "observed"
    TESTED = "tested"
    VALIDATED = "validated"
    REJECTED = "rejected"


class ArtifactType(StrEnum):
    METADATA_RAW = "metadata_raw"
    VIDEO = "video"
    AUDIO = "audio"
    TRANSCRIPT = "transcript"
    KEYFRAMES = "keyframes"
    SCENE_MAP = "scene_map"
    OCR = "ocr"
    THUMBNAIL = "thumbnail"
    LOCAL_FEATURES = "local_features"


class Provenance(FrozenContractModel):
    plugin_id: str
    plugin_version: str
    contract_version: str = CONTRACT_VERSION
    executed_at: datetime = Field(default_factory=utc_now)
    input_hash: str | None = None
    output_hash: str | None = None


class PlatformContentRef(FrozenContractModel):
    """Identity and discovery provenance; platform fields stay generic."""

    ref_id: UUID = Field(default_factory=uuid4)
    platform: str = Field(min_length=1)
    platform_content_id: str = Field(min_length=1)
    canonical_url: str
    creator_platform_id: str | None = None
    discovered_at: datetime = Field(default_factory=utc_now)
    discovery_source: str = Field(min_length=1)
    collector_plugin: str = Field(min_length=1)
    collector_version: str = Field(min_length=1)


class CreatorInfo(ContractModel):
    creator_id: str | None = None
    display_name: str | None = None


class ContentInfo(ContractModel):
    title: str | None = None
    description: str | None = None
    duration_sec: float | None = Field(default=None, ge=0)
    language: str | None = None


class Taxonomy(ContractModel):
    topic: list[str] = Field(default_factory=list)
    format: list[str] = Field(default_factory=list)
    mechanism: list[str] = Field(default_factory=list)


class SampleState(ContractModel):
    primary_class: SampleClass = SampleClass.UNKNOWN
    signals: list[str] = Field(default_factory=list)
    classified_at: datetime | None = None
    classifier_version: str | None = None


class ContentSample(ContractModel):
    sample_id: UUID = Field(default_factory=uuid4)
    ref_id: UUID
    published_at: datetime | None = None
    creator: CreatorInfo = Field(default_factory=CreatorInfo)
    content: ContentInfo = Field(default_factory=ContentInfo)
    taxonomy: Taxonomy = Field(default_factory=Taxonomy)
    sample_state: SampleState = Field(default_factory=SampleState)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MetricSnapshot(FrozenContractModel):
    snapshot_id: UUID = Field(default_factory=uuid4)
    sample_id: UUID
    captured_at: datetime = Field(default_factory=utc_now)
    content_age_sec: int | None = Field(default=None, ge=0)
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    favorites: int | None = Field(default=None, ge=0)
    creator_followers: int | None = Field(default=None, ge=0)
    source: Provenance
    raw_snapshot_ref: str = Field(min_length=1)


class MediaArtifact(FrozenContractModel):
    artifact_id: UUID = Field(default_factory=uuid4)
    sample_id: UUID
    type: ArtifactType
    storage_uri: str = Field(min_length=1)
    sha256: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    producer: Provenance
    created_at: datetime = Field(default_factory=utc_now)


class AnalyzerInfo(FrozenContractModel):
    name: str
    version: str
    model: str | None = None


class ObservedFeatures(FrozenContractModel):
    hook_start_sec: float | None = Field(default=None, ge=0)
    hook_end_sec: float | None = Field(default=None, ge=0)
    scene_count: int | None = Field(default=None, ge=0)
    avg_shot_length_sec: float | None = Field(default=None, ge=0)
    speech_rate: float | None = Field(default=None, ge=0)
    text_density: float | None = Field(default=None, ge=0)
    audio_peak_count: int | None = Field(default=None, ge=0)


class SemanticFeatures(FrozenContractModel):
    hook_type: list[str] | None = None
    narrative_beats: list[dict[str, Any]] | None = None
    emotions: list[str] | None = None
    tension: dict[str, Any] | None = None
    reward: dict[str, Any] | None = None
    visual_strategy: list[str] | None = None
    audio_strategy: list[str] | None = None


class ContentAnalysis(FrozenContractModel):
    analysis_id: UUID = Field(default_factory=uuid4)
    sample_id: UUID
    analyzer: AnalyzerInfo
    observed: ObservedFeatures = Field(default_factory=ObservedFeatures)
    semantic: SemanticFeatures = Field(default_factory=SemanticFeatures)
    confidence: float | None = Field(default=None, ge=0, le=1)
    artifact_refs: list[UUID] = Field(default_factory=list)
    provenance: Provenance
    created_at: datetime = Field(default_factory=utc_now)


class Scope(FrozenContractModel):
    platforms: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)


class Claim(FrozenContractModel):
    claim_id: UUID = Field(default_factory=uuid4)
    statement: str = Field(min_length=1)
    scope: Scope = Field(default_factory=Scope)
    subject_sample_ids: list[UUID] = Field(default_factory=list)
    status: EvidenceStatus = EvidenceStatus.HYPOTHESIS
    confidence: float = Field(default=0, ge=0, le=1)
    provenance: Provenance
    created_at: datetime = Field(default_factory=utc_now)


class Comparison(FrozenContractModel):
    method: str = Field(min_length=1)
    control_definition: str | None = None
    effect_size: float | None = None
    sample_count: int = Field(ge=0)


class EvidenceRecord(FrozenContractModel):
    evidence_id: UUID = Field(default_factory=uuid4)
    claim_id: UUID
    evidence_for: list[UUID] = Field(default_factory=list)
    evidence_against: list[UUID] = Field(default_factory=list)
    controls: list[UUID] = Field(default_factory=list)
    comparison: Comparison
    confidence: float = Field(ge=0, le=1)
    status: EvidenceStatus = EvidenceStatus.OBSERVED
    generated_by: Provenance
    created_at: datetime = Field(default_factory=utc_now)
    last_verified_at: datetime | None = None

    @model_validator(mode="after")
    def has_comparison_material(self) -> "EvidenceRecord":
        if self.comparison.sample_count < len(self.evidence_for) + len(self.evidence_against):
            raise ValueError("comparison.sample_count cannot be below support plus counterexample count")
        return self


class PatternMetrics(FrozenContractModel):
    support_count: int = Field(ge=0)
    counterexample_count: int = Field(ge=0)
    control_count: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    effect_size: float | None = None


class PatternCandidate(FrozenContractModel):
    pattern_id: UUID = Field(default_factory=uuid4)
    statement: str = Field(min_length=1)
    scope: Scope = Field(default_factory=Scope)
    evidence_ids: list[UUID] = Field(min_length=1)
    lifecycle: PatternLifecycle = PatternLifecycle.CANDIDATE
    metrics: PatternMetrics
    first_observed_at: datetime = Field(default_factory=utc_now)
    last_verified_at: datetime = Field(default_factory=utc_now)
    version: int = Field(default=1, ge=1)
    provenance: Provenance

    @field_validator("lifecycle")
    @classmethod
    def mvp_creation_stops_at_candidate(cls, value: PatternLifecycle) -> PatternLifecycle:
        return value


class DiscoveryMode(StrEnum):
    KEYWORD = "keyword"
    CREATOR = "creator"
    SEED_URL = "seed_url"


class DiscoveryQuery(ContractModel):
    mode: DiscoveryMode
    value: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=200)
    cursor: str | None = None


class DiscoveryResult(FrozenContractModel):
    platform: str
    platform_content_id: str
    canonical_url: str
    creator_platform_id: str | None = None
    published_at: datetime | None = None
    discovery_source: str
    discovered_at: datetime = Field(default_factory=utc_now)
    hints: dict[str, Any] = Field(default_factory=dict)
    raw_ref: str | None = None


class CollectionMetrics(FrozenContractModel):
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    favorites: int | None = Field(default=None, ge=0)


class CollectionCreator(FrozenContractModel):
    platform_creator_id: str | None = None
    display_name: str | None = None
    followers: int | None = Field(default=None, ge=0)


class CollectionContent(FrozenContractModel):
    title: str | None = None
    description: str | None = None
    published_at: datetime | None = None
    duration_sec: float | None = Field(default=None, ge=0)
    language: str | None = None


class CollectionMedia(FrozenContractModel):
    video_url: str | None = None
    thumbnail_url: str | None = None


class CollectionResult(FrozenContractModel):
    platform: str
    platform_content_id: str
    canonical_url: str
    creator: CollectionCreator = Field(default_factory=CollectionCreator)
    content: CollectionContent = Field(default_factory=CollectionContent)
    metrics: CollectionMetrics = Field(default_factory=CollectionMetrics)
    media: CollectionMedia = Field(default_factory=CollectionMedia)
    raw_ref: str = Field(min_length=1)
    provenance: Provenance

