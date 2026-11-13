"""
TwinOps Twin MQTT Consumer.
Subscribes to telemetry topics to keep the live digital twin state cache synchronized.
Ref: docs/04_architecture.md §3
"""

import asyncio
import json
import logging

import paho.mqtt.client as mqtt

from services.common.canonical import CanonicalTelemetryMessage
from services.twin.state_store import TwinStateStore

logger = logging.getLogger("twinops.twin.mqtt")


class TwinMqttConsumer:
    """
    Subscribes to twinops/{site}/{asset}/telemetry and pushes to TwinStateStore.
    """

    def __init__(
        self,
        state_store: TwinStateStore,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "twinops_twin_service",
        topic_pattern: str = "twinops/+/+/telemetry",
    ):
        self.state_store = state_store
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.topic_pattern = topic_pattern
        self.client = mqtt.Client(
            client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.connected = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            logger.info(
                f"Twin service connected to MQTT broker {self.broker_host}:{self.broker_port}"
            )
            self.client.subscribe(self.topic_pattern, qos=1)
        else:
            logger.error(f"Twin service MQTT connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            telemetry_msg = CanonicalTelemetryMessage.model_validate(payload)
            # paho calls this on its own thread: hand the message to the service's event loop
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self.state_store.update_from_telemetry(telemetry_msg), self._loop
                )
        except Exception as e:
            logger.error(f"Failed to process live twin payload: {e}")

    def start(self):
        """Start consumer loop in background thread. Call from the service's event loop."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
            logger.warning("No running event loop: MQTT messages will not update twins.")
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info("Live Twin MQTT Consumer started.")
        except Exception as e:
            logger.warning(
                f"Could not connect to MQTT broker {self.broker_host}:{self.broker_port}: {e}"
            )

    def stop(self):
        """Stop consumer loop."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Live Twin MQTT Consumer stopped.")
        except Exception as e:
            logger.debug(f"Stop error: {e}")
