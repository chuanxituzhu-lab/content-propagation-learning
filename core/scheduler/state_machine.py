"""A deliberately small, deterministic scheduler state machine."""

from __future__ import annotations

from datetime import datetime, timedelta

from core.contracts.models import utc_now
from core.contracts.runtime import ScheduleState, ScheduleStateRecord


class InvalidScheduleTransition(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[ScheduleState, set[ScheduleState]] = {
    ScheduleState.NEW: {ScheduleState.WATCHING, ScheduleState.DEGRADED, ScheduleState.FAILED},
    ScheduleState.WATCHING: {
        ScheduleState.RISING,
        ScheduleState.STABLE,
        ScheduleState.DEGRADED,
        ScheduleState.FAILED,
    },
    ScheduleState.RISING: {
        ScheduleState.STABLE,
        ScheduleState.EVERGREEN,
        ScheduleState.DEGRADED,
        ScheduleState.FAILED,
    },
    ScheduleState.STABLE: {ScheduleState.EVERGREEN, ScheduleState.ARCHIVED, ScheduleState.DEGRADED, ScheduleState.FAILED},
    ScheduleState.EVERGREEN: {ScheduleState.ARCHIVED, ScheduleState.DEGRADED, ScheduleState.FAILED},
    ScheduleState.ARCHIVED: set(),
    ScheduleState.DEGRADED: {ScheduleState.WATCHING, ScheduleState.FAILED},
    ScheduleState.FAILED: {ScheduleState.WATCHING},
}


INTERVALS = {
    ScheduleState.NEW: timedelta(hours=6),
    ScheduleState.WATCHING: timedelta(hours=6),
    ScheduleState.RISING: timedelta(hours=1),
    ScheduleState.STABLE: timedelta(hours=24),
    ScheduleState.EVERGREEN: timedelta(hours=72),
    ScheduleState.DEGRADED: timedelta(hours=12),
}


class ScheduleStateMachine:
    def transition(
        self,
        record: ScheduleStateRecord,
        target: ScheduleState,
        *,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> ScheduleStateRecord:
        if target not in ALLOWED_TRANSITIONS[record.state]:
            raise InvalidScheduleTransition(f"{record.state} -> {target} is not allowed")
        now = now or utc_now()
        return ScheduleStateRecord(
            schedule_id=record.schedule_id,
            subject_id=record.subject_id,
            state=target,
            next_action_at=self._next_action(target, now),
            priority=record.priority,
            updated_at=now,
            reason=reason,
        )

    def schedule(self, record: ScheduleStateRecord, *, now: datetime | None = None) -> ScheduleStateRecord:
        now = now or utc_now()
        return ScheduleStateRecord(
            schedule_id=record.schedule_id,
            subject_id=record.subject_id,
            state=record.state,
            next_action_at=self._next_action(record.state, now),
            priority=record.priority,
            updated_at=now,
            reason=record.reason,
        )

    def due(self, record: ScheduleStateRecord, *, now: datetime | None = None) -> bool:
        if record.next_action_at is None:
            return False
        now = now or utc_now()
        return now >= record.next_action_at

    @staticmethod
    def _next_action(state: ScheduleState, now: datetime) -> datetime | None:
        interval = INTERVALS.get(state)
        return None if interval is None else now + interval

