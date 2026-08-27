"""Deterministic Sample Scoring v0.1.

There is deliberately no composite viral score. Reach, creator-relative
performance, velocity, age, and engagement remain separately inspectable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable

from pydantic import Field

from core.contracts.models import (
    ContentSample,
    FrozenContractModel,
    MetricSnapshot,
    SampleClass,
    utc_now,
)


SCORING_VERSION = "world-loop/scoring-v0.1"


class ScoringConfig(FrozenContractModel):
    creator_window_size: int = Field(default=20, ge=1)
    minimum_baseline_samples: int = Field(default=8, ge=1)
    outlier_ratio: float = Field(default=3.0, gt=1)
    strong_outlier_ratio: float = Field(default=5.0, gt=3)
    extreme_outlier_ratio: float = Field(default=10.0, gt=5)
    underperform_ratio: float = Field(default=0.5, gt=0, lt=1)
    normal_upper_ratio: float = Field(default=2.0, gt=1)
    underperform_min_age_hours: float = Field(default=24.0, ge=0)
    rising_max_age_hours: float = Field(default=48.0, ge=0)
    rising_relative_velocity: float = Field(default=2.5, gt=0)
    rising_velocity_percentile: float = Field(default=0.90, ge=0, le=1)
    evergreen_min_age_days: float = Field(default=30.0, ge=0)
    evergreen_recent_7d_threshold: int | None = Field(default=None, ge=0)


class CreatorHistoryItem(FrozenContractModel):
    sample_id: str
    views: int | None = Field(default=None, ge=0)
    captured_at: datetime


class SampleDerivedMetrics(FrozenContractModel):
    sample_id: str
    age_hours: float | None = None
    creator_baseline_views: float | None = None
    creator_baseline_sample_count: int = 0
    relative_score: float | None = None
    velocity_views_per_hour: float | None = None
    relative_velocity: float | None = None
    platform_reach_percentile: float | None = None
    platform_velocity_percentile: float | None = None
    like_rate: float | None = None
    comment_rate: float | None = None
    share_rate: float | None = None
    favorite_rate: float | None = None
    primary_class: SampleClass = SampleClass.UNKNOWN
    signals: list[str] = Field(default_factory=list)
    research_priority: int = 0
    scoring_version: str = SCORING_VERSION
    calculated_at: datetime = Field(default_factory=utc_now)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def calculate_creator_baseline(
    history: Iterable[CreatorHistoryItem],
    *,
    window_size: int = 20,
    minimum: int = 8,
) -> tuple[float | None, int]:
    """Return median views and usable sample count, never an invented fallback."""

    ordered = sorted(history, key=lambda item: _aware(item.captured_at), reverse=True)
    values: list[int] = []
    seen: set[str] = set()
    for item in ordered:
        if item.sample_id in seen or item.views is None:
            continue
        seen.add(item.sample_id)
        values.append(item.views)
        if len(values) >= window_size:
            break
    if len(values) < minimum:
        return None, len(values)
    return float(median(values)), len(values)


def _rate(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _velocity(snapshots: Iterable[MetricSnapshot]) -> float | None:
    points = sorted(
        (snapshot for snapshot in snapshots if snapshot.views is not None),
        key=lambda snapshot: _aware(snapshot.captured_at),
    )
    if len(points) < 2:
        return None
    previous, current = points[-2], points[-1]
    hours = (_aware(current.captured_at) - _aware(previous.captured_at)).total_seconds() / 3600
    if hours <= 0:
        return None
    return (current.views - previous.views) / hours


def _add_signal(signals: list[str], value: str) -> None:
    if value not in signals:
        signals.append(value)


def score_sample(
    sample: ContentSample,
    current_snapshot: MetricSnapshot,
    *,
    creator_history: Iterable[CreatorHistoryItem] = (),
    sample_snapshots: Iterable[MetricSnapshot] = (),
    platform_reach_percentile: float | None = None,
    platform_velocity_percentile: float | None = None,
    baseline_velocity: float | None = None,
    recent_7d_views: int | None = None,
    rare_topic: bool = False,
    bootstrap_reach_threshold: int | None = None,
    now: datetime | None = None,
    config: ScoringConfig | None = None,
) -> SampleDerivedMetrics:
    config = config or ScoringConfig()
    now = _aware(now or utc_now())
    published_at = _aware(sample.published_at) if sample.published_at else None
    age_hours = None if published_at is None else max(0.0, (now - published_at).total_seconds() / 3600)

    history = list(creator_history)
    baseline, baseline_count = calculate_creator_baseline(
        history,
        window_size=config.creator_window_size,
        minimum=config.minimum_baseline_samples,
    )
    views = current_snapshot.views
    relative_score = None if views is None or not baseline else views / baseline
    velocity = _velocity([*sample_snapshots, current_snapshot])
    relative_velocity = None
    if velocity is not None and baseline_velocity and baseline_velocity > 0:
        relative_velocity = velocity / baseline_velocity

    signals: list[str] = []
    if (
        platform_reach_percentile is not None and platform_reach_percentile >= 0.99
    ) or (bootstrap_reach_threshold is not None and views is not None and views >= bootstrap_reach_threshold):
        _add_signal(signals, SampleClass.MEGA_VIRAL.value)
        if bootstrap_reach_threshold is not None and (
            platform_reach_percentile is None or platform_reach_percentile < 0.99
        ):
            _add_signal(signals, "mega_viral_threshold_source=bootstrap")

    if relative_score is not None and relative_score >= config.outlier_ratio:
        _add_signal(signals, SampleClass.OUTLIER.value)
        if relative_score >= config.extreme_outlier_ratio:
            _add_signal(signals, "extreme_outlier")
        elif relative_score >= config.strong_outlier_ratio:
            _add_signal(signals, "strong_outlier")

    is_rising = (
        age_hours is not None
        and age_hours <= config.rising_max_age_hours
        and (
            (platform_velocity_percentile is not None and platform_velocity_percentile >= config.rising_velocity_percentile)
            or (relative_velocity is not None and relative_velocity >= config.rising_relative_velocity)
        )
    )
    if is_rising:
        _add_signal(signals, SampleClass.RISING.value)

    is_evergreen = (
        age_hours is not None
        and age_hours >= config.evergreen_min_age_days * 24
        and recent_7d_views is not None
        and (
            config.evergreen_recent_7d_threshold is None
            or recent_7d_views >= config.evergreen_recent_7d_threshold
        )
        and recent_7d_views > 0
    )
    if is_evergreen:
        _add_signal(signals, SampleClass.EVERGREEN.value)

    is_underperform = (
        relative_score is not None
        and relative_score <= config.underperform_ratio
        and age_hours is not None
        and age_hours >= config.underperform_min_age_hours
    )
    if is_underperform:
        _add_signal(signals, SampleClass.UNDERPERFORM.value)

    if (
        relative_score is not None
        and config.underperform_ratio < relative_score < config.normal_upper_ratio
        and not is_rising
    ):
        _add_signal(signals, SampleClass.NORMAL.value)

    priority_order = [
        SampleClass.MEGA_VIRAL,
        SampleClass.OUTLIER,
        SampleClass.RISING,
        SampleClass.EVERGREEN,
        SampleClass.UNDERPERFORM,
        SampleClass.NORMAL,
    ]
    primary = next((candidate for candidate in priority_order if candidate.value in signals), SampleClass.UNKNOWN)

    priority = 0
    if "extreme_outlier" in signals:
        priority += 3
    elif "strong_outlier" in signals:
        priority += 2
    if SampleClass.RISING.value in signals:
        priority += 2
    if SampleClass.UNDERPERFORM.value in signals:
        priority += 2
    if rare_topic:
        priority += 2
    if SampleClass.MEGA_VIRAL.value in signals:
        priority += 1
    if views is not None and current_snapshot.likes is not None and current_snapshot.comments is not None:
        priority += 1
    if primary in {SampleClass.NORMAL, SampleClass.UNDERPERFORM}:
        priority += 1
    if baseline is None:
        priority -= 2

    return SampleDerivedMetrics(
        sample_id=str(sample.sample_id),
        age_hours=age_hours,
        creator_baseline_views=baseline,
        creator_baseline_sample_count=baseline_count,
        relative_score=relative_score,
        velocity_views_per_hour=velocity,
        relative_velocity=relative_velocity,
        platform_reach_percentile=platform_reach_percentile,
        platform_velocity_percentile=platform_velocity_percentile,
        like_rate=_rate(current_snapshot.likes, views),
        comment_rate=_rate(current_snapshot.comments, views),
        share_rate=_rate(current_snapshot.shares, views),
        favorite_rate=_rate(current_snapshot.favorites, views),
        primary_class=primary,
        signals=signals,
        research_priority=max(0, priority),
        calculated_at=now,
    )

