"""Append-only SQLite Core Store; large media remains on the filesystem."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID, uuid4

from core.contracts.models import (
    Claim,
    ContentAnalysis,
    ContentSample,
    EvidenceRecord,
    MediaArtifact,
    MetricSnapshot,
    PatternCandidate,
    PlatformContentRef,
)
from core.contracts.runtime import PluginManifest, PluginType
from core.registry.provenance import create_provenance, sha256_payload


MODEL_TYPES = {
    cls.__name__: cls
    for cls in (
        PlatformContentRef,
        ContentSample,
        MetricSnapshot,
        MediaArtifact,
        ContentAnalysis,
        Claim,
        EvidenceRecord,
        PatternCandidate,
    )
}


class SQLiteCoreStore:
    """Core storage with insert-only entity and raw snapshot operations."""

    def __init__(self, path: str | Path = "data/db/core.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.manifest = PluginManifest(
            plugin_id="world.sqlite.core-store",
            type=PluginType.STORAGE,
            version="0.1.0",
            capabilities=["storage.core", "storage.raw", "storage.snapshot"],
            platforms=[],
        )
        self.initialize()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS entities (
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (entity_type, entity_id)
            );
            CREATE TABLE IF NOT EXISTS raw_snapshots (
                raw_snapshot_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                storage_uri TEXT,
                payload_json TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
            CREATE INDEX IF NOT EXISTS idx_snapshots_platform_time ON raw_snapshots(platform, captured_at);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteCoreStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def save(self, model: Any) -> str:
        entity_type = type(model).__name__
        if entity_type not in MODEL_TYPES:
            raise TypeError(f"unsupported core entity: {entity_type}")
        payload = model.model_dump(mode="json")
        identity_fields = {
            "PlatformContentRef": "ref_id",
            "ContentSample": "sample_id",
            "MetricSnapshot": "snapshot_id",
            "MediaArtifact": "artifact_id",
            "ContentAnalysis": "analysis_id",
            "Claim": "claim_id",
            "EvidenceRecord": "evidence_id",
            "PatternCandidate": "pattern_id",
        }
        entity_id = str(getattr(model, identity_fields[entity_type], None))
        if entity_id == "None":
            raise ValueError(f"{entity_type} has no recognized identity")
        created_at = _json_datetime(getattr(model, "created_at", datetime.now(timezone.utc)))
        try:
            self.connection.execute(
                "INSERT INTO entities(entity_type, entity_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (entity_type, entity_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), created_at),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"immutable entity already exists: {entity_type}/{entity_id}") from exc
        return entity_id

    def get(self, entity_type: str, entity_id: str | UUID) -> Any | None:
        row = self.connection.execute(
            "SELECT payload_json FROM entities WHERE entity_type = ? AND entity_id = ?",
            (entity_type, str(entity_id)),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        model_type = MODEL_TYPES.get(entity_type)
        return model_type.model_validate(payload) if model_type else payload

    def query(self, entity_type: str, *, limit: int = 100) -> list[Any]:
        rows = self.connection.execute(
            "SELECT payload_json FROM entities WHERE entity_type = ? ORDER BY created_at LIMIT ?",
            (entity_type, limit),
        ).fetchall()
        model_type = MODEL_TYPES.get(entity_type)
        return [model_type.model_validate(json.loads(row["payload_json"])) if model_type else json.loads(row["payload_json"]) for row in rows]

    def append_snapshot(self, snapshot: MetricSnapshot, *, platform: str, storage_uri: str | None = None) -> str:
        payload = snapshot.model_dump(mode="json")
        raw_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            "INSERT INTO raw_snapshots(raw_snapshot_id, platform, captured_at, storage_uri, payload_json, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                raw_id,
                platform,
                snapshot.captured_at.isoformat(),
                storage_uri,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                sha256_payload(payload),
                now,
            ),
        )
        self.connection.commit()
        return raw_id

    def append_raw_snapshot(
        self,
        *,
        platform: str,
        payload: Any,
        captured_at: datetime | None = None,
        storage_uri: str | None = None,
    ) -> str:
        raw_id = str(uuid4())
        captured_at = captured_at or datetime.now(timezone.utc)
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            "INSERT INTO raw_snapshots(raw_snapshot_id, platform, captured_at, storage_uri, payload_json, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                raw_id,
                platform,
                captured_at.isoformat(),
                storage_uri,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                sha256_payload(payload),
                now,
            ),
        )
        self.connection.commit()
        return raw_id

    def raw_snapshots(self, *, platform: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if platform:
            rows = self.connection.execute(
                "SELECT * FROM raw_snapshots WHERE platform = ? ORDER BY captured_at LIMIT ?",
                (platform, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM raw_snapshots ORDER BY captured_at LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def store_artifact_ref(self, artifact: MediaArtifact) -> str:
        return self.save(artifact)


def _json_datetime(value: datetime) -> str:
    return value.isoformat() if value.tzinfo else value.replace(tzinfo=timezone.utc).isoformat()
