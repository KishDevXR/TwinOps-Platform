"""
TwinOps Asset Type Twin Templates.
Standardized templates defining metrics, engineering units, alarm limits,
derived KPIs, 3D model mappings, and maintenance presets.
Ref: docs/05_design_document.md §4, docs/01_scope_decisions.md §1
"""

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class MetricDefinition(BaseModel):
    name: str
    unit: str
    description: str = ""
    lo_lo: float | None = None
    lo: float | None = None
    hi: float | None = None
    hi_hi: float | None = None


class DerivedMetricDefinition(BaseModel):
    name: str
    unit: str = ""
    expr: str
    description: str = ""


class PMDefault(BaseModel):
    name: str
    trigger_type: str = "meter"  # 'calendar' or 'meter'
    interval_hours: int | None = None
    interval_days: int | None = None
    checklist: List[str] = Field(default_factory=list)


class AssetTypeTemplate(BaseModel):
    id: str
    name: str
    category: str
    metrics: List[MetricDefinition]
    derived: List[DerivedMetricDefinition] = Field(default_factory=list)
    status_rules: Dict[str, str] = Field(default_factory=dict)
    model_3d: str
    pm_defaults: List[PMDefault] = Field(default_factory=list)
    ai: Dict[str, bool] = Field(default_factory=lambda: {"anomaly": True, "rul": True})


# ==============================================================================
# PILOT TEMPLATES (8 Standard Asset Types for Pilot Auto-Component Plant)
# ==============================================================================

