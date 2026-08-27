"""Storage adapter contract used by local implementations."""

from __future__ import annotations

from typing import Any, Protocol


class StorageAdapter(Protocol):
    def save(self, model: Any) -> str:
        ...

    def get(self, entity_type: str, entity_id: str) -> Any | None:
        ...

    def query(self, entity_type: str, *, limit: int = 100) -> list[Any]:
        ...

