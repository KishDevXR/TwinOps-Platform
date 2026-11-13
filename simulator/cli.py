"""
TwinOps Virtual Plant Simulator Command Line Interface.
Run standalone or embedded in Docker / test environments.
Usage:
  python -m simulator.cli --site PUNE-01 --interval 1.0 --dump-stdout
"""

import argparse
import asyncio
import logging
import signal
import sys

from simulator.modbus_server import ModbusSimulatorServer
from simulator.opcua_server import OpcUaSimulatorServer
from simulator.plant import VirtualPlant
from simulator.publisher import MqttTelemetryPublisher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("twinops.simulator.cli")


async def main():
    parser = argparse.ArgumentParser(description="TwinOps Virtual Plant Simulator")
    parser.add_argument("--site", default="PUNE-01", help="Plant Site ID (default: PUNE-01)")
    parser.add_argument("--interval", type=float, default=1.0, help="Tick interval in seconds (default: 1.0)")
    parser.add_argument("--mqtt-host", default="localhost", help="MQTT Broker host")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT Broker port")
    parser.add_argument("--enable-modbus", action="store_true", help="Start Modbus TCP server (port 5020)")
    parser.add_argument("--enable-opcua", action="store_true", help="Start OPC UA server (port 48400)")
    parser.add_argument("--dump-stdout", action="store_true", help="Print generated telemetry to stdout")
    parser.add_argument("--inject", action="append", help="Inject fault: <asset_id>:<fault_type>[:<severity>]")
    args = parser.parse_args()

    plant = VirtualPlant(site=args.site)

    # Apply initial fault injections if specified
    if args.inject:
        for inj in args.inject:
            parts = inj.split(":")
            aid = parts[0]
            ftype = parts[1]
            sev = float(parts[2]) if len(parts) > 2 else 1.0
            plant.inject_fault(aid, ftype, severity=sev)

    # Initialize MQTT publisher
    publisher = MqttTelemetryPublisher(
        broker_host=args.mqtt_host,
        broker_port=args.mqtt_port
    )
    publisher.connect()

    # Servers
    modbus_server = None
    if args.enable_modbus:
        modbus_server = ModbusSimulatorServer(plant, host="0.0.0.0", port=5020)
        await modbus_server.start()

    opcua_server = None
    if args.enable_opcua:
        opcua_server = OpcUaSimulatorServer(plant, endpoint="opc.tcp://0.0.0.0:48400/twinops/server/")
        await opcua_server.start()

    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows event loop limitation for add_signal_handler

    logger.info(f"TwinOps Simulator active for {len(plant.machines)} assets across 2 lines.")

    sample_counter = 0

    async def on_telemetry(msg):
        nonlocal sample_counter
        publisher.publish_telemetry(msg)
        if args.dump-stdout and sample_counter < 5:
            print(f"[{msg.ts.strftime('%H:%M:%S')}] {msg.asset_id} ({msg.status.value}): "
                  f"{ {k: v.v for k, v in list(msg.metrics.items())[:3]} }")
            sample_counter += 1

    try:
        # Periodic update task for Modbus and OPC UA
        async def background_servers_tick():
            while not stop_event.is_set():
                if modbus_server:
                    modbus_server.update_registers_from_plant()
                if opcua_server:
                    await opcua_server.update_nodes_from_plant()
                await asyncio.sleep(args.interval)

        bg_task = asyncio.create_task(background_servers_tick())

        await plant.run_continuous(
            interval_s=args.interval,
            on_telemetry=on_telemetry,
            stop_event=stop_event
        )

        bg_task.cancel()
    finally:
        publisher.disconnect()
        if modbus_server:
            await modbus_server.stop()
        if opcua_server:
            await opcua_server.stop()
        logger.info("Simulator gracefully terminated.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