TEMPLATES: Dict[str, AssetTypeTemplate] = {
    # 1. CNC Machining Centre (Fanuc / Siemens / Haas)
    "cnc_machine": AssetTypeTemplate(
        id="cnc_machine",
        name="CNC Machining Centre",
        category="Machining",
        metrics=[
            MetricDefinition(name="spindle_temp_c", unit="°C", hi=65.0, hi_hi=75.0, description="Spindle bearing temperature"),
            MetricDefinition(name="vibration_mm_s", unit="mm/s", hi=4.5, hi_hi=7.1, description="RMS vibration velocity (ISO 10816)"),
            MetricDefinition(name="spindle_rpm", unit="RPM", hi=12000, description="Spindle rotational speed"),
            MetricDefinition(name="spindle_load_pct", unit="%", hi=85.0, hi_hi=100.0, description="Spindle motor load %"),
            MetricDefinition(name="feed_rate_mm_min", unit="mm/min", description="Axis feed rate"),
            MetricDefinition(name="coolant_flow_l_min", unit="L/min", lo=5.0, lo_lo=2.0, description="Coolant delivery rate"),
            MetricDefinition(name="coolant_temp_c", unit="°C", hi=35.0, hi_hi=45.0, description="Coolant temperature"),
            MetricDefinition(name="power_kw", unit="kW", hi=25.0, description="Active electric power"),
            MetricDefinition(name="part_count", unit="count", description="Completed workpiece counter"),
            MetricDefinition(name="axis_x_pos_mm", unit="mm"),
            MetricDefinition(name="axis_y_pos_mm", unit="mm"),
            MetricDefinition(name="axis_z_pos_mm", unit="mm"),
        ],
        derived=[
            DerivedMetricDefinition(
                name="spindle_thermal_rise_c",
                unit="°C",
                expr="spindle_temp_c - coolant_temp_c",
                description="Thermal delta between spindle and coolant"
            )
        ],
        status_rules={
            "RUNNING": "spindle_rpm > 500 and power_kw > 1.5",
            "IDLE": "spindle_rpm <= 500 and power_kw > 0.5",
            "STOPPED": "power_kw <= 0.5",
        },
        model_3d="models/cnc_machine.glb",
        pm_defaults=[
            PMDefault(
                name="Spindle & Way Lube Inspection",
                trigger_type="meter",
                interval_hours=250,
                checklist=["Check lube oil reservoir level", "Inspect way wipers for wear", "Verify spindle chiller flow"]
            ),
            PMDefault(
                name="Axis Backlash & Ball Screw Check",
                trigger_type="meter",
                interval_hours=1000,
                checklist=["Dial indicator test on X/Y/Z", "Grease linear guide blocks", "Inspect cable drag chains"]
            ),
        ],
        ai={"anomaly": True, "rul": True}
    ),

    # 2. Centrifugal Coolant/Water Pump
    "centrifugal_pump": AssetTypeTemplate(
        id="centrifugal_pump",
        name="Centrifugal Pump",
        category="Utilities & Fluids",
        metrics=[
            MetricDefinition(name="flow_m3h", unit="m³/h", hi=120.0, description="Discharge volume flow"),
            MetricDefinition(name="discharge_bar", unit="bar", hi=8.0, hi_hi=10.0, lo=2.0, description="Discharge pressure"),
            MetricDefinition(name="suction_bar", unit="bar", lo=0.2, lo_lo=0.0, description="Suction head pressure"),
            MetricDefinition(name="motor_temp_c", unit="°C", hi=80.0, hi_hi=95.0, description="Motor winding temperature"),
            MetricDefinition(name="vibration_mm_s", unit="mm/s", hi=4.5, hi_hi=7.1, description="Pump casing vibration RMS"),
            MetricDefinition(name="power_kw", unit="kW", hi=18.0, description="Motor electrical power draw"),
            MetricDefinition(name="motor_rpm", unit="RPM", hi=3000),
        ],
        derived=[
            DerivedMetricDefinition(
                name="efficiency_pct",
                unit="%",
                expr="(flow_m3h * discharge_bar * 2.78) / (power_kw + 0.001)",
                description="Hydraulic efficiency ratio"
            ),
            DerivedMetricDefinition(
                name="differential_bar",
                unit="bar",
                expr="discharge_bar - suction_bar",
                description="Pump total dynamic head differential"
            )
        ],
        status_rules={
            "RUNNING": "power_kw > 0.5",
            "STOPPED": "power_kw <= 0.5",
        },
        model_3d="models/pump_centrifugal.glb",
        pm_defaults=[
            PMDefault(
                name="Bearing Greasing & Seal Check",
                trigger_type="meter",
                interval_hours=500,
                checklist=["Grease drive and non-drive bearings", "Inspect mechanical seal for leakage", "Record vibration level"]
            )
        ],
        ai={"anomaly": True, "rul": True}
    ),

    # 3. 6-Axis Articulated Robot Cell (Fanuc / ABB / Kuka)
    "robot_cell": AssetTypeTemplate(
        id="robot_cell",
        name="6-Axis Articulated Robot",
        category="Robotics & Handling",
        metrics=[
            MetricDefinition(name="cycle_time_s", unit="s", hi=45.0, description="Per-part handling cycle duration"),
            MetricDefinition(name="power_kw", unit="kW", hi=8.0),
            MetricDefinition(name="joint_j1_temp_c", unit="°C", hi=70.0),
            MetricDefinition(name="joint_j2_temp_c", unit="°C", hi=70.0),
            MetricDefinition(name="joint_j3_temp_c", unit="°C", hi=70.0),
            MetricDefinition(name="gripper_pressure_bar", unit="bar", lo=4.0, description="Pneumatic gripper pressure"),
            MetricDefinition(name="cycle_count", unit="count"),
        ],
        status_rules={
            "RUNNING": "power_kw > 1.0",
            "IDLE": "power_kw > 0.2 and power_kw <= 1.0",
            "STOPPED": "power_kw <= 0.2",
        },
        model_3d="models/robot_6axis.glb",
        pm_defaults=[
            PMDefault(
                name="Gearbox Lubrication & Belt Tension",
                trigger_type="meter",
                interval_hours=2000,
                checklist=["Inspect harness dress pack", "Check timing belt tension on wrist axes", "Check seal grease"]
            )
        ],
        ai={"anomaly": True, "rul": False}
    ),

    # 4. Conveyor Line
    "conveyor": AssetTypeTemplate(
        id="conveyor",
        name="Parts Belt Conveyor",
        category="Material Handling",
        metrics=[
            MetricDefinition(name="speed_m_min", unit="m/min", lo=5.0, hi=25.0),
            MetricDefinition(name="motor_current_a", unit="A", hi=12.0, hi_hi=16.0),
            MetricDefinition(name="motor_temp_c", unit="°C", hi=75.0),
            MetricDefinition(name="belt_tension_n", unit="N", lo=500, hi=1200),
            MetricDefinition(name="power_kw", unit="kW", hi=5.5),
        ],
        status_rules={
            "RUNNING": "speed_m_min > 0.5",
            "STOPPED": "speed_m_min <= 0.5",
        },
        model_3d="models/conveyor.glb",
        pm_defaults=[
            PMDefault(
                name="Roller Bearing Inspection & Belt Tracking",
                trigger_type="calendar",
                interval_days=60,
                checklist=["Inspect belt alignment and tracking", "Check drive chain lubrication", "Inspect emergency pull cord"]
            )
        ],
        ai={"anomaly": True, "rul": False}
    ),

    # 5. Rotary Screw Air Compressor
    "air_compressor": AssetTypeTemplate(
        id="air_compressor",
        name="Rotary Screw Air Compressor",
        category="Utilities",
        metrics=[
            MetricDefinition(name="discharge_pressure_bar", unit="bar", lo=6.5, hi=8.5, hi_hi=9.5),
            MetricDefinition(name="discharge_temp_c", unit="°C", hi=95.0, hi_hi=110.0),
            MetricDefinition(name="motor_power_kw", unit="kW", hi=45.0),
            MetricDefinition(name="flow_rate_cfm", unit="CFM", lo=150.0),
            MetricDefinition(name="oil_differential_pressure_bar", unit="bar", hi=1.2, description="Oil filter pressure drop"),
            MetricDefinition(name="run_hours", unit="h"),
        ],
        derived=[
            DerivedMetricDefinition(
                name="specific_power_kw_cfm",
                unit="kW/CFM",
                expr="motor_power_kw / (flow_rate_cfm + 0.001)",
                description="Compressor specific power efficiency"
            )
        ],
        status_rules={
            "RUNNING": "discharge_pressure_bar > 6.0 and motor_power_kw > 5.0",
            "IDLE": "discharge_pressure_bar > 6.0 and motor_power_kw <= 5.0",
            "STOPPED": "motor_power_kw <= 1.0",
        },
        model_3d="models/air_compressor.glb",
        pm_defaults=[
            PMDefault(
                name="Air/Oil Filter & Separator Replacement",
                trigger_type="meter",
                interval_hours=2000,
                checklist=["Replace air intake filter element", "Replace oil separator cartridge", "Check belt tension"]
            )
        ],
        ai={"anomaly": True, "rul": True}
    ),

    # 6. Industrial Water Chiller
    "chiller": AssetTypeTemplate(
        id="chiller",
        name="Industrial Process Chiller",
        category="Utilities & Cooling",
        metrics=[
            MetricDefinition(name="chilled_water_inlet_c", unit="°C", hi=18.0),
            MetricDefinition(name="chilled_water_outlet_c", unit="°C", lo=7.0, hi=12.0, hi_hi=15.0),
            MetricDefinition(name="refrigerant_suction_bar", unit="bar", lo=3.0),
            MetricDefinition(name="refrigerant_discharge_bar", unit="bar", hi=18.0, hi_hi=22.0),
            MetricDefinition(name="compressor_power_kw", unit="kW", hi=30.0),
            MetricDefinition(name="cop", unit="", description="Coefficient of Performance"),
        ],
        derived=[
            DerivedMetricDefinition(
                name="delta_t_c",
                unit="°C",
                expr="chilled_water_inlet_c - chilled_water_outlet_c",
                description="Water temperature drop across evaporator"
            )
        ],
        status_rules={
            "RUNNING": "compressor_power_kw > 2.0",
            "STOPPED": "compressor_power_kw <= 2.0",
        },
        model_3d="models/chiller.glb",
        pm_defaults=[
            PMDefault(
                name="Condenser Coil Cleaning & Refrigerant Leak Check",
                trigger_type="calendar",
                interval_days=90,
                checklist=["Clean condenser coil fins", "Inspect sight glass for moisture", "Check refrigerant pressure"]
            )
        ],
        ai={"anomaly": True, "rul": True}
    ),

    # 7. Air Handling Unit (AHU)
    "ahu": AssetTypeTemplate(
        id="ahu",
        name="Air Handling Unit",
        category="HVAC & Cleanroom",
        metrics=[
            MetricDefinition(name="supply_air_temp_c", unit="°C", lo=18.0, hi=24.0),
            MetricDefinition(name="filter_dp_pa", unit="Pa", hi=250.0, hi_hi=400.0, description="Differential pressure across pre-filter"),
            MetricDefinition(name="fan_speed_rpm", unit="RPM", hi=1800),
            MetricDefinition(name="air_flow_m3h", unit="m³/h", lo=5000.0),
            MetricDefinition(name="fan_power_kw", unit="kW", hi=7.5),
        ],
        status_rules={
            "RUNNING": "fan_power_kw > 0.5",
            "STOPPED": "fan_power_kw <= 0.5",
        },
        model_3d="models/ahu.glb",
        pm_defaults=[
            PMDefault(
                name="Filter Inspection & Cleaning",
                trigger_type="meter",
                interval_hours=1000,
                checklist=["Inspect filter differential pressure", "Clean or replace pre-filter media", "Check fan belt"]
            )
        ],
        ai={"anomaly": True, "rul": False}
    ),

    # 8. Digital Energy / Power Meter (Schneider / Siemens / ABB)
    "energy_meter": AssetTypeTemplate(
        id="energy_meter",
        name="Digital Power & Energy Meter",
        category="Electrical Distribution",
        metrics=[
            MetricDefinition(name="voltage_v", unit="V", lo=380.0, hi=440.0),
            MetricDefinition(name="current_a", unit="A", hi=150.0),
            MetricDefinition(name="power_kw", unit="kW"),
            MetricDefinition(name="power_reactive_kvar", unit="kVAR"),
            MetricDefinition(name="power_factor", unit="", lo=0.85, description="Power factor (cos phi)"),
            MetricDefinition(name="frequency_hz", unit="Hz", lo=49.0, hi=51.0),
            MetricDefinition(name="energy_kwh", unit="kWh"),
        ],
        status_rules={
            "RUNNING": "voltage_v > 100.0",
            "OFFLINE": "voltage_v <= 100.0",
        },
        model_3d="models/energy_meter.glb",
        pm_defaults=[
            PMDefault(
                name="Meter Calibration & Thermal Imaging of Terminals",
                trigger_type="calendar",
                interval_days=180,
                checklist=["IR thermography on incoming busbars", "Verify CT ratio and firmware settings", "Test phase balance"]
            )
        ],
        ai={"anomaly": True, "rul": False}
    ),
}


def get_template(type_id: str) -> AssetTypeTemplate | None:
    """Retrieve asset type template by ID."""
    return TEMPLATES.get(type_id)
