from __future__ import annotations

import unittest
from datetime import timedelta

from core.contracts.models import utc_now
from core.contracts.runtime import PluginManifest, PluginType, ScheduleState, ScheduleStateRecord
from core.registry.registry import PluginRegistry
from core.scheduler.state_machine import InvalidScheduleTransition, ScheduleStateMachine


class GoodPlugin:
    manifest = PluginManifest(
        plugin_id="test.good",
        type=PluginType.DISCOVERY,
        version="0.1",
        capabilities=["discover"],
        platforms=["good-platform"],
    )

    def execute(self, request):
        return {"ok": request}


class BadPlugin:
    manifest = PluginManifest(
        plugin_id="test.bad",
        type=PluginType.DISCOVERY,
        version="0.1",
        capabilities=["discover"],
        platforms=["bad-platform"],
    )

    def execute(self, request):
        raise RuntimeError("only this plugin is broken")


class RegistrySchedulerTests(unittest.TestCase):
    def test_plugin_failure_is_isolated_by_platform(self):
        registry = PluginRegistry(unavailable_after=2)
        registry.register(GoodPlugin())
        registry.register(BadPlugin())
        failed = registry.execute("discover", "x", platform="bad-platform")
        self.assertEqual(failed.status, "failed")
        good = registry.execute("discover", "x", platform="good-platform")
        self.assertEqual(good.status, "success")
        self.assertEqual(good.data, {"ok": "x"})

    def test_scheduler_adapts_interval_and_rejects_backwards_jump(self):
        machine = ScheduleStateMachine()
        now = utc_now()
        record = ScheduleStateRecord(subject_id="s", state=ScheduleState.NEW)
        watching = machine.transition(record, ScheduleState.WATCHING, now=now)
        rising = machine.transition(watching, ScheduleState.RISING, now=now)
        self.assertEqual(rising.next_action_at - now, timedelta(hours=1))
        with self.assertRaises(InvalidScheduleTransition):
            machine.transition(rising, ScheduleState.NEW, now=now)


if __name__ == "__main__":
    unittest.main()

