"""Hashing and provenance helpers shared by plugins and stores."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.contracts.models import CONTRACT_VERSION, Provenance, utc_now


def canonical_json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def create_provenance(
    plugin_id: str,
    plugin_version: str,
    *,
    input_value: Any = None,
    output_value: Any = None,
    contract_version: str = CONTRACT_VERSION,
) -> Provenance:
    return Provenance(
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        contract_version=contract_version,
        executed_at=utc_now(),
        input_hash=sha256_payload(input_value) if input_value is not None else None,
        output_hash=sha256_payload(output_value) if output_value is not None else None,
    )

