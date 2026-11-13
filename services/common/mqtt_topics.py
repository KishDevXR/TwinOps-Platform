"""
TwinOps MQTT Topic Definitions and Helpers.
Ref: docs/05_design_document.md §3
"""


# Topic patterns
# twinops/{site}/{asset}/telemetry  (edge -> cloud)
# twinops/{site}/{asset}/event      (edge -> cloud)
# twinops/{site}/edge/{gw}/health   (edge -> cloud)
# twinops/{site}/edge/{gw}/config   (cloud -> edge)


def telemetry_topic(site: str, asset_id: str) -> str:
    """Generate MQTT topic for asset telemetry."""
    return f"twinops/{site}/{asset_id}/telemetry"


def event_topic(site: str, asset_id: str) -> str:
    """Generate MQTT topic for asset events & edge alarms."""
    return f"twinops/{site}/{asset_id}/event"


def gateway_health_topic(site: str, gateway_id: str) -> str:
    """Generate MQTT topic for edge gateway heartbeat."""
    return f"twinops/{site}/edge/{gateway_id}/health"


def gateway_config_topic(site: str, gateway_id: str) -> str:
    """Generate MQTT topic for cloud-to-edge gateway config."""
    return f"twinops/{site}/edge/{gateway_id}/config"


def parse_topic(topic: str) -> dict[str, str] | None:
    """
    Parse an incoming MQTT topic into its components.
    Returns dict with keys or None if pattern does not match.
    """
    parts = topic.strip("/").split("/")
    if len(parts) < 4 or parts[0] != "twinops":
        return None

    site = parts[1]

    if parts[2] == "edge":
        # twinops/{site}/edge/{gw}/{channel}
        if len(parts) >= 5:
            return {"type": "gateway", "site": site, "gateway_id": parts[3], "channel": parts[4]}
    else:
        # twinops/{site}/{asset}/{channel}
        asset_id = parts[2]
        channel = parts[3]
        return {"type": "asset", "site": site, "asset_id": asset_id, "channel": channel}

    return None
