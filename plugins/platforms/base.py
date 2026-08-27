"""Platform adapter helpers. No platform-specific types cross this boundary."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.contracts.models import (
    CollectionContent,
    CollectionCreator,
    CollectionMedia,
    CollectionMetrics,
    CollectionResult,
    DiscoveryMode,
    DiscoveryQuery,
    DiscoveryResult,
    utc_now,
)
from core.contracts.runtime import PluginManifest
from core.registry.provenance import create_provenance


class AdapterUnavailable(RuntimeError):
    pass


def parse_timestamp(info: dict[str, Any]) -> datetime | None:
    for key in ("timestamp", "release_timestamp", "upload_timestamp"):
        value = info.get(key)
        if value is not None:
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                pass
    date = info.get("upload_date")
    if isinstance(date, str) and re.fullmatch(r"\d{8}", date):
        try:
            return datetime.strptime(date, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


class RawSnapshotMixin:
    platform: str
    raw_dir: Path
    manifest: PluginManifest

    def _save_raw(self, key: str, payload: Any) -> str:
        safe_key = re.sub(r"[^A-Za-z0-9_.-]", "_", key)[:120]
        destination = self.raw_dir / self.platform / f"{safe_key}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str),
            encoding="utf-8",
        )
        return str(destination)


class DiscoveryAdapter(RawSnapshotMixin, ABC):
    @abstractmethod
    def discover(self, query: DiscoveryQuery) -> list[DiscoveryResult]:
        raise NotImplementedError

    def execute(self, request: DiscoveryQuery) -> list[DiscoveryResult]:
        return self.discover(request)


class CollectorAdapter(RawSnapshotMixin, ABC):
    @abstractmethod
    def collect(self, url: str) -> CollectionResult:
        raise NotImplementedError

    def execute(self, request: str | DiscoveryResult) -> CollectionResult:
        url = request.canonical_url if isinstance(request, DiscoveryResult) else request
        return self.collect(url)


def map_collection(
    *,
    platform: str,
    info: dict[str, Any],
    canonical_url: str,
    raw_ref: str,
    manifest: PluginManifest,
) -> CollectionResult:
    """Map extractor-neutral info into the frozen canonical collection contract."""

    platform_content_id = str(info.get("id") or info.get("display_id") or canonical_url)
    creator_id = info.get("channel_id") or info.get("uploader_id")
    title = info.get("title")
    description = info.get("description")
    def first_present(*keys: str) -> Any:
        for key in keys:
            if info.get(key) is not None:
                return info[key]
        return None

    return CollectionResult(
        platform=platform,
        platform_content_id=platform_content_id,
        canonical_url=str(info.get("webpage_url") or canonical_url),
        creator=CollectionCreator(
            platform_creator_id=str(creator_id) if creator_id is not None else None,
            display_name=info.get("channel") or info.get("uploader") or info.get("creator"),
            followers=first_present("channel_follower_count", "follower_count"),
        ),
        content=CollectionContent(
            title=title,
            description=description,
            published_at=parse_timestamp(info),
            duration_sec=info.get("duration"),
            language=info.get("language") or info.get("lang"),
        ),
        metrics=CollectionMetrics(
            views=first_present("view_count", "play_count"),
            likes=first_present("like_count", "likes"),
            comments=first_present("comment_count", "comments"),
            shares=first_present("share_count", "shares"),
            favorites=first_present("favorite_count", "favorites"),
        ),
        media=CollectionMedia(
            video_url=info.get("url"),
            thumbnail_url=info.get("thumbnail"),
        ),
        raw_ref=raw_ref,
        provenance=create_provenance(
            manifest.plugin_id,
            manifest.version,
            input_value=canonical_url,
            output_value=info,
            contract_version=manifest.contract_version,
        ),
    )


def discovery_result_from_info(
    *,
    platform: str,
    info: dict[str, Any],
    fallback_url: str | None,
    discovery_source: str,
    raw_ref: str | None,
) -> DiscoveryResult | None:
    content_id = info.get("id") or info.get("display_id")
    url = info.get("webpage_url") or info.get("original_url") or fallback_url
    if not content_id or not url:
        return None
    return DiscoveryResult(
        platform=platform,
        platform_content_id=str(content_id),
        canonical_url=str(url),
        creator_platform_id=(str(info["channel_id"]) if info.get("channel_id") is not None else None),
        published_at=parse_timestamp(info),
        discovery_source=discovery_source,
        discovered_at=utc_now(),
        hints={
            key: info[key]
            for key in ("view_count", "play_count", "rank", "trend_score")
            if info.get(key) is not None
        },
        raw_ref=raw_ref,
    )
