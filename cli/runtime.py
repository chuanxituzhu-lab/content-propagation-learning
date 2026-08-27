from __future__ import annotations

from pathlib import Path

from core.registry.registry import PluginRegistry
from plugins.extractors.local_video.extractor import LocalVideoExtractor
from plugins.platforms.bilibili.adapter import BilibiliCollectorAdapter, BilibiliDiscoveryAdapter
from plugins.platforms.youtube.adapter import YouTubeCollectorAdapter, YouTubeDiscoveryAdapter


def build_registry(repo_root: str | Path = ".") -> PluginRegistry:
    root = Path(repo_root)
    raw_dir = root / "data" / "raw"
    registry = PluginRegistry()
    for plugin in (
        YouTubeDiscoveryAdapter(raw_dir),
        YouTubeCollectorAdapter(raw_dir),
        BilibiliDiscoveryAdapter(raw_dir),
        BilibiliCollectorAdapter(raw_dir),
        LocalVideoExtractor(default_output_dir=root / "data"),
    ):
        registry.register(plugin)
    return registry

