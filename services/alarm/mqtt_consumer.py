"""
TwinOps Alarm MQTT Consumer
Subscribes to telemetry topics and feeds canonical messages into AlarmRulesEngine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import paho.mqtt.client as mqtt

from services.alarm.engine import alarm_engine
from services.common.canonical import CanonicalTelemetryMessage
from services.common.database import get_async_session

logger = logging.getLogger("twinops.alarm.mqtt")


class AlarmMqttConsumer:
    def __init__(
        self,
        broker_host: str | None = None,
        broker_port: int | None = None,
        topic: str = "twinops/+/+/telemetry",
    ):
        self.broker_host = broker_host or os.getenv("MQTT_HOST", "127.0.0.1")
        self.broker_port = broker_port or int(os.getenv("MQTT_PORT", "1883"))
        self.topic = topic
        self.running = False
        self._task: asyncio.Task | None = None
        self._client: mqtt.Client | None = None

    async def handle_message(self, topic: str, payload_bytes: bytes):
        """Process incoming canonical telemetry and evaluate alarm rules."""
        try:
            raw_json = json.loads(payload_bytes.decode("utf-8"))
            telemetry = CanonicalTelemetryMessage.model_validate(raw_json)

            async with get_async_session() as session:
                await alarm_engine.evaluate_telemetry(telemetry, session=session)
                await session.commit()

        except Exception as e:
            logger.debug("Failed to evaluate telemetry on %s: %s", topic, e)

    async def start(self):
        """Subscribe via paho (network thread) and evaluate messages one at a time here.

        paho is used instead of aiomqtt: aiomqtt needs a selector event loop, which
        uvicorn does not use on Windows, and it is not a project dependency.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue(maxsize=5000)

        def _enqueue(item: tuple[str, bytes]):
            if not queue.full():  # shed load rather than grow without bound
                queue.put_nowait(item)

        def _on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                client.subscribe(self.topic, qos=1)
                logger.info("Alarm consumer subscribed to %s", self.topic)

        def _on_message(client, userdata, msg):
            loop.call_soon_threadsafe(_enqueue, (msg.topic, msg.payload))

        self._client = mqtt.Client(
            client_id="twinops_alarm_service", callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )
        self._client.on_connect = _on_connect
        self._client.on_message = _on_message
        # connect_async + loop_start retries in the background if the broker is not up yet
        self._client.connect_async(self.broker_host, self.broker_port, keepalive=60)
        self._client.loop_start()
        self.running = True
        logger.info(
            "Starting Alarm MQTT Consumer connecting to %s:%d (%s)",
            self.broker_host,
            self.broker_port,
            self.topic,
        )

        while self.running:
            topic, payload = await queue.get()
            await self.handle_message(topic, payload)

    async def stop(self):
        self.running = False
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        if self._task and not self._task.done():
            self._task.cancel()
