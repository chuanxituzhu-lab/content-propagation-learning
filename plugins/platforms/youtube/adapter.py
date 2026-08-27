"""YouTube adapters backed by the optional yt-dlp library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.contracts.models import DiscoveryMode, DiscoveryQuery, DiscoveryResult
from core.contracts.runtime import CostLevel, CostProfile, PluginManifest, PluginRequirements, PluginType, TokenCost
from plugins.platforms.base import (
    AdapterUnavailable,
    CollectorAdapter,
    DiscoveryAdapter,
    discovery_result_from_info,
    map_collection,
)


def _yt_dlp():
    try:
        import yt_dlp

        return yt_dlp
    except ImportError as exc:
        raise AdapterUnavailable("yt-dlp is required for live YouTube/Bilibili collection") from exc


def _extract(url_or_query: str, *, flat: bool = False) -> dict[str, Any]:
    yt_dlp = _yt_dlp()
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": not flat,
        "extract_flat": flat,
        "ignoreerrors": False,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url_or_query, download=False)
    if not isinstance(info, dict):
        raise AdapterUnavailable("yt-dlp returned no metadata")
    return info


def _entries(info: dict[str, Any]) -> list[dict[str, Any]]:
    entries = info.get("entries")
    if entries is None:
        return [info]
    return [entry for entry in entries if isinstance(entry, dict)]


class YouTubeDiscoveryAdapter(DiscoveryAdapter):
    platform = "youtube"

    def __init__(self, raw_dir: str | Path = "data/raw") -> None:
        self.raw_dir = Path(raw_dir)
        self.manifest = PluginManifest(
            plugin_id="world.youtube.discovery",
            type=PluginType.DISCOVERY,
            version="0.1.0",
            capabilities=["discover", "metadata"],
            platforms=[self.platform],
            requirements=PluginRequirements(network=True, auth="optional"),
            cost_profile=CostProfile(compute=CostLevel.LOW, token=TokenCost.NONE, network=True),
            priority=10,
        )

    def discover(self, query: DiscoveryQuery) -> list[DiscoveryResult]:
        if query.mode is DiscoveryMode.SEED_URL:
            info = _extract(query.value)
            raw_ref = self._save_raw(str(info.get("id") or "seed"), info)
            result = discovery_result_from_info(
                platform=self.platform,
                info=info,
                fallback_url=query.value,
                discovery_source="seed_url",
                raw_ref=raw_ref,
            )
            return [result] if result else []

        search = f"ytsearch{query.limit}:{query.value}"
        info = _extract(search, flat=True)
        results: list[DiscoveryResult] = []
        for index, entry in enumerate(_entries(info), start=1):
            raw_ref = self._save_raw(str(entry.get("id") or f"search-{index}"), entry)
            fallback = f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get("id") else None
            result = discovery_result_from_info(
                platform=self.platform,
                info=entry,
                fallback_url=fallback,
                discovery_source=f"{query.mode.value}:{query.value}",
                raw_ref=raw_ref,
            )
            if result:
                results.append(result)
        return results[: query.limit]


class YouTubeCollectorAdapter(CollectorAdapter):
    platform = "youtube"

    def __init__(self, raw_dir: str | Path = "data/raw") -> None:
        self.raw_dir = Path(raw_dir)
        self.manifest = PluginManifest(
            plugin_id="world.youtube.collector",
            type=PluginType.COLLECTOR,
            version="0.1.0",
            capabilities=["collect", "metrics", "media_url"],
            platforms=[self.platform],
            requirements=PluginRequirements(network=True, auth="optional"),
            cost_profile=CostProfile(compute=CostLevel.LOW, token=TokenCost.NONE, network=True),
            priority=10,
        )

    def collect(self, url: str):
        info = _extract(url)
        raw_ref = self._save_raw(str(info.get("id") or "collected"), info)
        return map_collection(
            platform=self.platform,
            info=info,
            canonical_url=url,
            raw_ref=raw_ref,
            manifest=self.manifest,
        )

