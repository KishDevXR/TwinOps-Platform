"""
TwinOps Physics-Lite Virtual Machine & Fault Injection Engine.
Ref: docs/05_design_document.md §8
"""

import math
import random
from datetime import UTC, datetime
from typing import Any

from services.common.canonical import (
    AssetOperationalStatus,
    CanonicalTelemetryMessage,
    DataQuality,
    MetricValue,
)
from simulator.config import AssetConfig


class VirtualMachine:
    """
    Virtual asset simulation instance with dynamic states, first-order thermal lags,
    vibration harmonics, and controllable fault injection modes.
    """

    def __init__(self, config: AssetConfig, site: str = "PUNE-01"):
        self.config = config
        self.asset_id = config.asset_id
        self.type_id = config.type_id
        self.site = site

        # Operational status & internal timers
        self.status = AssetOperationalStatus.RUNNING
        self.uptime_seconds = 0
        self.part_counter = random.randint(100, 500)
        self.run_hours = float(random.randint(1200, 4800))
        self.time_in_state = 0.0

        # Physical state variables
        self.load_factor = 0.85
        self.temperature = float(config.nominal_params.get("base_temp", 40.0))
        self.vibration = 1.8 + random.uniform(0.1, 0.4)
        self.power_kw = float(config.nominal_params.get("power_kw", 10.0))

        # Fault injection state
        self.active_faults: dict[str, dict[str, Any]] = {}
        # e.g. {"overheat": {"severity": 1.0, "time_active": 0.0}}

    def inject_fault(
        self, fault_type: str, severity: float = 1.0, params: dict[str, Any] | None = None
    ):
        """
        Inject a specific physical or sensor fault.
        fault_type can be: 'overheat', 'bearing_wear', 'cavitation', 'filter_clog',
                           'air_leak', 'power_imbalance', 'comm_loss', 'sensor_fault'
        """
        self.active_faults[fault_type] = {
            "severity": float(severity),
            "time_active": 0.0,
            "params": params or {},
        }

    def clear_fault(self, fault_type: str | None = None):
        """Clear a specific active fault or all faults if fault_type is None."""
        if fault_type:
            self.active_faults.pop(fault_type, None)
        else:
            self.active_faults.clear()

    def set_status(self, status: AssetOperationalStatus):
        """Explicitly switch asset operational status."""
        self.status = status
        self.time_in_state = 0.0

    def step(self, dt: float = 1.0) -> CanonicalTelemetryMessage | None:
        """
        Advance physics simulation by dt seconds and generate Canonical Telemetry Message.
        Returns None if asset is in total communication blackout.
        """
        self.uptime_seconds += int(dt)
        self.time_in_state += dt
        now = datetime.now(UTC)

        # Advance active fault timers
        for fault in self.active_faults.values():
            fault["time_active"] += dt

        # Check total communication loss fault
        if "comm_loss" in self.active_faults:
            return None

        # Check sensor fault quality override
        quality_override = None
        if "sensor_fault" in self.active_faults:
            quality_override = DataQuality.BAD

        # Run type-specific physics generator
        if self.type_id == "cnc_machine":
            metrics, status = self._step_cnc(dt)
        elif self.type_id == "centrifugal_pump":
            metrics, status = self._step_pump(dt)
        elif self.type_id == "robot_cell":
            metrics, status = self._step_robot(dt)
        elif self.type_id == "conveyor":
            metrics, status = self._step_conveyor(dt)
        elif self.type_id == "air_compressor":
            metrics, status = self._step_compressor(dt)
        elif self.type_id == "chiller":
            metrics, status = self._step_chiller(dt)
        elif self.type_id == "ahu":
            metrics, status = self._step_ahu(dt)
        elif self.type_id == "energy_meter":
            metrics, status = self._step_energy_meter(dt)
        else:
            metrics, status = self._step_generic(dt)

        # Apply sensor quality override if active
        if quality_override is not None:
            for k in metrics:
                metrics[k] = MetricValue(v=metrics[k].v, q=quality_override)

        # Accumulate run hours when running
        if status == AssetOperationalStatus.RUNNING:
            self.run_hours += dt / 3600.0

        return CanonicalTelemetryMessage(
            v=1, site=self.site, asset_id=self.asset_id, ts=now, metrics=metrics, status=status
        )

    # -------------------------------------------------------------
    # Type-Specific Physics-Lite Models
    # -------------------------------------------------------------

    def _step_cnc(self, dt: float) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        nominal_rpm = float(self.config.nominal_params.get("spindle_rpm", 8000))
        base_power = float(self.config.nominal_params.get("power_kw", 12.0))

        # Machining cycle: slight periodic load variations (sinusoidal + noise)
        cycle_phase = (self.uptime_seconds % 60) / 60.0
        in_cut = cycle_phase > 0.15 and cycle_phase < 0.85

        if self.status == AssetOperationalStatus.STOPPED:
            rpm = 0.0
            power = 0.2
            target_temp = 28.0
            target_vib = 0.1
            feed = 0.0
            load_pct = 0.0
            status = AssetOperationalStatus.STOPPED
        elif self.status == AssetOperationalStatus.IDLE:
            rpm = 500.0 + random.uniform(-10, 10)
            power = 1.2 + random.uniform(-0.1, 0.1)
            target_temp = 34.0
            target_vib = 0.8
            feed = 0.0
            load_pct = 8.0
            status = AssetOperationalStatus.IDLE
        else:
            # RUNNING
            status = AssetOperationalStatus.RUNNING
            rpm = nominal_rpm * (0.95 + 0.05 * in_cut) + random.uniform(-25, 25)
            load_pct = (75.0 if in_cut else 25.0) + random.uniform(-3, 3)
            power = base_power * (0.4 + 0.6 * (load_pct / 100.0)) + random.uniform(-0.2, 0.2)
            feed = (1200.0 if in_cut else 400.0) + random.uniform(-10, 10)
            target_temp = 48.0 + (load_pct * 0.15)
            target_vib = 1.8 + (load_pct * 0.02)
            if in_cut and random.random() < (dt / 45.0):
                self.part_counter += 1

        # Check Injected Faults
        if "overheat" in self.active_faults:
            sev = self.active_faults["overheat"]["severity"]
            target_temp += 35.0 * sev  # pushes spindle temp to 75-85 °C (triggers HI/HI_HI)

        if "bearing_wear" in self.active_faults:
            sev = self.active_faults["bearing_wear"]["severity"]
            t_act = self.active_faults["bearing_wear"]["time_active"]
            # Gradual wear progression term
            growth = min(2.5, 1.0 + (t_act / 60.0))
            target_vib += 4.5 * sev * growth  # pushes vibration to > 6.5 mm/s

        # First order thermal lag: dT/dt = (T_target - T) / tau
        tau_temp = 20.0  # 20 second thermal time constant
        self.temperature += (target_temp - self.temperature) * (dt / tau_temp) + random.uniform(
            -0.05, 0.05
        )

        # Vibration dynamic response
        tau_vib = 3.0
        self.vibration += (target_vib - self.vibration) * (dt / tau_vib) + random.uniform(
            -0.08, 0.08
        )
        self.vibration = max(0.1, self.vibration)

        # Coolant delivery
        coolant_temp = 24.0 + random.uniform(-0.3, 0.3)
        coolant_flow = (
            14.5 + random.uniform(-0.5, 0.5) if status == AssetOperationalStatus.RUNNING else 0.0
        )

        # Axis positions (smooth simulated table movement)
        pos_x = 250.0 + 120.0 * math.sin(self.uptime_seconds * 0.2)
        pos_y = 150.0 + 80.0 * math.cos(self.uptime_seconds * 0.25)
        pos_z = -45.0 + 15.0 * math.sin(self.uptime_seconds * 0.4)

        metrics = {
            "spindle_temp_c": MetricValue(v=round(self.temperature, 2), q=DataQuality.GOOD),
            "vibration_mm_s": MetricValue(v=round(self.vibration, 2), q=DataQuality.GOOD),
            "spindle_rpm": MetricValue(v=round(rpm, 1), q=DataQuality.GOOD),
            "spindle_load_pct": MetricValue(v=round(load_pct, 1), q=DataQuality.GOOD),
            "feed_rate_mm_min": MetricValue(v=round(feed, 1), q=DataQuality.GOOD),
            "coolant_flow_l_min": MetricValue(v=round(coolant_flow, 2), q=DataQuality.GOOD),
            "coolant_temp_c": MetricValue(v=round(coolant_temp, 2), q=DataQuality.GOOD),
            "power_kw": MetricValue(v=round(power, 2), q=DataQuality.GOOD),
            "part_count": MetricValue(v=int(self.part_counter), q=DataQuality.GOOD),
            "axis_x_pos_mm": MetricValue(v=round(pos_x, 2), q=DataQuality.GOOD),
            "axis_y_pos_mm": MetricValue(v=round(pos_y, 2), q=DataQuality.GOOD),
            "axis_z_pos_mm": MetricValue(v=round(pos_z, 2), q=DataQuality.GOOD),
        }
        return metrics, status

    def _step_pump(self, dt: float) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        nominal_flow = float(self.config.nominal_params.get("flow_m3h", 40.0))
        nominal_head = float(self.config.nominal_params.get("discharge_bar", 5.5))
        base_power = float(self.config.nominal_params.get("power_kw", 9.0))

        flow = nominal_flow + random.uniform(-0.8, 0.8)
        discharge = nominal_head + random.uniform(-0.15, 0.15)
        suction = 1.2 + random.uniform(-0.05, 0.05)
        rpm = 2920.0 + random.uniform(-10, 10)
        power = base_power + random.uniform(-0.2, 0.2)
        target_temp = 58.0
        target_vib = 2.1

        # Check Injected Faults
        if "bearing_wear" in self.active_faults:
            sev = self.active_faults["bearing_wear"]["severity"]
            t_act = self.active_faults["bearing_wear"]["time_active"]
            growth = 1.0 + (t_act / 40.0)
            target_vib += 5.2 * sev * growth  # drives vibration > 7.1 mm/s (HI_HI zone)
            target_temp += 22.0 * sev

        if "cavitation" in self.active_faults:
            sev = self.active_faults["cavitation"]["severity"]
            suction = max(0.01, suction - 1.15 * sev)  # suction loss
            discharge *= 1.0 - 0.35 * sev
            flow *= 1.0 - 0.4 * sev
            # Cavitation causes wild high frequency vibration oscillations
            target_vib += 4.8 * sev + random.uniform(-1.5, 1.5)

        tau_temp = 25.0
        self.temperature += (target_temp - self.temperature) * (dt / tau_temp) + random.uniform(
            -0.04, 0.04
        )

        tau_vib = 2.0
        self.vibration += (target_vib - self.vibration) * (dt / tau_vib) + random.uniform(
            -0.06, 0.06
        )
        self.vibration = max(0.1, self.vibration)

        status = AssetOperationalStatus.RUNNING if power > 1.0 else AssetOperationalStatus.STOPPED

        metrics = {
            "flow_m3h": MetricValue(v=round(flow, 2), q=DataQuality.GOOD),
            "discharge_bar": MetricValue(v=round(discharge, 2), q=DataQuality.GOOD),
            "suction_bar": MetricValue(v=round(suction, 2), q=DataQuality.GOOD),
            "motor_temp_c": MetricValue(v=round(self.temperature, 2), q=DataQuality.GOOD),
            "vibration_mm_s": MetricValue(v=round(self.vibration, 2), q=DataQuality.GOOD),
            "power_kw": MetricValue(v=round(power, 2), q=DataQuality.GOOD),
            "motor_rpm": MetricValue(v=round(rpm, 1), q=DataQuality.GOOD),
        }
        return metrics, status

    def _step_compressor(self, dt: float) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        nom_pressure = float(self.config.nominal_params.get("discharge_pressure_bar", 7.4))
        nom_power = float(self.config.nominal_params.get("motor_power_kw", 30.0))

        # Modulation cycle around target pressure
        cycle = math.sin(self.uptime_seconds * 0.08)
        pressure = nom_pressure + 0.3 * cycle + random.uniform(-0.05, 0.05)
        power = nom_power * (0.8 + 0.2 * cycle) + random.uniform(-0.4, 0.4)
        flow_cfm = 210.0 * (0.85 + 0.15 * cycle) + random.uniform(-3, 3)
        oil_dp = 0.45 + random.uniform(-0.02, 0.02)
        target_temp = 82.0

        if "air_leak" in self.active_faults:
            sev = self.active_faults["air_leak"]["severity"]
            pressure -= 1.8 * sev  # drops below 6.0 bar
            power *= 1.0 + 0.25 * sev  # compressor runs at 100% capacity continuously

        if "filter_clog" in self.active_faults:
            sev = self.active_faults["filter_clog"]["severity"]
            oil_dp += 1.1 * sev  # oil filter differential pressure alarm

        self.temperature += (target_temp - self.temperature) * (dt / 30.0) + random.uniform(
            -0.05, 0.05
        )
        status = AssetOperationalStatus.RUNNING

        metrics = {
            "discharge_pressure_bar": MetricValue(v=round(pressure, 2), q=DataQuality.GOOD),
            "discharge_temp_c": MetricValue(v=round(self.temperature, 2), q=DataQuality.GOOD),
            "motor_power_kw": MetricValue(v=round(power, 2), q=DataQuality.GOOD),
            "flow_rate_cfm": MetricValue(v=round(flow_cfm, 1), q=DataQuality.GOOD),
            "oil_differential_pressure_bar": MetricValue(v=round(oil_dp, 3), q=DataQuality.GOOD),
            "run_hours": MetricValue(v=round(self.run_hours, 2), q=DataQuality.GOOD),
        }
        return metrics, status

    def _step_robot(self, dt: float) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        nom_cycle = float(self.config.nominal_params.get("cycle_time_s", 30.0))
        power = 3.5 + 1.2 * math.sin(self.uptime_seconds * 0.3) + random.uniform(-0.1, 0.1)
        j1 = 44.0 + 3.0 * math.sin(self.uptime_seconds * 0.05)
        j2 = 48.0 + 4.0 * math.cos(self.uptime_seconds * 0.05)
        j3 = 42.0 + 2.0 * math.sin(self.uptime_seconds * 0.08)
        grip_pressure = 6.2 + random.uniform(-0.1, 0.1)

        metrics = {
            "cycle_time_s": MetricValue(
                v=round(nom_cycle + random.uniform(-1.0, 1.0), 1), q=DataQuality.GOOD
            ),
            "power_kw": MetricValue(v=round(power, 2), q=DataQuality.GOOD),
            "joint_j1_temp_c": MetricValue(v=round(j1, 1), q=DataQuality.GOOD),
            "joint_j2_temp_c": MetricValue(v=round(j2, 1), q=DataQuality.GOOD),
            "joint_j3_temp_c": MetricValue(v=round(j3, 1), q=DataQuality.GOOD),
            "gripper_pressure_bar": MetricValue(v=round(grip_pressure, 2), q=DataQuality.GOOD),
            "cycle_count": MetricValue(v=int(self.uptime_seconds // 30), q=DataQuality.GOOD),
        }
        return metrics, AssetOperationalStatus.RUNNING

    def _step_conveyor(self, dt: float) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        speed = float(self.config.nominal_params.get("speed_m_min", 14.0)) + random.uniform(
            -0.2, 0.2
        )
        power = float(self.config.nominal_params.get("power_kw", 3.2)) + random.uniform(-0.1, 0.1)
        current = 8.5 + random.uniform(-0.3, 0.3)
        temp = 48.0 + random.uniform(-0.2, 0.2)
        tension = 850.0 + random.uniform(-15, 15)

        metrics = {
            "speed_m_min": MetricValue(v=round(speed, 2), q=DataQuality.GOOD),
            "motor_current_a": MetricValue(v=round(current, 2), q=DataQuality.GOOD),
            "motor_temp_c": MetricValue(v=round(temp, 1), q=DataQuality.GOOD),
            "belt_tension_n": MetricValue(v=round(tension, 1), q=DataQuality.GOOD),
            "power_kw": MetricValue(v=round(power, 2), q=DataQuality.GOOD),
        }
        return metrics, AssetOperationalStatus.RUNNING

    def _step_chiller(self, dt: float) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        inlet_c = 14.2 + random.uniform(-0.2, 0.2)
        outlet_c = 8.4 + random.uniform(-0.2, 0.2)
        suction_bar = 4.2 + random.uniform(-0.1, 0.1)
        discharge_bar = 15.6 + random.uniform(-0.3, 0.3)
        power = 22.4 + random.uniform(-0.4, 0.4)
        cop = 4.1 + random.uniform(-0.1, 0.1)

        metrics = {
            "chilled_water_inlet_c": MetricValue(v=round(inlet_c, 2), q=DataQuality.GOOD),
            "chilled_water_outlet_c": MetricValue(v=round(outlet_c, 2), q=DataQuality.GOOD),
            "refrigerant_suction_bar": MetricValue(v=round(suction_bar, 2), q=DataQuality.GOOD),
            "refrigerant_discharge_bar": MetricValue(v=round(discharge_bar, 2), q=DataQuality.GOOD),
            "compressor_power_kw": MetricValue(v=round(power, 2), q=DataQuality.GOOD),
            "cop": MetricValue(v=round(cop, 2), q=DataQuality.GOOD),
        }
        return metrics, AssetOperationalStatus.RUNNING

    def _step_ahu(self, dt: float) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        temp = 21.2 + random.uniform(-0.3, 0.3)
        dp = float(self.config.nominal_params.get("filter_dp_pa", 140.0)) + random.uniform(-3, 3)
        rpm = float(self.config.nominal_params.get("fan_speed_rpm", 1420)) + random.uniform(-10, 10)
        power = 4.8 + random.uniform(-0.1, 0.1)
        flow = 8200.0 + random.uniform(-50, 50)

        if "filter_clog" in self.active_faults:
            sev = self.active_faults["filter_clog"]["severity"]
            dp += 220.0 * sev  # drives filter dp > 360 Pa (reaches HI / HI_HI)
            flow *= 1.0 - 0.25 * sev

        metrics = {
            "supply_air_temp_c": MetricValue(v=round(temp, 2), q=DataQuality.GOOD),
            "filter_dp_pa": MetricValue(v=round(dp, 1), q=DataQuality.GOOD),
            "fan_speed_rpm": MetricValue(v=round(rpm, 1), q=DataQuality.GOOD),
            "air_flow_m3h": MetricValue(v=round(flow, 1), q=DataQuality.GOOD),
            "fan_power_kw": MetricValue(v=round(power, 2), q=DataQuality.GOOD),
        }
        return metrics, AssetOperationalStatus.RUNNING

    def _step_energy_meter(
        self, dt: float
    ) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        voltage = float(self.config.nominal_params.get("voltage_v", 415.0)) + random.uniform(
            -2.5, 2.5
        )
        current = float(self.config.nominal_params.get("current_a", 100.0)) + random.uniform(
            -4.0, 4.0
        )
        pf = float(self.config.nominal_params.get("power_factor", 0.92)) + random.uniform(
            -0.01, 0.01
        )

        active_kw = (math.sqrt(3) * voltage * current * pf) / 1000.0
        reactive_kvar = active_kw * math.tan(math.acos(min(1.0, max(0.1, pf))))
        freq = 50.02 + random.uniform(-0.04, 0.04)

        # Accumulate kWh
        self.power_kw += active_kw * dt / 3600.0

        metrics = {
            "voltage_v": MetricValue(v=round(voltage, 1), q=DataQuality.GOOD),
            "current_a": MetricValue(v=round(current, 1), q=DataQuality.GOOD),
            "power_kw": MetricValue(v=round(active_kw, 2), q=DataQuality.GOOD),
            "power_reactive_kvar": MetricValue(v=round(reactive_kvar, 2), q=DataQuality.GOOD),
            "power_factor": MetricValue(v=round(pf, 3), q=DataQuality.GOOD),
            "frequency_hz": MetricValue(v=round(freq, 2), q=DataQuality.GOOD),
            "energy_kwh": MetricValue(v=round(self.power_kw, 2), q=DataQuality.GOOD),
        }
        return metrics, AssetOperationalStatus.RUNNING

    def _step_generic(self, dt: float) -> tuple[dict[str, MetricValue], AssetOperationalStatus]:
        return {
            "power_kw": MetricValue(v=round(self.power_kw, 2), q=DataQuality.GOOD)
        }, AssetOperationalStatus.RUNNING
