"""
Logistics KPIs (LOG-03): truck turnaround, pallets handled, forklift carry time and utilisation.
Derived from stored dock / forklift telemetry, so the service stays stateless.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from itertools import pairwise
from typing import Any

LOGISTICS_METRICS = ("truck_dwell_s", "pallets_handled", "pallets_moved", "load_kg", "speed_m_s")


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 1) if xs else None


def calculate_logistics_kpis(
    rows: Iterable[tuple[datetime, str, str, float]],
) -> dict[str, dict[str, Any]]:
    """rows: (ts, asset_id, metric, value), ordered by ts. Returns KPIs keyed by asset_id."""
    series: dict[tuple[str, str], list[tuple[datetime, float]]] = defaultdict(list)
    for ts, asset_id, metric, value in rows:
        series[(asset_id, metric)].append((ts, value))

    out: dict[str, dict[str, Any]] = defaultdict(dict)
    for (asset_id, metric), pts in series.items():
        vals = [v for _, v in pts]
        if metric == "truck_dwell_s":
            # a visit ends when dwell falls back to 0; its last value is the turnaround
            done = [a for a, b in pairwise(vals) if a > 0 and b == 0]
            out[asset_id]["trucks_completed"] = len(done)
            out[asset_id]["avg_truck_turnaround_s"] = _mean(done)
        elif metric in ("pallets_handled", "pallets_moved"):
            out[asset_id][metric] = int(max(vals) - min(vals))
        elif metric == "speed_m_s":
            out[asset_id]["utilisation_pct"] = round(100 * sum(v > 0 for v in vals) / len(vals), 1)
        elif metric == "load_kg":
            # loaded runs = pick-up to drop; duration from first to last loaded sample
            trips, start, prev = [], None, None
            for ts, v in pts:
                if v > 0 and start is None:
                    start = ts
                elif v == 0 and start is not None:
                    trips.append((prev - start).total_seconds())
                    start = None
                prev = ts
            out[asset_id]["avg_carry_time_s"] = _mean(trips)
    return dict(out)
