"""
TwinOps logistics simulation: docks, trucks and forklifts (LOG-01..04).

Inbound:  truck -> DOCK-RCV -> FLT-01 carries pallets to the line in-feeds.
Outbound: finished parts (line's last CNC part_count) -> pallets -> FLT-02 -> DOCK-SHP -> truck.
State is published as normal canonical telemetry; truck/pallet milestones as canonical events.
Runs on simulated time (sum of dt), so tests can fast-forward it.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from services.common.canonical import (
    AssetOperationalStatus,
    CanonicalEventMessage,
    DataQuality,
    MetricValue,
)
from simulator.config import AISLE_Z, LOGISTICS_POINTS

PALLET_KG = 450.0
SPEED_M_S = 2.0
LOAD_S_PER_PALLET = 5.0  # truck loading time at the shipping dock


@dataclass
class Dock:
    truck_present: bool = False
    truck_since: float = 0.0
    pallets_pending: int = 0
    pallets_handled: int = 0


@dataclass
class Forklift:
    x: float
    z: float
    home: tuple[float, float]
    heading: float = 0.0
    speed: float = 0.0
    battery: float = 90.0
    load_kg: float = 0.0
    pallets_moved: int = 0
    charging: bool = False
    path: list[tuple[float, float]] = field(default_factory=list)
    # remaining legs: (action, point name); action is 'pickup', 'drop' or 'charge'
    legs: list[tuple[str, str]] = field(default_factory=list)
    carry_from: str = ""
    carry_start: float = 0.0


class LogisticsSim:
    def __init__(
        self,
        site: str,
        line_output: Callable[[str], int],
        truck_interval_s: float = 180.0,
        pallets_per_truck: int = 6,
        parts_per_pallet: int = 2,
    ):
        self.site = site
        self.line_output = line_output
        self.truck_interval_s = truck_interval_s
        self.pallets_per_truck = pallets_per_truck
        self.parts_per_pallet = parts_per_pallet
        self.t = 0.0
        self.next_truck_at = 5.0
        self.docks = {"DOCK-RCV": Dock(), "DOCK-SHP": Dock()}
        self.forklifts = {
            "FLT-01": Forklift(6.0, AISLE_Z, home=(6.0, AISLE_Z)),
            "FLT-02": Forklift(50.0, AISLE_Z, home=(50.0, AISLE_Z)),
        }
        self._next_line = 0
        self._baseline: dict[str, int] = {}
        self._picked = {"LINE-01": 0, "LINE-02": 0}
        self._events: list[CanonicalEventMessage] = []

    def reset_baseline(self):
        """Count finished pallets from the current part counters onwards."""
        self._baseline = {ln: self.line_output(ln) for ln in ("LINE-01", "LINE-02")}

    # ---------------------------------------------------------------- events
    def _emit(self, asset_id: str, event_type: str, message: str, **data):
        self._events.append(
            CanonicalEventMessage(
                site=self.site, asset_id=asset_id, event_type=event_type, message=message, data=data
            )
        )

    def pop_events(self) -> list[CanonicalEventMessage]:
        events, self._events = self._events, []
        return events

    # ----------------------------------------------------------------- step
    def step(self, dt: float):
        self.t += dt
        rcv, shp = self.docks["DOCK-RCV"], self.docks["DOCK-SHP"]

        # Inbound truck arrives on a timer once the dock is free.
        if not rcv.truck_present and self.t >= self.next_truck_at:
            rcv.truck_present, rcv.truck_since = True, self.t
            rcv.pallets_pending = self.pallets_per_truck
            self._emit(
                "DOCK-RCV", "TRUCK_ARRIVED", "Inbound truck docked", pallets=rcv.pallets_pending
            )

        # Outbound truck arrives when a full load is staged, loads, then leaves.
        if not shp.truck_present and shp.pallets_pending >= self.pallets_per_truck:
            shp.truck_present, shp.truck_since = True, self.t
            self._emit(
                "DOCK-SHP", "TRUCK_ARRIVED", "Outbound truck docked", pallets=self.pallets_per_truck
            )
        elif (
            shp.truck_present
            and self.t - shp.truck_since >= LOAD_S_PER_PALLET * self.pallets_per_truck
        ):
            shp.pallets_pending -= self.pallets_per_truck
            shp.pallets_handled += self.pallets_per_truck
            self._depart("DOCK-SHP", "Outbound")

        self._dispatch()
        for fid, f in self.forklifts.items():
            self._move(fid, f, dt)

    def _depart(self, dock_id: str, direction: str):
        dock = self.docks[dock_id]
        dock.truck_present = False
        self._emit(
            dock_id,
            "TRUCK_DEPARTED",
            f"{direction} truck departed",
            turnaround_s=round(self.t - dock.truck_since, 1),
        )
        if dock_id == "DOCK-RCV":
            self.next_truck_at = self.t + self.truck_interval_s

    def _dispatch(self):
        """Give idle forklifts their next job."""
        f1, f2 = self.forklifts["FLT-01"], self.forklifts["FLT-02"]
        if not f1.legs and not f1.charging:
            if f1.battery < 25:
                f1.legs = [("charge", "CHARGER")]
            elif self.docks["DOCK-RCV"].pallets_pending > 0:
                line = ("LINE-01", "LINE-02")[self._next_line]
                self._next_line ^= 1
                f1.legs, f1.path = [("pickup", "DOCK-RCV"), ("drop", f"{line}-IN")], []
        if not f2.legs and not f2.charging:
            if f2.battery < 25:
                f2.legs = [("charge", "CHARGER")]
            else:
                for line in ("LINE-01", "LINE-02"):
                    made = (self.line_output(line) - self._baseline[line]) // self.parts_per_pallet
                    if made > self._picked[line]:
                        self._picked[line] += 1
                        f2.legs, f2.path = [("pickup", f"{line}-OUT"), ("drop", "DOCK-SHP")], []
                        break

    def _move(self, fid: str, f: Forklift, dt: float):
        if f.charging:
            f.speed = 0.0
            f.battery = min(95.0, f.battery + 1.0 * dt)
            f.charging = f.battery < 95.0
            return
        if not f.legs:
            # Nothing to do: return home, then wait.
            if not f.path and (f.x, f.z) != f.home:
                f.path = self._route((f.x, f.z), f.home)
        elif not f.path:
            target = LOGISTICS_POINTS[f.legs[0][1]]
            if (f.x, f.z) == target:
                self._arrive(fid, f)
                return
            f.path = self._route((f.x, f.z), target)

        budget = SPEED_M_S * dt
        f.speed = 0.0
        while f.path and budget > 0:
            tx, tz = f.path[0]
            dist = math.hypot(tx - f.x, tz - f.z)
            if dist <= budget:
                if dist > 0:
                    f.heading = math.degrees(math.atan2(tx - f.x, tz - f.z)) % 360
                f.x, f.z = tx, tz
                f.path.pop(0)
                budget -= dist
            else:
                f.heading = math.degrees(math.atan2(tx - f.x, tz - f.z)) % 360
                f.x += (tx - f.x) / dist * budget
                f.z += (tz - f.z) / dist * budget
                budget = 0
            f.speed = SPEED_M_S
        f.battery = max(0.0, f.battery - (0.03 if f.speed else 0.005) * dt)

    @staticmethod
    def _route(a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
        """Manhattan route through the central aisle (keeps forklifts out of the machine bays)."""
        return [(a[0], AISLE_Z), (b[0], AISLE_Z), b]

    def _arrive(self, fid: str, f: Forklift):
        action, point = f.legs.pop(0)
        if action == "charge":
            f.charging = True
        elif action == "pickup":
            f.load_kg, f.carry_from, f.carry_start = PALLET_KG, point, self.t
            if point == "DOCK-RCV":
                rcv = self.docks["DOCK-RCV"]
                rcv.pallets_pending -= 1
                rcv.pallets_handled += 1
                if rcv.pallets_pending == 0:
                    self._depart("DOCK-RCV", "Inbound")
        else:  # drop
            f.load_kg = 0.0
            f.pallets_moved += 1
            if point == "DOCK-SHP":
                self.docks["DOCK-SHP"].pallets_pending += 1
            self._emit(
                fid,
                "PALLET_MOVED",
                f"Pallet moved {f.carry_from} -> {point}",
                from_point=f.carry_from,
                to_point=point,
                duration_s=round(self.t - f.carry_start, 1),
            )

    # -------------------------------------------------------------- metrics
    def metrics(self, asset_id: str) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        def mv(v: float) -> MetricValue:
            return MetricValue(v=v, q=DataQuality.GOOD)

        if asset_id in self.docks:
            d = self.docks[asset_id]
            dwell = round(self.t - d.truck_since, 1) if d.truck_present else 0.0
            status = (
                AssetOperationalStatus.RUNNING if d.truck_present else AssetOperationalStatus.IDLE
            )
            return {
                "truck_present": mv(int(d.truck_present)),
                "pallets_pending": mv(d.pallets_pending),
                "pallets_handled": mv(d.pallets_handled),
                "truck_dwell_s": mv(dwell),
            }, status

        f = self.forklifts[asset_id]
        status = AssetOperationalStatus.RUNNING if f.speed else AssetOperationalStatus.IDLE
        return {
            "battery_pct": mv(round(f.battery, 1)),
            "pos_x_m": mv(round(f.x, 2)),
            "pos_z_m": mv(round(f.z, 2)),
            "heading_deg": mv(round(f.heading, 1)),
            "speed_m_s": mv(f.speed),
            "load_kg": mv(f.load_kg),
            "pallets_moved": mv(f.pallets_moved),
        }, status
