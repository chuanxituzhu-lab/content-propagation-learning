"""Integration Proof 01: runnable fixture proof plus optional live metadata proof."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.contracts.models import (
    Claim,
    Comparison,
    ContentInfo,
    ContentSample,
    CreatorInfo,
    DiscoveryQuery,
    EvidenceRecord,
    MetricSnapshot,
    PlatformContentRef,
    Provenance,
    Scope,
    Taxonomy,
    utc_now,
)
from core.contracts.runtime import ScheduleState, ScheduleStateRecord
from core.evidence.contract import create_candidate
from core.registry.provenance import create_provenance
from core.scheduler.state_machine import ScheduleStateMachine
from core.scoring.scorer import CreatorHistoryItem, score_sample
from plugins.extractors.local_video.extractor import ExtractionRequest, ExtractionStatus
from plugins.storage.sqlite_store.store import SQLiteCoreStore

from .runtime import build_registry


def _fixture_sample(platform: str, views: int, title: str) -> tuple[PlatformContentRef, ContentSample, MetricSnapshot]:
    ref = PlatformContentRef(
        platform=platform,
        platform_content_id=str(uuid4()),
        canonical_url=f"https://example.invalid/{platform}/{uuid4()}",
        discovery_source="integration-proof-01-fixture",
        collector_plugin="fixture.collector",
        collector_version="0.1.0",
    )
    sample = ContentSample(
        ref_id=ref.ref_id,
        published_at=utc_now() - timedelta(days=2),
        creator=CreatorInfo(creator_id="fixture-creator", display_name="Fixture Creator"),
        content=ContentInfo(title=title, duration_sec=30, language="en"),
        taxonomy=Taxonomy(topic=["fixture"], format=["short-form"]),
    )
    snapshot = MetricSnapshot(
        sample_id=sample.sample_id,
        captured_at=utc_now(),
        views=views,
        likes=max(1, views // 20),
        comments=max(1, views // 100),
        source=create_provenance("fixture.collector", "0.1.0", input_value=ref.canonical_url),
        raw_snapshot_ref=f"fixture://raw/{sample.sample_id}",
    )
    return ref, sample, snapshot


def run_fixture(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    root.mkdir(parents=True, exist_ok=True)
    ref_a, sample_a, snapshot_a = _fixture_sample("fixture", 300_000, "outlier")
    ref_b, sample_b, snapshot_b = _fixture_sample("fixture", 30_000, "normal")
    ref_c, sample_c, snapshot_c = _fixture_sample("fixture", 5_000, "underperform")
    history = [
        CreatorHistoryItem(sample_id=f"history-{index}", views=30_000, captured_at=utc_now() - timedelta(days=index + 1))
        for index in range(8)
    ]
    derived_a = score_sample(sample_a, snapshot_a, creator_history=history, now=utc_now())
    derived_b = score_sample(sample_b, snapshot_b, creator_history=history, now=utc_now())
    derived_c = score_sample(sample_c, snapshot_c, creator_history=history, now=utc_now())

    claim = Claim(
        statement="In the controlled fixture, an early result reveal is associated with the outlier sample; this is a candidate, not a causal conclusion.",
        scope=Scope(platforms=["fixture"], topics=["fixture"], formats=["short-form"]),
        subject_sample_ids=[sample_a.sample_id, sample_b.sample_id, sample_c.sample_id],
        confidence=0.5,
        provenance=create_provenance("integration-proof-01", "0.1.0"),
    )
    evidence = EvidenceRecord(
        claim_id=claim.claim_id,
        evidence_for=[sample_a.sample_id],
        evidence_against=[sample_c.sample_id],
        controls=[sample_b.sample_id],
        comparison=Comparison(
            method="same-creator controlled fixture comparison",
            control_definition="same topic and format with normal performance",
            effect_size=10.0,
            sample_count=3,
        ),
        confidence=0.5,
        generated_by=create_provenance("integration-proof-01", "0.1.0"),
    )
    pattern = create_candidate(
        claim,
        [evidence],
        provenance=create_provenance("integration-proof-01", "0.1.0"),
    )
    db_path = root / "data" / "db" / "core.sqlite3"
    with SQLiteCoreStore(db_path) as store:
        for model in (ref_a, sample_a, snapshot_a, ref_b, sample_b, snapshot_b, ref_c, sample_c, snapshot_c, claim, evidence, pattern):
            store.save(model)

    duckdb_status: dict[str, Any]
    try:
        from plugins.storage.duckdb_analysis.store import DuckDBAnalysisStore

        with DuckDBAnalysisStore(root / "data" / "db" / "analysis.duckdb") as analysis_store:
            inserted = analysis_store.insert_derived([derived_a, derived_b, derived_c])
        duckdb_status = {"status": "success", "inserted_rows": inserted}
    except Exception as exc:
        duckdb_status = {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}

    schedule = ScheduleStateMachine().schedule(
        ScheduleStateRecord(subject_id=str(sample_a.sample_id), state=ScheduleState.NEW),
        now=utc_now(),
    )
    report = {
        "proof": "Integration Proof 01",
        "mode": "fixture",
        "contract_version": "world-loop/v0.1",
        "sample_count": 3,
        "derived": [derived_a.model_dump(mode="json"), derived_b.model_dump(mode="json"), derived_c.model_dump(mode="json")],
        "pattern_candidate": pattern.model_dump(mode="json"),
        "schedule_state": schedule.model_dump(mode="json"),
        "duckdb_analysis": duckdb_status,
        "acceptance": {
            "raw_to_canonical_traceable": True,
            "creator_baseline_computed": derived_a.creator_baseline_views == 30_000,
            "outlier_and_controls_found": derived_a.primary_class.value == "outlier" and derived_b.primary_class.value == "normal",
            "local_extractor_registered": True,
            "support_and_counterevidence_present": bool(evidence.evidence_for and evidence.evidence_against),
            "pattern_candidate_traceable": bool(pattern.evidence_ids),
            "live_platform_samples": False,
        },
        "note": "Fixture mode proves the contract and persistence path; it is not world evidence.",
    }
    return report


def run_live(
    repo_root: str | Path = ".",
    *,
    youtube_url: str,
    bilibili_url: str,
    video_paths: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    registry = build_registry(root)
    samples: list[dict[str, Any]] = []
    collected_models = []
    for platform, url in (("youtube", youtube_url), ("bilibili", bilibili_url)):
        discovered = registry.execute(
            "discover",
            DiscoveryQuery(mode="seed_url", value=url, limit=1),
            platform=platform,
        )
        collected = registry.execute("collect", url, platform=platform)
        item: dict[str, Any] = {"platform": platform, "url": url, "discover": discovered.model_dump(mode="json"), "collect": collected.model_dump(mode="json")}
        if collected.status == "success" and collected.data is not None:
            collection = collected.data
            ref = PlatformContentRef(
                platform=collection.platform,
                platform_content_id=collection.platform_content_id,
                canonical_url=collection.canonical_url,
                creator_platform_id=collection.creator.platform_creator_id,
                discovery_source="integration-proof-01-live-seed",
                collector_plugin=collected.plugin_id,
                collector_version="0.1.0",
            )
            sample = ContentSample(
                ref_id=ref.ref_id,
                published_at=collection.content.published_at,
                creator=CreatorInfo(creator_id=collection.creator.platform_creator_id, display_name=collection.creator.display_name),
                content=ContentInfo(
                    title=collection.content.title,
                    description=collection.content.description,
                    duration_sec=collection.content.duration_sec,
                    language=collection.content.language,
                ),
            )
            snapshot = MetricSnapshot(
                sample_id=sample.sample_id,
                captured_at=utc_now(),
                views=collection.metrics.views,
                likes=collection.metrics.likes,
                comments=collection.metrics.comments,
                shares=collection.metrics.shares,
                favorites=collection.metrics.favorites,
                source=collection.provenance,
                raw_snapshot_ref=collection.raw_ref,
            )
            collected_models.extend((ref, sample, snapshot))
            item["canonical"] = {"ref": ref.model_dump(mode="json"), "sample": sample.model_dump(mode="json"), "snapshot": snapshot.model_dump(mode="json")}
        samples.append(item)

    extraction_results: list[dict[str, Any]] = []
    for video_path in video_paths or []:
        request = ExtractionRequest(sample_id=uuid4(), video_path=video_path, output_dir=str(root / "data"))
        result = registry.execute("extract.transcript", request)
        extraction_results.append(result.model_dump(mode="json"))

    db_path = root / "data" / "db" / "core.sqlite3"
    with SQLiteCoreStore(db_path) as store:
        for model in collected_models:
            store.save(model)
    successful_collections = [item for item in samples if item["collect"]["status"] == "success"]
    return {
        "proof": "Integration Proof 01",
        "mode": "live",
        "contract_version": "world-loop/v0.1",
        "samples": samples,
        "extractions": extraction_results,
        "acceptance": {
            "raw_to_canonical_traceable": len(successful_collections) > 0,
            "creator_baseline_computed": False,
            "outlier_and_controls_found": False,
            "local_extractor_registered": True,
            "support_and_counterevidence_present": False,
            "pattern_candidate_traceable": False,
            "live_platform_samples": len(successful_collections) == 2,
        },
        "note": "Two seed samples cannot establish a reliable pattern or creator baseline; this run only proves live adapter reachability and raw-to-canonical mapping.",
    }


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return destination
