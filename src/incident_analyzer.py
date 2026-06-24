"""Compute aging, staleness, hold-status and exception flags."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger("servicenow_reporter")


@dataclass
class AnalysisResult:
    enriched: pd.DataFrame
    summary: dict[str, Any] = field(default_factory=dict)
    exceptions: dict[str, pd.DataFrame] = field(default_factory=dict)
    aging_distribution: dict[str, int] = field(default_factory=dict)


def _hours_since(ts: pd.Timestamp, now: datetime) -> float | None:
    if pd.isna(ts):
        return None
    return round((now - ts.to_pydatetime()).total_seconds() / 3600.0, 2)


def _aging_bucket(days: float | None, buckets: list[dict]) -> str:
    if days is None:
        return "Unknown"
    for b in buckets:
        if b["min"] <= days < b["max"]:
            return b["label"]
    return "Unknown"


def analyze(df: pd.DataFrame, thresholds: dict[str, Any]) -> AnalysisResult:
    """Enrich and analyze the incident dataframe."""
    now = datetime.now()
    on_hold_states = {s.lower() for s in thresholds.get("on_hold_states", [])}
    aging_buckets = thresholds.get("aging_buckets_days", [])
    stale_hours = thresholds.get("stale_hours", [24, 48, 72])

    enriched = df.copy()
    enriched["hours_since_update"] = enriched["last_updated"].apply(
        lambda x: _hours_since(x, now)
    )
    enriched["days_since_update"] = enriched["hours_since_update"].apply(
        lambda h: round(h / 24, 2) if h is not None else None
    )
    enriched["aging_bucket"] = enriched["days_since_update"].apply(
        lambda d: _aging_bucket(d, aging_buckets)
    )
    enriched["is_on_hold"] = enriched["state"].fillna("").str.lower().isin(on_hold_states)

    # Stale flags per threshold
    for h in stale_hours:
        enriched[f"stale_{h}h"] = enriched["hours_since_update"].apply(
            lambda x, h=h: (x is not None) and (x >= h)
        )

    # ---- Summary ----
    total = len(enriched)
    summary = {
        "report_date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_incidents": total,
        "total_on_hold": int(enriched["is_on_hold"].sum()),
    }
    for h in stale_hours:
        summary[f"not_updated_{h}h"] = int(enriched[f"stale_{h}h"].sum())

    # ---- Aging distribution ----
    aging_distribution = (
        enriched["aging_bucket"].value_counts().to_dict()
    )

    # ---- Exceptions ----
    longest_stale = max(stale_hours)
    exc_stale = enriched[enriched[f"stale_{longest_stale}h"]].copy()

    exc_hold_no_reason = enriched[
        enriched["is_on_hold"] & enriched["hold_reason"].isna()
    ].copy()

    exc_dependency_missing = enriched[
        enriched["is_on_hold"] & enriched["dependency"].isna()
    ].copy()

    exceptions = {
        f"stale_over_{longest_stale}h": exc_stale,
        "on_hold_missing_reason": exc_hold_no_reason,
        "on_hold_missing_dependency": exc_dependency_missing,
    }

    logger.info(
        "Analysis done | total=%s | on_hold=%s | stale_buckets=%s",
        summary["total_incidents"],
        summary["total_on_hold"],
        {h: summary[f"not_updated_{h}h"] for h in stale_hours},
    )

    return AnalysisResult(
        enriched=enriched,
        summary=summary,
        exceptions=exceptions,
        aging_distribution=aging_distribution,
    )
