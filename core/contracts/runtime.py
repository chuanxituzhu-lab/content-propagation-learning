"""Runtime and governance contracts kept outside the knowledge model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from .models import CONTRACT_VERSION, ContractModel, FrozenContractModel, Provenance, utc_now


class PluginType(StrEnum):
    DISCOVERY = "discovery"
    COLLECTOR = "collector"
    EXTRACTOR = "extractor"
    ANALYZER = "analyzer"
    STORAGE = "storage"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class CostLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TokenCost(StrEnum):
    NONE = "none"
    LOW = "low"
    HIGH = "high"


class CostProfile(FrozenContractModel):
    compute: CostLevel = CostLevel.LOW
    token: TokenCost = TokenCost.NONE
    network: bool = False


class PluginRequirements(FrozenContractModel):
    network: bool = False
    auth: str = "none"


class PluginManifest(FrozenContractModel):
    plugin_id: str = Field(min_length=1)
    type: PluginType
    version: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    platforms: list[str] = Field(default_factory=list)
    requirements: PluginRequirements = Field(default_factory=PluginRequirements)
    cost_profile: CostProfile = Field(default_factory=CostProfile)
    contract_version: str = CONTRACT_VERSION
    priority: int = 0


class ScheduleState(StrEnum):
    NEW = "NEW"
    WATCHING = "WATCHING"
    RISING = "RISING"
    STABLE = "STABLE"
    EVERGREEN = "EVERGREEN"
    ARCHIVED = "ARCHIVED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class ScheduleStateRecord(FrozenContractModel):
    schedule_id: UUID = Field(default_factory=uuid4)
    subject_id: str = Field(min_length=1)
    state: ScheduleState = ScheduleState.NEW
    next_action_at: datetime | None = None
    priority: int = 0
    updated_at: datetime = Field(default_factory=utc_now)
    reason: str | None = None


class EvolutionAction(StrEnum):
    HOLD = "hold"
    ADD = "add"
    MERGE = "merge"
    SUPERSEDE = "supersede"
    DISCARD = "discard"


class EvolutionDecision(FrozenContractModel):
    decision_id: UUID = Field(default_factory=uuid4)
    target_id: UUID
    action: EvolutionAction
    from_status: str
    to_status: str | None = None
    rationale: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(default_factory=list)
    decided_at: datetime = Field(default_factory=utc_now)
    decision_by: str = "rule-engine"
    provenance: Provenance

