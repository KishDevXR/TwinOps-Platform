"""
TwinOps Simulator MQTT Publisher.
Publishes canonical telemetry and event payloads to the MQTT broker (EMQX).
Ref: docs/04_architecture.md §3, docs/05_design_document.md §3
"""

import json
import logging
from typing import Optional
import paho.mqtt.client as mqtt

from services.common.canonical import CanonicalEventMessage, CanonicalTelemetryMessage
from services.common.mqtt_topics import event_topic, telemetry_topic

logger = logging.getLogger("twinops.simulator.publisher")


class MqttTelemetryPublisher:
    """
    Connects to MQTT broker and publishes canonical telemetry and event streams.
    """

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "twinops_simulator_plant",
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.client = mqtt.Client(
            client_id=client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        if username and password:
            self.client.username_pw_set(username, password)
        if use_tls:
            self.client.tls_set()

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.connected = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker {self.broker_host}:{self.broker_port}")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker (code={rc})")

    def connect(self):
        """Connect asynchronously to the broker."""
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.warning(f"Could not connect to MQTT broker {self.broker_host}:{self.broker_port}: {e}")

    def disconnect(self):
        """Disconnect and stop client loop."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.debug(f"Disconnect error: {e}")

    def publish_telemetry(self, msg: CanonicalTelemetryMessage) -> bool:
        """Publish Canonical Telemetry payload to twinops/{site}/{asset_id}/telemetry."""
        topic = telemetry_topic(msg.site, msg.asset_id)
        payload = msg.model_dump_json()

        if self.connected:
            info = self.client.publish(topic, payload, qos=1)
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        return False

    def publish_event(self, msg: CanonicalEventMessage) -> bool:
        """Publish Canonical Event payload to twinops/{site}/{asset_id}/event."""
        topic = event_topic(msg.site, msg.asset_id)
        payload = msg.model_dump_json()

        if self.connected:
            info = self.client.publish(topic, payload, qos=1)
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        return False
