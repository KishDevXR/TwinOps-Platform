"""Shared test setup."""

import os
import tempfile
from pathlib import Path

# Tests get their own fresh database, never the dev stack's twinops.db (a running stack
# writes live telemetry into it). Must be set before services.common.database is imported.
_TEST_DB = Path(tempfile.gettempdir()) / "twinops_pytest.db"
_TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"

import paho.mqtt.client as mqtt
import pytest


@pytest.fixture(autouse=True)
def _no_real_mqtt_broker(monkeypatch):
    """Services started in tests must not reach a real broker.

    They use the same client IDs as a running stack, so connecting would take over (and
    silently kill) the live services' MQTT sessions.
    """
    monkeypatch.setattr(mqtt.Client, "connect", lambda self, *a, **k: 0)
    monkeypatch.setattr(mqtt.Client, "connect_async", lambda self, *a, **k: None)
