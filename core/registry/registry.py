"""Small capability-based registry with per-plugin health isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import Field

from core.contracts.models import ContractModel, FrozenContractModel, Provenance
from core.contracts.runtime import HealthStatus, PluginManifest

from .provenance import create_provenance


class ExecutablePlugin(Protocol):
    manifest: PluginManifest

    def execute(self, request: Any) -> Any:
        ...


class PluginExecutionResult(ContractModel):
    status: str
    plugin_id: str
    data: Any = None
    error: str | None = None
    provenance: Provenance | None = None


class PluginHealthRecord(FrozenContractModel):
    plugin_id: str
    status: HealthStatus = HealthStatus.HEALTHY
    failure_count: int = Field(default=0, ge=0)
    last_error: str | None = None


@dataclass(frozen=True)
class RoutedPlugin:
    plugin: ExecutablePlugin
    health: PluginHealthRecord


class PluginRegistry:
    """Routes only by declared capability and optional generic platform name."""

    def __init__(self, *, unavailable_after: int = 3) -> None:
        self._plugins: dict[str, ExecutablePlugin] = {}
        self._health: dict[str, PluginHealthRecord] = {}
        self._unavailable_after = unavailable_after

    def register(self, plugin: ExecutablePlugin) -> None:
        plugin_id = plugin.manifest.plugin_id
        if plugin_id in self._plugins:
            raise ValueError(f"plugin already registered: {plugin_id}")
        self._plugins[plugin_id] = plugin
        self._health[plugin_id] = PluginHealthRecord(plugin_id=plugin_id)

    def unregister(self, plugin_id: str) -> None:
        self._plugins.pop(plugin_id, None)
        self._health.pop(plugin_id, None)

    def manifests(self) -> list[PluginManifest]:
        return [plugin.manifest for plugin in self._plugins.values()]

    def health(self, plugin_id: str) -> PluginHealthRecord:
        try:
            return self._health[plugin_id]
        except KeyError as exc:
            raise KeyError(f"unknown plugin: {plugin_id}") from exc

    def find(self, capability: str, platform: str | None = None) -> list[RoutedPlugin]:
        candidates: list[RoutedPlugin] = []
        for plugin in self._plugins.values():
            manifest = plugin.manifest
            if capability not in manifest.capabilities:
                continue
            if platform and manifest.platforms and platform not in manifest.platforms:
                continue
            health = self._health[manifest.plugin_id]
            if health.status is HealthStatus.UNAVAILABLE:
                continue
            candidates.append(RoutedPlugin(plugin, health))
        return sorted(
            candidates,
            key=lambda item: (
                item.health.status is HealthStatus.HEALTHY,
                item.plugin.manifest.priority,
            ),
            reverse=True,
        )

    def route(self, capability: str, platform: str | None = None) -> ExecutablePlugin:
        candidates = self.find(capability, platform)
        if not candidates:
            raise LookupError(f"no healthy provider for capability={capability!r}, platform={platform!r}")
        return candidates[0].plugin

    def execute(
        self,
        capability: str,
        request: Any,
        *,
        platform: str | None = None,
    ) -> PluginExecutionResult:
        plugin = self.route(capability, platform)
        manifest = plugin.manifest
        try:
            data = plugin.execute(request)
            self._health[manifest.plugin_id] = PluginHealthRecord(plugin_id=manifest.plugin_id)
            return PluginExecutionResult(
                status="success",
                plugin_id=manifest.plugin_id,
                data=data,
                provenance=create_provenance(
                    manifest.plugin_id,
                    manifest.version,
                    input_value=request,
                    output_value=data,
                    contract_version=manifest.contract_version,
                ),
            )
        except Exception as exc:  # plugin failures must not escape into other providers
            previous = self._health[manifest.plugin_id]
            failure_count = previous.failure_count + 1
            status = (
                HealthStatus.UNAVAILABLE
                if failure_count >= self._unavailable_after
                else HealthStatus.DEGRADED
            )
            self._health[manifest.plugin_id] = PluginHealthRecord(
                plugin_id=manifest.plugin_id,
                status=status,
                failure_count=failure_count,
                last_error=f"{type(exc).__name__}: {exc}",
            )
            return PluginExecutionResult(
                status="failed",
                plugin_id=manifest.plugin_id,
                error=f"{type(exc).__name__}: {exc}",
            )

