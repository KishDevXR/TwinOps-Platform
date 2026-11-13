"""
TwinOps Alarm MQTT Consumer
Subscribes to telemetry topics and feeds canonical messages into AlarmRulesEngine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

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
        """Connect to MQTT broker and start subscription loop."""
        try:
            import aiomqtt
        except ImportError:
            logger.warning("aiomqtt not installed; MQTT subscription disabled.")
            return

        self.running = True
        logger.info(
            "Starting Alarm MQTT Consumer connecting to %s:%d (%s)",
            self.broker_host,
            self.broker_port,
            self.topic,
        )

        while self.running:
            try:
                async with aiomqtt.Client(self.broker_host, self.broker_port) as client:
                    await client.subscribe(self.topic)
                    logger.info("Alarm consumer subscribed to %s", self.topic)
                    async for message in client.messages:
                        if not self.running:
                            break
                        await self.handle_message(str(message.topic), message.payload)
            except Exception as e:
                if not self.running:
                    break
                logger.debug("MQTT broker unavailable (%s), retrying in 3s...", e)
                await asyncio.sleep(3.0)

    async def stop(self):
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
