"""Bilibili adapters: public search discovery plus yt-dlp metadata collection."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from core.contracts.models import DiscoveryMode, DiscoveryQuery, DiscoveryResult, utc_now
from core.contracts.runtime import CostLevel, CostProfile, PluginManifest, PluginRequirements, PluginType, TokenCost
from plugins.platforms.base import (
    AdapterUnavailable,
    CollectorAdapter,
    DiscoveryAdapter,
    discovery_result_from_info,
    map_collection,
)
from plugins.platforms.youtube.adapter import _extract, _entries


BV_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}")


class BilibiliDiscoveryAdapter(DiscoveryAdapter):
    platform = "bilibili"

    def __init__(self, raw_dir: str | Path = "data/raw") -> None:
        self.raw_dir = Path(raw_dir)
        self.manifest = PluginManifest(
            plugin_id="world.bilibili.discovery",
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
            try:
                info = _extract(query.value)
            except Exception as exc:
                raise AdapterUnavailable(f"Bilibili seed collection failed: {exc}") from exc
            raw_ref = self._save_raw(str(info.get("id") or "seed"), info)
            result = discovery_result_from_info(
                platform=self.platform,
                info=info,
                fallback_url=query.value,
                discovery_source="seed_url",
                raw_ref=raw_ref,
            )
            return [result] if result else []

        if query.mode is DiscoveryMode.CREATOR and query.value.isdigit():
            source = f"https://space.bilibili.com/{query.value}/video"
            info = _extract(source, flat=True)
            results: list[DiscoveryResult] = []
            for index, entry in enumerate(_entries(info), start=1):
                raw_ref = self._save_raw(str(entry.get("id") or f"creator-{index}"), entry)
                result = discovery_result_from_info(
                    platform=self.platform,
                    info=entry,
                    fallback_url=entry.get("url"),
                    discovery_source=f"creator:{query.value}",
                    raw_ref=raw_ref,
                )
                if result:
                    results.append(result)
            return results[: query.limit]

        search_url = f"https://search.bilibili.com/all?keyword={quote(query.value)}"
        try:
            request = Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=20) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raise AdapterUnavailable(f"Bilibili public search failed: {exc}") from exc
        raw_ref = self._save_raw(f"search-{quote(query.value)}", {"url": search_url, "html": html})
        results: list[DiscoveryResult] = []
        seen: set[str] = set()
        for content_id in BV_PATTERN.findall(html):
            if content_id in seen:
                continue
            seen.add(content_id)
            results.append(
                DiscoveryResult(
                    platform=self.platform,
                    platform_content_id=content_id,
                    canonical_url=f"https://www.bilibili.com/video/{content_id}",
                    discovery_source=f"{query.mode.value}:{query.value}",
                    discovered_at=utc_now(),
                    raw_ref=raw_ref,
                )
            )
            if len(results) >= query.limit:
                break
        return results


class BilibiliCollectorAdapter(CollectorAdapter):
    platform = "bilibili"

    def __init__(self, raw_dir: str | Path = "data/raw") -> None:
        self.raw_dir = Path(raw_dir)
        self.manifest = PluginManifest(
            plugin_id="world.bilibili.collector",
            type=PluginType.COLLECTOR,
            version="0.1.0",
            capabilities=["collect", "metrics", "media_url"],
            platforms=[self.platform],
            requirements=PluginRequirements(network=True, auth="optional"),
            cost_profile=CostProfile(compute=CostLevel.LOW, token=TokenCost.NONE, network=True),
            priority=10,
        )

    def collect(self, url: str):
        try:
            info = _extract(url)
        except Exception as exc:
            raise AdapterUnavailable(f"Bilibili collection failed: {exc}") from exc
        raw_ref = self._save_raw(str(info.get("id") or "collected"), info)
        return map_collection(
            platform=self.platform,
            info=info,
            canonical_url=url,
            raw_ref=raw_ref,
            manifest=self.manifest,
        )

