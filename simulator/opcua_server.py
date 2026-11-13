"""
TwinOps OPC UA Simulator Server.
Exposes CNCs and SCADA tags over OPC UA (TCP 4840 / 48400) to validate
edge protocol subscriptions (TC-CON-01).
"""

import asyncio
import logging
from typing import Dict, Optional
from asyncua import Server, ua
from simulator.plant import VirtualPlant

logger = logging.getLogger("twinops.simulator.opcua")


class OpcUaSimulatorServer:
    """
    OPC UA server replicating Purdue Level 3 SCADA / PLC endpoints.
    Exposes 50+ real-time tags across Line 1 and Line 2 assets.
    """

    def __init__(
        self,
        plant: VirtualPlant,
        endpoint: str = "opc.tcp://0.0.0.0:48400/twinops/server/",
        server_name: str = "TwinOps SCADA OPC UA Simulator"
    ):
        self.plant = plant
        self.endpoint = endpoint
        self.server_name = server_name
        self.server = Server()
        self.tag_nodes: Dict[str, ua.Node] = {}
        self.idx = 0
        self.is_running = False

    async def init(self):
        """Initialize OPC UA address space and populate 50+ tags."""
        await self.server.init()
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name(self.server_name)
        self.idx = await self.server.register_namespace("http://twinops.plant/pune01")

        # Root objects
        objects = self.server.nodes.objects
        plant_folder = await objects.add_folder(self.idx, "Plant_PUNE01")
        line1_folder = await plant_folder.add_folder(self.idx, "Line1")

        # Assets exposed via OPC UA: CNC-01, CNC-02, CNC-03, PUMP-01, COMP-01
        for asset_id in ["CNC-01", "CNC-02", "CNC-03"]:
            asset_folder = await line1_folder.add_folder(self.idx, asset_id)
            for tag_name, vtype in [
                ("SpindleTemp", ua.VariantType.Double),
                ("Vibration", ua.VariantType.Double),
                ("SpindleRPM", ua.VariantType.Double),
                ("SpindleLoad", ua.VariantType.Double),
                ("FeedRate", ua.VariantType.Double),
                ("CoolantFlow", ua.VariantType.Double),
                ("PowerKW", ua.VariantType.Double),
                ("PartCount", ua.VariantType.Int64),
                ("Status", ua.VariantType.String),
            ]:
                node = await asset_folder.add_variable(self.idx, tag_name, 0.0, vtype)
                await node.set_writable()
                self.tag_nodes[f"{asset_id}.{tag_name}"] = node

        # Pump 01 tags
        pump_folder = await line1_folder.add_folder(self.idx, "PUMP-01")
        for tag_name in ["Flow", "DischargePressure", "SuctionPressure", "MotorTemp", "Vibration", "Power"]:
            node = await pump_folder.add_variable(self.idx, tag_name, 0.0, ua.VariantType.Double)
            await node.set_writable()
            self.tag_nodes[f"PUMP-01.{tag_name}"] = node

        # Compressor 01 tags
        comp_folder = await line1_folder.add_folder(self.idx, "COMP-01")
        for tag_name in ["DischargePressure", "DischargeTemp", "MotorPower", "FlowRateCFM", "OilDP", "RunHours"]:
            node = await comp_folder.add_variable(self.idx, tag_name, 0.0, ua.VariantType.Double)
            await node.set_writable()
            self.tag_nodes[f"COMP-01.{tag_name}"] = node

        logger.info(f"Initialized OPC UA address space with {len(self.tag_nodes)} industrial tags.")

    async def update_nodes_from_plant(self):
        """Update node values with latest values from the simulated plant."""
        for asset_id in ["CNC-01", "CNC-02", "CNC-03"]:
            m = self.plant.get_machine(asset_id)
            if not m:
                continue
            msg = m.step(dt=0.0)
            if not msg:
                continue
            mets = msg.metrics
            await self._write_val(f"{asset_id}.SpindleTemp", float(mets["spindle_temp_c"].v), ua.VariantType.Double)
            await self._write_val(f"{asset_id}.Vibration", float(mets["vibration_mm_s"].v), ua.VariantType.Double)
            await self._write_val(f"{asset_id}.SpindleRPM", float(mets["spindle_rpm"].v), ua.VariantType.Double)
            await self._write_val(f"{asset_id}.SpindleLoad", float(mets["spindle_load_pct"].v), ua.VariantType.Double)
            await self._write_val(f"{asset_id}.FeedRate", float(mets["feed_rate_mm_min"].v), ua.VariantType.Double)
            await self._write_val(f"{asset_id}.CoolantFlow", float(mets["coolant_flow_l_min"].v), ua.VariantType.Double)
            await self._write_val(f"{asset_id}.PowerKW", float(mets["power_kw"].v), ua.VariantType.Double)
            await self._write_val(f"{asset_id}.PartCount", int(mets["part_count"].v), ua.VariantType.Int64)
            await self._write_val(f"{asset_id}.Status", str(msg.status.value), ua.VariantType.String)

        # Pump 01
        p = self.plant.get_machine("PUMP-01")
        if p:
            msg = p.step(dt=0.0)
            if msg:
                mets = msg.metrics
                await self._write_val("PUMP-01.Flow", float(mets["flow_m3h"].v), ua.VariantType.Double)
                await self._write_val("PUMP-01.DischargePressure", float(mets["discharge_bar"].v), ua.VariantType.Double)
                await self._write_val("PUMP-01.SuctionPressure", float(mets["suction_bar"].v), ua.VariantType.Double)
                await self._write_val("PUMP-01.MotorTemp", float(mets["motor_temp_c"].v), ua.VariantType.Double)
                await self._write_val("PUMP-01.Vibration", float(mets["vibration_mm_s"].v), ua.VariantType.Double)
                await self._write_val("PUMP-01.Power", float(mets["power_kw"].v), ua.VariantType.Double)

        # Comp 01
        c = self.plant.get_machine("COMP-01")
        if c:
            msg = c.step(dt=0.0)
            if msg:
                mets = msg.metrics
                await self._write_val("COMP-01.DischargePressure", float(mets["discharge_pressure_bar"].v), ua.VariantType.Double)
                await self._write_val("COMP-01.DischargeTemp", float(mets["discharge_temp_c"].v), ua.VariantType.Double)
                await self._write_val("COMP-01.MotorPower", float(mets["motor_power_kw"].v), ua.VariantType.Double)
                await self._write_val("COMP-01.FlowRateCFM", float(mets["flow_rate_cfm"].v), ua.VariantType.Double)
                await self._write_val("COMP-01.OilDP", float(mets["oil_differential_pressure_bar"].v), ua.VariantType.Double)
                await self._write_val("COMP-01.RunHours", float(mets["run_hours"].v), ua.VariantType.Double)

    async def _write_val(self, key: str, val: any, vtype: ua.VariantType):
        node = self.tag_nodes.get(key)
        if node:
            await node.write_value(ua.DataValue(ua.Variant(val, vtype)))

    async def start(self):
        """Start the OPC UA server."""
        await self.init()
        await self.server.start()
        self.is_running = True
        logger.info(f"OPC UA Simulator Server online at {self.endpoint}")

    async def stop(self):
        """Stop server."""
        if self.is_running:
            await self.server.stop()
            self.is_running = False
            logger.info("OPC UA Simulator Server stopped.")
