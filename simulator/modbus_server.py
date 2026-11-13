"""
TwinOps Modbus TCP Simulator Server.
Exposes simulated Energy Meters and Pumps over Modbus TCP to validate
edge protocol connectors (TC-CON-02).
"""

import asyncio
import logging

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from simulator.plant import VirtualPlant

logger = logging.getLogger("twinops.simulator.modbus")


class ModbusSimulatorServer:
    """
    Modbus TCP server exposing energy meter and pump registers.
    Unit 1: EM-01 (Energy Meter 01)
    Unit 2: PUMP-01 (Coolant Supply Pump 01)
    """

    def __init__(self, plant: VirtualPlant, host: str = "0.0.0.0", port: int = 15020):
        self.plant = plant
        self.host = host
        self.port = port
        self.server: ModbusTcpServer | None = None
        self.server_task: asyncio.Task | None = None

        # Build SimDevices
        # 100 registers each
        self.data_em = SimData(address=0, count=100, datatype=DataType.REGISTERS, values=[0] * 100)
        self.dev_em = SimDevice(1, simdata=self.data_em)

        self.data_pump = SimData(
            address=0, count=100, datatype=DataType.REGISTERS, values=[0] * 100
        )
        self.dev_pump = SimDevice(2, simdata=self.data_pump)

    async def update_registers_from_plant(self):
        """Update Modbus register values from the plant's latest state."""
        if not self.server or not hasattr(self.server, "context"):
            return

        # Unit 1: EM-01
        em = self.plant.get_machine("EM-01")
        if em:
            msg = em.step(dt=0.0)
            if msg:
                m = msg.metrics
                v_scaled = int(float(m["voltage_v"].v) * 10)  # 415.0V -> 4150
                i_scaled = int(float(m["current_a"].v) * 10)  # 180.0A -> 1800
                p_scaled = int(float(m["power_kw"].v) * 100)  # 125.0kW -> 12500
                q_scaled = int(float(m["power_reactive_kvar"].v) * 100)
                pf_scaled = int(float(m["power_factor"].v) * 1000)  # 0.940 -> 940
                f_scaled = int(float(m["frequency_hz"].v) * 100)  # 50.02Hz -> 5002
                kwh = int(float(m["energy_kwh"].v))

                vals = [
                    v_scaled,
                    i_scaled,
                    p_scaled,
                    q_scaled,
                    pf_scaled,
                    f_scaled,
                    (kwh >> 16) & 0xFFFF,
                    kwh & 0xFFFF,
                ]
                # Function code 3 (Holding Registers), starting at address 0
                await self.server.context.async_setValues(1, 3, 0, vals)

        # Unit 2: PUMP-01
        pump = self.plant.get_machine("PUMP-01")
        if pump:
            msg = pump.step(dt=0.0)
            if msg:
                m = msg.metrics
                flow_s = int(float(m["flow_m3h"].v) * 10)  # 40.0 m3/h -> 400
                head_s = int(float(m["discharge_bar"].v) * 100)  # 5.5 bar -> 550
                temp_s = int(float(m["motor_temp_c"].v) * 10)  # 58.0 C -> 580
                vib_s = int(float(m["vibration_mm_s"].v) * 100)  # 2.1 mm/s -> 210
                pwr_s = int(float(m["power_kw"].v) * 10)

                vals2 = [
                    flow_s,
                    head_s,
                    temp_s,
                    vib_s,
                    pwr_s,
                ]
                await self.server.context.async_setValues(2, 3, 0, vals2)

    async def start(self):
        """Start Modbus TCP server in background."""
        logger.info(f"Starting Modbus TCP Simulator server on {self.host}:{self.port}")
        self.server = ModbusTcpServer(
            context=[self.dev_em, self.dev_pump], address=(self.host, self.port)
        )
        self.server_task = asyncio.create_task(self.server.serve_forever())

    async def stop(self):
        """Stop server."""
        if self.server:
            try:
                await self.server.shutdown()
            except Exception:
                pass
        if self.server_task and not self.server_task.done():
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
            logger.info("Modbus TCP Simulator server stopped.")
