"""
Tests for Protocol Simulation: OPC UA and Modbus TCP.
Maps to test cases:
- TC-CON-01 (OPC UA subscription / read)
- TC-CON-02 (Modbus TCP poll)
"""

import asyncio

import pytest
from asyncua import Client as OpcUaClient
from pymodbus.client import AsyncModbusTcpClient

from simulator.modbus_server import ModbusSimulatorServer
from simulator.opcua_server import OpcUaSimulatorServer
from simulator.plant import VirtualPlant


@pytest.mark.asyncio
async def test_con_02_modbus_tcp_poll():
    """
    TC-CON-02: Modbus TCP poll.
    Verify Modbus server exposes registers matching plant telemetry.
    """
    plant = VirtualPlant(site="PUNE-01")
    modbus_server = ModbusSimulatorServer(plant, host="127.0.0.1", port=15021)
    await modbus_server.start()

    # Allow server to bind and update registers
    await asyncio.sleep(0.2)
    await modbus_server.update_registers_from_plant()

    client = AsyncModbusTcpClient("127.0.0.1", port=15021)
    connected = await client.connect()
    assert connected, "Failed to connect to Modbus TCP Simulator"

    try:
        # Read 8 registers from Unit 1 (EM-01) starting at address 0
        rr = await client.read_holding_registers(address=0, count=8, device_id=1)
        assert not rr.isError(), f"Modbus read error: {rr}"
        assert len(rr.registers) == 8

        # Voltage (scaled x 10) ~ 4150
        v_scaled = rr.registers[0]
        assert 3800 <= v_scaled <= 4400, f"Voltage out of range: {v_scaled}"

        # Current (scaled x 10) ~ 1800
        i_scaled = rr.registers[1]
        assert 800 <= i_scaled <= 2200, f"Current out of range: {i_scaled}"

        # Unit 2: PUMP-01 (read 5 registers)
        rr2 = await client.read_holding_registers(address=0, count=5, device_id=2)
        assert not rr2.isError()
        # Head (scaled x 100) ~ 550 (5.5 bar)
        head_scaled = rr2.registers[1]
        assert 400 <= head_scaled <= 700
    finally:
        client.close()
        await modbus_server.stop()


@pytest.mark.asyncio
async def test_con_01_opcua_subscribe_and_read():
    """
    TC-CON-01: OPC UA read / subscribe.
    Verify OPC UA server exposes CNC tags that match plant simulation.
    """
    plant = VirtualPlant(site="PUNE-01")
    opc_server = OpcUaSimulatorServer(plant, endpoint="opc.tcp://127.0.0.1:48401/twinops/server/")
    await opc_server.start()
    await asyncio.sleep(0.2)
    await opc_server.update_nodes_from_plant()

    client = OpcUaClient(url="opc.tcp://127.0.0.1:48401/twinops/server/")
    await client.connect()

    try:
        ns = await client.get_namespace_index("http://twinops.plant/pune01")
        assert ns > 0
        # Check CNC-01 nodes
        temp_node = opc_server.tag_nodes["CNC-01.SpindleTemp"]
        val = await temp_node.read_value()
        assert val > 20.0 and val < 100.0

        rpm_node = opc_server.tag_nodes["CNC-01.SpindleRPM"]
        rpm = await rpm_node.read_value()
        assert rpm > 5000.0

        # Verify Pump-01 tags exist and have values
        pump_flow = await opc_server.tag_nodes["PUMP-01.Flow"].read_value()
        assert pump_flow > 20.0

        # Verify compressor tags
        comp_p = await opc_server.tag_nodes["COMP-01.DischargePressure"].read_value()
        assert comp_p > 5.0
    finally:
        await client.disconnect()
        await opc_server.stop()
