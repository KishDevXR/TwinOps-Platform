"""
TwinOps Real-Time WebSocket Connection Manager.
Handles fan-out broadcasting of digital twin state changes to 3D web viewers and dashboards.
Ref: docs/04_architecture.md §3, docs/05_design_document.md §5
"""

import asyncio
import logging

from fastapi import WebSocket

from services.twin.state_store import LiveAssetTwin

logger = logging.getLogger("twinops.twin.ws")


class WebSocketManager:
    """
    Manages active client WebSocket connections and broadcasts twin telemetry streams.
    """

    def __init__(self):
        # site -> set of WebSockets
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, site: str = "PUNE-01"):
        """Accept new WebSocket connection and track by site."""
        await websocket.accept()
        async with self._lock:
            if site not in self.active_connections:
                self.active_connections[site] = set()
            self.active_connections[site].add(websocket)
        logger.info(
            f"WebSocket client connected to site '{site}'. Total: {len(self.active_connections[site])}"
        )

    async def disconnect(self, websocket: WebSocket, site: str = "PUNE-01"):
        """Remove disconnected client."""
        async with self._lock:
            if site in self.active_connections:
                self.active_connections[site].discard(websocket)
                if not self.active_connections[site]:
                    del self.active_connections[site]
        logger.info(f"WebSocket client disconnected from site '{site}'.")

    async def broadcast_twin_update(self, twin: LiveAssetTwin):
        """Broadcast single asset twin state update to all clients on that site."""
        site = twin.site
        payload = {
            "type": "twin_update",
            "asset_id": twin.asset_id,
            "status_color": twin.status_color,
            "operational_status": twin.operational_status,
            "last_updated": twin.last_updated.isoformat(),
            "metrics": {k: {"v": v.v, "q": v.q} for k, v in twin.metrics.items()},
            "derived_metrics": twin.derived_metrics,
            "status_reasons": twin.status_reasons,
        }

        async with self._lock:
            sockets = list(self.active_connections.get(site, set()))

        if not sockets:
            return

        dead_sockets = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket client: {e}")
                dead_sockets.append(ws)

        if dead_sockets:
            async with self._lock:
                for ws in dead_sockets:
                    if site in self.active_connections:
                        self.active_connections[site].discard(ws)

    async def broadcast_full_snapshot(self, websocket: WebSocket, twins: list[LiveAssetTwin]):
        """Send complete plant snapshot upon initial client connection."""
        snapshot = [
            {
                "asset_id": t.asset_id,
                "name": t.name,
                "type_id": t.type_id,
                "criticality": t.criticality,
                "status_color": t.status_color,
                "operational_status": t.operational_status,
                "position_3d": t.position_3d,
                "model_3d": t.model_3d,
                "last_updated": t.last_updated.isoformat(),
                "metrics": {k: {"v": v.v, "q": v.q} for k, v in t.metrics.items()},
                "derived_metrics": t.derived_metrics,
                "status_reasons": t.status_reasons,
            }
            for t in twins
        ]
        await websocket.send_json({"type": "snapshot", "assets": snapshot})
