"""
TwinOps Overall Equipment Effectiveness (OEE) & Productivity Analytics (ANL-01)
Formulation according to SEMI E10 / ISO 22400:
Availability = Run Time / Planned Time
Performance = (Ideal Cycle Time * Total Count) / Run Time
Quality = Good Count / Total Count
OEE = Availability * Performance * Quality
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OEEResult:
    availability_pct: float
    performance_pct: float
    quality_pct: float
    oee_pct: float
    planned_time_s: float
    operating_time_s: float
    ideal_cycle_time_s: float
    total_count: int
    good_count: int
    scrap_count: int
    energy_per_part_kwh: float | None = None


def calculate_oee(
    planned_time_s: float,
    operating_time_s: float,
    ideal_cycle_time_s: float,
    total_count: int,
    good_count: int,
    energy_kwh: float | None = None,
) -> OEEResult:
    """
    Calculate SEMI E10 / ISO 22400 standard OEE metrics.
    For TC-ANL-01 benchmark:
    planned=8h (28800s), operating=7h (25200s), ideal=60s, total=400, good=390
    -> Availability 87.5%, Performance 95.2%, Quality 97.5%, OEE 81.3%
    """
    if planned_time_s <= 0:
        raise ValueError("planned_time_s must be positive")
    if operating_time_s < 0:
        raise ValueError("operating_time_s cannot be negative")
    if total_count < 0 or good_count < 0:
        raise ValueError("counts cannot be negative")
    if good_count > total_count:
        raise ValueError("good_count cannot exceed total_count")

    # 1. Availability: operating time / planned time
    availability = min(1.0, operating_time_s / planned_time_s)

    # 2. Performance: (ideal cycle time * total count) / operating time
    if operating_time_s > 0:
        performance = min(1.0, (ideal_cycle_time_s * total_count) / operating_time_s)
    else:
        performance = 0.0

    # 3. Quality: good count / total count
    if total_count > 0:
        quality = good_count / total_count
    else:
        quality = 1.0

    # 4. Overall OEE (round half up to avoid banker's rounding on .25)
    oee = availability * performance * quality

    scrap = max(0, total_count - good_count)
    energy_per_part = (energy_kwh / good_count) if (energy_kwh and good_count > 0) else None

    return OEEResult(
        availability_pct=round(availability * 100 + 1e-6, 1),
        performance_pct=round(performance * 100 + 1e-6, 1),
        quality_pct=round(quality * 100 + 1e-6, 1),
        oee_pct=round(oee * 100 + 1e-6, 1),
        planned_time_s=planned_time_s,
        operating_time_s=operating_time_s,
        ideal_cycle_time_s=ideal_cycle_time_s,
        total_count=total_count,
        good_count=good_count,
        scrap_count=scrap,
        energy_per_part_kwh=round(energy_per_part, 3) if energy_per_part else None,
    )


def calculate_downtime_pareto(
    downtime_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Generate Pareto 80/20 distribution of plant downtime causes.
    Input: list of { reason: str, duration_minutes: float }
    Output: sorted reasons with percentage and cumulative percentage.
    """
    category_totals: dict[str, float] = {}
    for ev in downtime_events:
        reason = ev.get("reason", "Unknown")
        dur = float(ev.get("duration_minutes", 0.0))
        category_totals[reason] = category_totals.get(reason, 0.0) + dur

    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    total_downtime = sum(category_totals.values()) or 1.0

    pareto_list = []
    cumulative_min = 0.0
    for reason, minutes in sorted_categories:
        cumulative_min += minutes
        pct = (minutes / total_downtime) * 100
        cum_pct = (cumulative_min / total_downtime) * 100
        pareto_list.append(
            {
                "reason": reason,
                "downtime_minutes": round(minutes, 1),
                "share_pct": round(pct, 1),
                "cumulative_pct": round(cum_pct, 1),
            }
        )

    return pareto_list
