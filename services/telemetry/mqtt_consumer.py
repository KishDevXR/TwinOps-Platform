"""
TwinOps Telemetry MQTT Consumer.
Subscribes to twinops/{site}/{asset}/telemetry and feeds the ingest pipeline.
Ref: docs/04_architecture.md §3
"""

import asyncio
import json
import logging

import paho.mqtt.client as mqtt

from services.common.canonical import CanonicalTelemetryMessage
from services.telemetry.ingest import TelemetryIngestService

logger = logging.getLogger("twinops.telemetry.mqtt")


class TelemetryMqttConsumer:
    """
    Subscribes to telemetry topics and pushes messages into TelemetryIngestService.
    """

    def __init__(
        self,
        ingest_service: TelemetryIngestService,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "twinops_telemetry_service",
        topic_pattern: str = "twinops/+/+/telemetry",
    ):
        self.ingest_service = ingest_service
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
            logger.info(f"Connected to MQTT broker {self.broker_host}:{self.broker_port}")
            self.client.subscribe(self.topic_pattern, qos=1)
            logger.info(f"Subscribed to topic: {self.topic_pattern}")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            telemetry_msg = CanonicalTelemetryMessage.model_validate(payload)
            # paho calls this on its own thread: hand the message to the service's event loop
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self.ingest_service.ingest_message(telemetry_msg), self._loop
                )
        except Exception as e:
            logger.error(f"Failed to process telemetry payload from {msg.topic}: {e}")

    def start(self):
        """Start consumer loop in background thread. Call from the service's event loop."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
            logger.warning("No running event loop: MQTT messages will not be ingested.")
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info("MQTT Telemetry Consumer loop started.")
        except Exception as e:
            logger.warning(
                f"Could not connect to MQTT broker {self.broker_host}:{self.broker_port}: {e}"
            )

    def stop(self):
        """Stop consumer loop."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT Telemetry Consumer stopped.")
        except Exception as e:
            logger.debug(f"Stop error: {e}")
