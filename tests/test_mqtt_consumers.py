"""
MQTT consumers must hand messages from paho's network thread to the service event loop.
Regression: they called asyncio.get_running_loop() on the paho thread, which always fails,
so every live message was silently dropped. Requirements: CON-01 (MQTT ingest), TWN-01, ALM-01.
"""

import asyncio
import threading
from types import SimpleNamespace

from services.alarm.mqtt_consumer import AlarmMqttConsumer
from services.telemetry.mqtt_consumer import TelemetryMqttConsumer
from services.twin.mqtt_consumer import TwinMqttConsumer
from simulator.plant import VirtualPlant


def _paho_msg():
    m = VirtualPlant().tick(1.0)[0]
    return SimpleNamespace(
        topic=f"twinops/{m.site}/{m.asset_id}/telemetry", payload=m.model_dump_json().encode()
    )


def _deliver_from_thread(callback, msg):
    t = threading.Thread(target=callback, args=(None, None, msg))
    t.start()
    t.join()


async def _wait_for(cond, seconds=2.0):
    for _ in range(int(seconds / 0.02)):
        if cond():
            return True
        await asyncio.sleep(0.02)
    return False


class _Recorder:
    def __init__(self):
        self.got = []

    async def ingest_message(self, msg):
        self.got.append(msg)

    async def update_from_telemetry(self, msg):
        self.got.append(msg)


async def test_con_01_telemetry_consumer_ingests_message_from_paho_thread(monkeypatch):
    rec = _Recorder()
    c = TelemetryMqttConsumer(rec)
    monkeypatch.setattr(c.client, "connect", lambda *a, **k: None)  # no broker in tests
    monkeypatch.setattr(c.client, "loop_start", lambda: None)
    c.start()
    _deliver_from_thread(c._on_message, _paho_msg())
    assert await _wait_for(lambda: len(rec.got) == 1)
    assert rec.got[0].asset_id == "CNC-01"


async def test_twn_01_twin_consumer_updates_state_from_paho_thread(monkeypatch):
    rec = _Recorder()
    c = TwinMqttConsumer(rec)
    monkeypatch.setattr(c.client, "connect", lambda *a, **k: None)
    monkeypatch.setattr(c.client, "loop_start", lambda: None)
    c.start()
    _deliver_from_thread(c._on_message, _paho_msg())
    assert await _wait_for(lambda: len(rec.got) == 1)


async def test_alm_01_alarm_consumer_evaluates_message_from_paho_thread(monkeypatch):
    import paho.mqtt.client as mqtt

    seen = []
    clients = []

    class FakeClient:
        def __init__(self, *a, **k):
            clients.append(self)

        def connect_async(self, *a, **k):
            pass

        def loop_start(self):
            pass

        def loop_stop(self):
            pass

        def disconnect(self):
            pass

    monkeypatch.setattr(mqtt, "Client", FakeClient)
    c = AlarmMqttConsumer()

    async def record(topic, payload):
        seen.append(topic)

    monkeypatch.setattr(c, "handle_message", record)
    task = asyncio.create_task(c.start())
    assert await _wait_for(lambda: clients and hasattr(clients[0], "on_message"))
    _deliver_from_thread(clients[0].on_message, _paho_msg())
    assert await _wait_for(lambda: seen == ["twinops/PUNE-01/CNC-01/telemetry"])
    await c.stop()
    task.cancel()
