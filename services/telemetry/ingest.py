"""
TwinOps Telemetry Ingestion Service.
High-throughput micro-batching pipeline converting canonical telemetry messages
into database records for TimescaleDB / SQLite.
Ref: docs/04_architecture.md §3, docs/05_design_document.md §2-3
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert

from services.common.canonical import CanonicalTelemetryMessage
from services.common.database import TelemetryModel, async_session_factory

logger = logging.getLogger("twinops.telemetry.ingest")


class TelemetryIngestService:
    """
    Micro-batch buffer and inserter for high-frequency telemetry.
    Unpacks canonical message metric dictionaries into relational rows.
    """

    def __init__(
        self, batch_size: int = 500, flush_interval_s: float = 0.2, max_buffer_size: int = 50000
    ):
        self.batch_size = batch_size
        self.flush_interval_s = flush_interval_s
        self.max_buffer_size = max_buffer_size

        self.buffer: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False

        # Metrics & Telemetry Stats
        self.total_records_ingested = 0
        self.total_batches_flushed = 0
        self.last_flush_ts: datetime | None = None

    def start(self):
        """Start the background micro-batch periodic flusher."""
        if not self._running:
            self._running = True
            self._flush_task = asyncio.create_task(self._periodic_flush_loop())
            logger.info("TelemetryIngestService flush loop started.")

    async def stop(self):
        """Stop flusher and drain any remaining buffered records."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # Final drain
        await self.flush()
        logger.info("TelemetryIngestService stopped and buffer drained.")

    async def ingest_message(self, msg: CanonicalTelemetryMessage):
        """
        Unpack and buffer a CanonicalTelemetryMessage.
        Each metric key/value pair becomes an independent time-series entry.
        """
        records: list[dict[str, Any]] = []
        for metric_name, mv in msg.metrics.items():
            # Only numeric values are stored in the time-series hypertable
            if isinstance(mv.v, (int, float, bool)):
                records.append(
                    {
                        "ts": msg.ts,
                        "asset_id": msg.asset_id,
                        "metric": metric_name,
                        "value": float(mv.v),
                        "quality": int(mv.q),
                    }
                )

        if not records:
            return

        async with self._lock:
            self.buffer.extend(records)
            self.total_records_ingested += len(records)
            should_flush = len(self.buffer) >= self.batch_size

        if should_flush:
            await self.flush()

    async def ingest_batch(self, messages: list[CanonicalTelemetryMessage]):
        """Ingest a batch of CanonicalTelemetryMessages."""
        for msg in messages:
            await self.ingest_message(msg)

    # Alias for canonical ingest
    ingest_canonical = ingest_message


    async def flush(self) -> int:
        """Flush all currently buffered records to database."""
        async with self._lock:
            if not self.buffer:
                return 0
            to_flush = list(self.buffer)
            self.buffer.clear()

        # Batch insert into DB
        async with async_session_factory() as session:
            try:
                await session.execute(insert(TelemetryModel), to_flush)
                await session.commit()
                self.total_batches_flushed += 1
                self.last_flush_ts = datetime.now(UTC)
                logger.debug(f"Flushed {len(to_flush)} telemetry records to database.")
                return len(to_flush)
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to flush telemetry batch of {len(to_flush)} records: {e}")
                # Re-queue failed records back into buffer if space permits
                async with self._lock:
                    if len(self.buffer) + len(to_flush) <= self.max_buffer_size:
                        self.buffer[0:0] = to_flush
                raise

    async def _periodic_flush_loop(self):
        """Periodic loop ensuring buffered records don't wait longer than flush_interval_s."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval_s)
                if len(self.buffer) > 0:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telemetry periodic flush loop: {e}")


# Default singleton ingest service instance
ingest_service = TelemetryIngestService()

