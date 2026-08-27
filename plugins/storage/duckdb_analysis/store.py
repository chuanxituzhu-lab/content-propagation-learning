"""DuckDB analysis adapter; optional at runtime, never part of Core imports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from core.contracts.runtime import PluginManifest, PluginType


class DuckDBUnavailable(RuntimeError):
    pass


class DuckDBAnalysisStore:
    def __init__(self, path: str | Path = "data/db/analysis.duckdb") -> None:
        try:
            import duckdb
        except ImportError as exc:
            raise DuckDBUnavailable("duckdb is required for analysis storage; install the analysis extra") from exc
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(self.path))
        self.manifest = PluginManifest(
            plugin_id="world.duckdb.analysis-store",
            type=PluginType.STORAGE,
            version="0.1.0",
            capabilities=["storage.analysis", "analysis.derived"],
            platforms=[],
        )
        self.initialize()

    def initialize(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS derived_metrics (
                sample_id VARCHAR,
                payload_json VARCHAR,
                scoring_version VARCHAR,
                calculated_at TIMESTAMP
            )
            """
        )

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "DuckDBAnalysisStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def insert_derived(self, metrics: Iterable[Any]) -> int:
        rows = []
        for item in metrics:
            payload = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            rows.append(
                (
                    str(payload["sample_id"]),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    payload.get("scoring_version"),
                    payload.get("calculated_at") or datetime.now(timezone.utc),
                )
            )
        if rows:
            self.connection.executemany("INSERT INTO derived_metrics VALUES (?, ?, ?, ?)", rows)
        return len(rows)

    def query(self, sql: str, parameters: Iterable[Any] = ()) -> list[tuple[Any, ...]]:
        return self.connection.execute(sql, list(parameters)).fetchall()
