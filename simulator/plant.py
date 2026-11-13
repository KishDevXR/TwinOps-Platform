"""
TwinOps Virtual Plant Simulator Manager.
Coordinates all 29 pilot assets, time ticking, fault injections, and dispatching.
Ref: docs/01_scope_decisions.md §1, docs/05_design_document.md §8
"""

import asyncio
import logging
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from services.common.canonical import CanonicalEventMessage, CanonicalTelemetryMessage
from simulator.config import ASSET_RELATIONSHIPS, LINE_OUTPUT_ASSET, PILOT_ASSETS
from simulator.datasets import make_replay
from simulator.logistics import LogisticsSim
from simulator.machine import VirtualMachine

logger = logging.getLogger("twinops.simulator")


class VirtualPlant:
    """
    Simulates the entire 2-line discrete manufacturing pilot plant (PUNE-01).
    Encapsulates 29 virtual assets (25 machines + 2 docks + 2 forklifts) and their thermodynamic/operational interactions.
    """

    def __init__(self, site: str = "PUNE-01", replay_dir: Path | None = None):
        self.site = site
        self.machines: dict[str, VirtualMachine] = {}
        self.relationships = ASSET_RELATIONSHIPS
        self.is_running = False

        self.logistics = LogisticsSim(
            site, line_output=lambda line: self.machines[LINE_OUTPUT_ASSET[line]].part_counter
        )
        for cfg in PILOT_ASSETS:
            self.machines[cfg.asset_id] = VirtualMachine(
                cfg, site=self.site, logistics=self.logistics
            )
        if replay_dir:
            seen: Counter[str] = Counter()
            for m in self.machines.values():
                m.replay = make_replay(
                    m.type_id, replay_dir, m.config.nominal_params, seen[m.type_id]
                )
                seen[m.type_id] += 1
        # baseline once the CNC part counters exist
        self.logistics.reset_baseline()

        logger.info(f"Initialized VirtualPlant at {site} with {len(self.machines)} assets.")

    def get_machine(self, asset_id: str) -> VirtualMachine | None:
        return self.machines.get(asset_id)

    def list_machines(self) -> list[VirtualMachine]:
        return list(self.machines.values())

    def inject_fault(
        self,
        asset_id: str,
        fault_type: str,
        severity: float = 1.0,
        params: dict[str, Any] | None = None,
    ):
        """Inject a fault into a specific machine."""
        machine = self.get_machine(asset_id)
        if not machine:
            raise ValueError(f"Asset '{asset_id}' not found in virtual plant {self.site}")
        machine.inject_fault(fault_type, severity=severity, params=params)
        logger.warning(f"Injected fault '{fault_type}' (sev={severity}) into {asset_id}")

    def clear_fault(self, asset_id: str, fault_type: str | None = None):
        """Clear active fault(s) on a machine."""
        machine = self.get_machine(asset_id)
        if not machine:
            raise ValueError(f"Asset '{asset_id}' not found in virtual plant {self.site}")
        machine.clear_fault(fault_type)
        logger.info(f"Cleared fault(s) on {asset_id}")

    def clear_all_faults(self):
        """Reset all machines to normal healthy state."""
        for m in self.machines.values():
            m.clear_fault()
        logger.info("Cleared all active faults across plant.")

    def tick(self, dt: float = 1.0) -> list[CanonicalTelemetryMessage]:
        """
        Advance the entire plant by dt seconds and collect all generated telemetry messages.
        Filters out machines currently in total communication loss.
        """
        messages: list[CanonicalTelemetryMessage] = []
        self.logistics.step(dt)
        for machine in self.machines.values():
            msg = machine.step(dt=dt)
            if msg is not None:
                messages.append(msg)
        return messages

    def pop_events(self) -> list[CanonicalEventMessage]:
        """Drain logistics events (truck arrivals/departures, pallet moves) since last call."""
        return self.logistics.pop_events()

    async def run_continuous(
        self,
        interval_s: float = 1.0,
        on_telemetry: Callable[[CanonicalTelemetryMessage], Any] | None = None,
        on_event: Callable[[CanonicalEventMessage], Any] | None = None,
        stop_event: asyncio.Event | None = None,
    ):
        """
        Continuously run the plant simulation loop at interval_s until stopped.
        """
        self.is_running = True
        logger.info(f"Starting continuous simulation clock (interval={interval_s}s)...")
        try:
            while self.is_running:
                if stop_event and stop_event.is_set():
                    break

                start_time = asyncio.get_event_loop().time()
                messages = self.tick(dt=interval_s)

                if on_telemetry:
                    for msg in messages:
                        if asyncio.iscoroutinefunction(on_telemetry):
                            await on_telemetry(msg)
                        else:
                            on_telemetry(msg)

                for ev in self.pop_events():
                    if on_event:
                        on_event(ev)

                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_dur = max(0.01, interval_s - elapsed)
                await asyncio.sleep(sleep_dur)
        finally:
            self.is_running = False
            logger.info("Continuous plant simulation stopped.")
